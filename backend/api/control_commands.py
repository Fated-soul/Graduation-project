from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError

from backend.api.errors import raise_database_http_exception
from backend.schemas.common import APIResponse
from backend.schemas.control_command import (
    ControlCommandAck,
    ControlCommandCreate,
    ControlCommandStatus,
    ControlCommandWebSocketAck,
)
from backend.schemas.device import DeviceStatusUpdate
from backend.services import control_command_service, device_service
from backend.services.device_connection_manager import device_connection_manager

router = APIRouter(tags=["control_commands"])


@router.post(
    "/api/control-commands",
    response_model=APIResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_control_command(command: ControlCommandCreate) -> APIResponse:
    try:
        device = device_service.get_device(command.device_id)
        if device is None:
            raise HTTPException(status_code=404, detail="device not found")

        created = control_command_service.create_command(command)
        sent_command = control_command_service.mark_sent(created["command_id"])
        if sent_command is None:
            raise HTTPException(status_code=404, detail="control command not found")

        delivered = await device_connection_manager.send_json(
            command.device_id,
            control_command_service.build_websocket_payload(sent_command),
        )
        if not delivered:
            failed = control_command_service.mark_failed(
                created["command_id"],
                "device websocket not connected",
            )
            raise HTTPException(
                status_code=409,
                detail=jsonable_encoder(
                    {
                        "message": "设备未通过 WebSocket 在线，命令未下发。",
                        "data": failed,
                    }
                ),
            )

    except HTTPException:
        raise
    except Exception as exc:
        raise_database_http_exception(exc)

    response_data = dict(sent_command)
    response_data["delivered"] = True
    return APIResponse(message="control command delivered", data=response_data)


@router.get("/api/control-commands", response_model=APIResponse)
def list_control_commands(
    device_id: str | None = Query(default=None, min_length=1, max_length=50),
    command_status: ControlCommandStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
) -> APIResponse:
    try:
        commands = control_command_service.list_commands(
            device_id=device_id,
            status=command_status,
            limit=limit,
        )
    except Exception as exc:
        raise_database_http_exception(exc)
    return APIResponse(data=commands)


@router.get("/api/control-commands/connections", response_model=APIResponse)
def list_device_connections() -> APIResponse:
    return APIResponse(
        data={
            "connected_device_ids": device_connection_manager.connected_device_ids(),
        }
    )


@router.get("/api/control-commands/{command_id}", response_model=APIResponse)
def get_control_command(command_id: str) -> APIResponse:
    try:
        command = control_command_service.get_command(command_id)
    except Exception as exc:
        raise_database_http_exception(exc)
    if command is None:
        raise HTTPException(status_code=404, detail="control command not found")
    return APIResponse(data=command)


@router.post("/api/control-commands/{command_id}/ack", response_model=APIResponse)
def acknowledge_control_command(command_id: str, ack: ControlCommandAck) -> APIResponse:
    try:
        updated = control_command_service.acknowledge_command(command_id, ack)
    except Exception as exc:
        raise_database_http_exception(exc)
    if updated is None:
        raise HTTPException(status_code=404, detail="control command not found")
    return APIResponse(message="control command acknowledged", data=updated)


@router.websocket("/api/ws/devices/{device_id}")
async def device_websocket(websocket: WebSocket, device_id: str) -> None:
    await device_connection_manager.connect(device_id, websocket)
    try:
        device_service.update_status(device_id, DeviceStatusUpdate(online=True))
    except Exception:
        pass

    await websocket.send_json(
        {
            "type": "connected",
            "device_id": device_id,
            "message": "device websocket connected",
        }
    )

    try:
        while True:
            text = await websocket.receive_text()
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "invalid json"})
                continue

            if payload.get("type") == "heartbeat":
                try:
                    device_service.update_status(device_id, DeviceStatusUpdate(online=True))
                except Exception:
                    pass
                await websocket.send_json({"type": "heartbeat_ack", "device_id": device_id})
                continue

            if "command_id" not in payload:
                await websocket.send_json({"type": "error", "message": "unknown message"})
                continue

            try:
                ack = ControlCommandWebSocketAck.model_validate(payload)
                updated = control_command_service.acknowledge_command(
                    ack.command_id,
                    ControlCommandAck(
                        status=ack.status,
                        message=ack.message,
                        started_at=ack.started_at,
                    ),
                )
            except ValidationError as exc:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "invalid ack payload",
                        "detail": exc.errors(),
                    }
                )
                continue
            except Exception as exc:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "ack store failed",
                        "detail": str(exc),
                    }
                )
                continue

            if updated is None:
                await websocket.send_json(
                    {
                        "type": "ack_error",
                        "command_id": ack.command_id,
                        "message": "control command not found",
                    }
                )
                continue

            await websocket.send_json(
                {
                    "type": "ack_received",
                    "command_id": ack.command_id,
                    "status": ack.status,
                }
            )
    except WebSocketDisconnect:
        pass
    finally:
        removed = device_connection_manager.disconnect(device_id, websocket)
        if removed:
            try:
                device_service.update_status(device_id, DeviceStatusUpdate(online=False))
            except Exception:
                pass
