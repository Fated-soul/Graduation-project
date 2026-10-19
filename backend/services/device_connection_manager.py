from __future__ import annotations

from typing import Any

from fastapi import WebSocket


class DeviceConnectionManager:
    """比赛原型用的内存 WebSocket 连接表。

    当前默认单进程 uvicorn 运行。后续如果部署多进程或多服务器，
    这里应替换为 Redis、MQTT Broker 或云 IoT 设备通道。
    """

    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, device_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        previous = self._connections.get(device_id)
        self._connections[device_id] = websocket
        if previous is not None and previous is not websocket:
            try:
                await previous.close(code=4000, reason="new device connection opened")
            except RuntimeError:
                pass

    def disconnect(self, device_id: str, websocket: WebSocket | None = None) -> bool:
        current = self._connections.get(device_id)
        if current is None:
            return False
        if websocket is not None and current is not websocket:
            return False
        self._connections.pop(device_id, None)
        return True

    def is_connected(self, device_id: str) -> bool:
        return device_id in self._connections

    def connected_device_ids(self) -> list[str]:
        return sorted(self._connections)

    async def send_json(self, device_id: str, payload: dict[str, Any]) -> bool:
        websocket = self._connections.get(device_id)
        if websocket is None:
            return False
        try:
            await websocket.send_json(payload)
            return True
        except RuntimeError:
            self.disconnect(device_id, websocket)
            return False


device_connection_manager = DeviceConnectionManager()
