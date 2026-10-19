from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.repositories import control_command_repository
from backend.schemas.control_command import ControlCommandAck, ControlCommandCreate
from backend.schemas.stimulation import StimulationEventCreate
from backend.services import stimulation_service


def create_command(command: ControlCommandCreate) -> dict[str, Any]:
    return control_command_repository.create_control_command(
        command=command,
        command_id=str(uuid4()),
    )


def get_command(command_id: str) -> dict[str, Any] | None:
    return control_command_repository.get_control_command(command_id)


def list_commands(
    device_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    return control_command_repository.list_control_commands(
        device_id=device_id,
        status=status,
        limit=limit,
    )


def mark_sent(command_id: str) -> dict[str, Any] | None:
    return control_command_repository.mark_command_sent(command_id)


def mark_failed(command_id: str, error_message: str) -> dict[str, Any] | None:
    return control_command_repository.mark_command_failed(command_id, error_message)


def build_websocket_payload(command: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "control_command",
        "command_id": command["command_id"],
        "mouse_id": command["mouse_id"],
        "device_id": command["device_id"],
        "command_type": command["command_type"],
        "duration_ms": command["duration_ms"],
        "intensity": command.get("intensity"),
    }


def acknowledge_command(command_id: str, ack: ControlCommandAck) -> dict[str, Any] | None:
    existing = control_command_repository.get_control_command(command_id)
    if existing is None:
        return None

    updated = control_command_repository.acknowledge_command(
        command_id=command_id,
        status=ack.status,
        message=ack.message,
    )
    if updated is None:
        return None

    if ack.status == "completed" and existing.get("status") != "completed":
        started_at = ack.started_at or updated.get("dispatched_at") or updated.get("requested_at")
        event = StimulationEventCreate(
            mouse_id=updated["mouse_id"],
            device_id=updated["device_id"],
            event_type=updated["command_type"],
            duration_ms=updated["duration_ms"],
            intensity=updated.get("intensity"),
            started_at=started_at,
        )
        updated["stimulation_event"] = stimulation_service.create_event(event)

    return updated
