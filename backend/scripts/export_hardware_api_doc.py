from __future__ import annotations

from backend.scripts.export_word_docs import (
    PROJECT_ROOT,
    _bullet,
    _code_block,
    _paragraph,
    _table,
    _write_docx,
)


def create_hardware_api_doc() -> None:
    title = "明察鼠毫硬件端接口文档"
    blocks = [
        _paragraph(title, "Title"),
        _paragraph(
            "本文档给 ESP32 硬件端使用，说明如何向后端上传数据、如何通过 WebSocket "
            "接收前端按钮下发的电击/爆闪/噪声控制命令，以及执行后如何回传结果。"
        ),
        _paragraph("一、地址配置", "Heading1"),
        _bullet("如果你这边使用 ngrok http 8000，硬件端访问公网 HTTPS 地址。"),
        _bullet("HTTP 接口基础地址：把 ngrok 显示的 https 地址作为 BASE_URL。"),
        _bullet("WebSocket 控制地址：把 https:// 改成 wss://，路径使用 /api/ws/devices/{device_id}。"),
        _table(
            ["配置项", "示例", "说明"],
            [
                ("BASE_URL", "https://xxxx.ngrok-free.dev", "HTTP 上传数据时使用。"),
                ("WS_URL", "wss://xxxx.ngrok-free.dev/api/ws/devices/ESP32-002", "ESP32 实时控制通道。"),
                ("SERVER_HOST", "xxxx.ngrok-free.dev", "如果库要求拆分主机，只填域名，不带 https://。"),
                ("SERVER_PORT", "443", "HTTPS/WSS 默认端口。"),
                ("DEVICE_ID", "ESP32-002", "必须和后端 devices 表中的 device_id 一致。"),
                ("MOUSE_ID", "MOUSE-002", "当前设备绑定的小鼠编号。"),
            ],
            [1800, 3300, 4260],
        ),
        _paragraph("二、硬件端需要用到的接口", "Heading1"),
        _table(
            ["用途", "方法", "路径", "硬件端是否必须"],
            [
                ("健康检查", "GET", "/api/health", "可选，用于确认后端可访问"),
                ("上传环境/设备数据", "POST", "/api/telemetry", "需要"),
                ("上传小鼠生命体征", "POST", "/api/vital-signs", "需要"),
                ("更新设备在线/电源状态", "PATCH", "/api/devices/{device_id}/status", "可选"),
                ("连接实时控制通道", "WebSocket", "/api/ws/devices/{device_id}", "需要，用于马上执行前端命令"),
                ("HTTP 回传控制结果", "POST", "/api/control-commands/{command_id}/ack", "可选，WebSocket 回传失败时使用"),
                ("直接记录刺激事件", "POST", "/api/stimulation", "一般不用；按钮控制时由回执自动记录"),
            ],
            [2100, 1200, 3800, 2260],
        ),
        _paragraph("三、上传环境/设备遥测数据", "Heading1"),
        _paragraph("接口：POST {BASE_URL}/api/telemetry"),
        _paragraph("注意：这里的 temperature 是环境温度，不是小鼠体温。小鼠体温必须上传到 /api/vital-signs 的 body_temperature。"),
        _table(
            ["字段", "类型", "必填", "说明"],
            [
                ("mouse_id", "string/null", "否", "实验鼠编号，如 MOUSE-002；设备未绑定时可不传。"),
                ("device_id", "string", "是", "来源设备编号，如 ESP32-002。"),
                ("temperature", "number/null", "否", "环境温度，单位摄氏度，允许 -50 到 100。"),
                ("humidity", "number/null", "否", "环境湿度，单位百分比，允许 0 到 100。"),
                ("is_dark", "boolean/null", "否", "是否黑暗环境，true 表示黑暗。"),
                ("voltage", "number/null", "否", "设备电压，单位 V，不能小于 0。"),
                ("current", "number/null", "否", "设备电流，单位 A，不能小于 0。"),
                ("recorded_at", "string/null", "否", "采集时间，ISO 8601；不传则用服务器时间。"),
            ],
            [1700, 1500, 900, 5260],
        ),
        _paragraph("请求示例", "Heading2"),
        _code_block(
            """
POST https://xxxx.ngrok-free.dev/api/telemetry
Content-Type: application/json

{
  "mouse_id": "MOUSE-002",
  "device_id": "ESP32-002",
  "temperature": 24.6,
  "humidity": 61.2,
  "is_dark": true,
  "voltage": 5.02,
  "current": 0.43
}
            """
        ),
        _paragraph("成功响应", "Heading2"),
        _code_block(
            """
{
  "success": true,
  "message": "telemetry stored",
  "data": {
    "id": 123,
    "mouse_id": "MOUSE-002",
    "device_id": "ESP32-002",
    "temperature": 24.6,
    "humidity": 61.2,
    "is_dark": true,
    "voltage": 5.02,
    "current": 0.43,
    "recorded_at": "2026-07-22T18:30:00+08:00",
    "created_at": "2026-07-22T18:30:00+08:00"
  }
}
            """
        ),
        _paragraph("四、上传小鼠生命体征", "Heading1"),
        _paragraph("接口：POST {BASE_URL}/api/vital-signs"),
        _paragraph("这个接口用于小鼠体温、心率、血氧。它和 /api/telemetry 可以不同频率上传。"),
        _table(
            ["字段", "类型", "必填", "说明"],
            [
                ("mouse_id", "string", "是", "实验鼠编号，如 MOUSE-002。"),
                ("device_id", "string", "是", "来源设备编号，如 ESP32-002。"),
                ("body_temperature", "number/null", "否", "小鼠体温，单位摄氏度，允许 20 到 45。"),
                ("heart_rate", "number/null", "否", "小鼠心率，单位 bpm，允许 0 到 1000。"),
                ("blood_oxygen", "number/null", "否", "小鼠血氧饱和度，单位百分比，允许 0 到 100。"),
                ("recorded_at", "string/null", "否", "采集时间，ISO 8601；不传则用服务器时间。"),
            ],
            [1800, 1500, 900, 5160],
        ),
        _paragraph("请求示例", "Heading2"),
        _code_block(
            """
POST https://xxxx.ngrok-free.dev/api/vital-signs
Content-Type: application/json

{
  "mouse_id": "MOUSE-002",
  "device_id": "ESP32-002",
  "body_temperature": 38.6,
  "heart_rate": 492,
  "blood_oxygen": 92.8
}
            """
        ),
        _paragraph("成功响应", "Heading2"),
        _code_block(
            """
{
  "success": true,
  "message": "vital signs stored",
  "data": {
    "id": 88,
    "mouse_id": "MOUSE-002",
    "device_id": "ESP32-002",
    "body_temperature": 38.6,
    "heart_rate": 492,
    "blood_oxygen": 92.8,
    "recorded_at": "2026-07-22T18:30:00+08:00",
    "created_at": "2026-07-22T18:30:00+08:00"
  }
}
            """
        ),
        _paragraph("五、连接 WebSocket 实时控制通道", "Heading1"),
        _paragraph("接口：WebSocket wss://xxxx.ngrok-free.dev/api/ws/devices/{device_id}"),
        _paragraph("示例：wss://xxxx.ngrok-free.dev/api/ws/devices/ESP32-002"),
        _paragraph("ESP32 连接成功后，后端会立即发送："),
        _code_block(
            """
{
  "type": "connected",
  "device_id": "ESP32-002",
  "message": "device websocket connected"
}
            """
        ),
        _paragraph("保持在线", "Heading2"),
        _paragraph("ESP32 可以定期发送心跳："),
        _code_block(
            """
{
  "type": "heartbeat"
}
            """
        ),
        _paragraph("后端会返回："),
        _code_block(
            """
{
  "type": "heartbeat_ack",
  "device_id": "ESP32-002"
}
            """
        ),
        _paragraph("六、ESP32 会收到的控制命令", "Heading1"),
        _paragraph("前端点击“立即电击”“立即爆闪”或“立即噪声”后，如果 ESP32 在线，后端会通过 WebSocket 立刻推送如下消息。"),
        _paragraph("电击命令："),
        _code_block(
            """
{
  "type": "control_command",
  "command_id": "后端生成的唯一命令编号",
  "mouse_id": "MOUSE-002",
  "device_id": "ESP32-002",
  "command_type": "electric_shock",
  "duration_ms": 1500,
  "intensity": null
}
            """
        ),
        _paragraph("爆闪命令："),
        _code_block(
            """
{
  "type": "control_command",
  "command_id": "后端生成的唯一命令编号",
  "mouse_id": "MOUSE-002",
  "device_id": "ESP32-002",
  "command_type": "flash",
  "duration_ms": 3000,
  "intensity": null
}
            """
        ),
        _paragraph("噪声命令："),
        _code_block(
            """
{
  "type": "control_command",
  "command_id": "后端生成的唯一命令编号",
  "mouse_id": "MOUSE-002",
  "device_id": "ESP32-002",
  "command_type": "noise",
  "duration_ms": 3000,
  "intensity": null
}
            """
        ),
        _table(
            ["字段", "说明"],
            [
                ("type", "固定为 control_command，表示这是后端下发的硬件控制命令。"),
                ("command_id", "命令唯一编号，ESP32 回传结果时必须原样带回。"),
                ("mouse_id", "本次控制对应的小鼠编号。"),
                ("device_id", "本次控制对应的 ESP32 设备编号。"),
                ("command_type", "electric_shock 表示电击，flash 表示爆闪，noise 表示噪声。"),
                ("duration_ms", "持续时间，单位毫秒。"),
                ("intensity", "刺激强度，当前可为 null，后续可用于电击强度、灯光亮度或噪声音量。"),
            ],
            [2200, 7160],
        ),
        _paragraph("七、ESP32 执行后回传结果", "Heading1"),
        _paragraph("推荐通过同一个 WebSocket 回传，成功时发送："),
        _code_block(
            """
{
  "command_id": "原样带回收到的 command_id",
  "status": "completed",
  "message": "ok"
}
            """
        ),
        _paragraph("失败时发送："),
        _code_block(
            """
{
  "command_id": "原样带回收到的 command_id",
  "status": "failed",
  "message": "说明失败原因，例如 relay timeout"
}
            """
        ),
        _paragraph("后端收到 completed 后，会自动写入 stimulation_events，前端的刺激事件表会显示这次电击、爆闪或噪声。"),
        _paragraph("如果 WebSocket 回传不方便，也可以使用 HTTP 回传：", "Heading2"),
        _code_block(
            """
POST https://xxxx.ngrok-free.dev/api/control-commands/{command_id}/ack
Content-Type: application/json

{
  "status": "completed",
  "message": "ok"
}
            """
        ),
        _paragraph("八、可选：更新设备状态", "Heading1"),
        _paragraph("接口：PATCH {BASE_URL}/api/devices/{device_id}/status"),
        _paragraph("如果 ESP32 想单独上报在线状态、电压、电流，可以调用这个接口；上传 /api/telemetry 时后端也会同步更新设备 last_seen、online、voltage、current。"),
        _code_block(
            """
PATCH https://xxxx.ngrok-free.dev/api/devices/ESP32-002/status
Content-Type: application/json

{
  "online": true,
  "voltage": 5.03,
  "current": 0.42
}
            """
        ),
        _paragraph("九、不要把这些字段传错", "Heading1"),
        _table(
            ["常见问题", "正确做法"],
            [
                ("小鼠体温传到 telemetry.temperature", "不要这样做。telemetry.temperature 是环境温度，小鼠体温用 vital-signs.body_temperature。"),
                ("心率、血氧和环境数据一个接口上传", "不要混在一起。心率、血氧、小鼠体温统一 POST /api/vital-signs。"),
                ("前端按钮控制时直接 POST /api/stimulation", "不要这样做。前端按钮控制走 /api/control-commands 和 WebSocket 回执，后端自动记录事件。"),
                ("ESP32 没连 WebSocket", "前端点击不会下发成功，会提示设备未在线。"),
                ("回执不带 command_id", "后端无法确认是哪条命令执行完成，必须原样带回 command_id。"),
            ],
            [3100, 6260],
        ),
        _paragraph("十、HTTP 状态码", "Heading1"),
        _table(
            ["状态码", "含义", "硬件端处理建议"],
            [
                ("200", "查询或更新成功", "按响应 data 读取结果。"),
                ("201", "数据写入成功", "上传成功，可以继续下一次采集。"),
                ("404", "设备或小鼠不存在", "检查 device_id、mouse_id 是否和后端数据库一致。"),
                ("409", "设备 WebSocket 未连接，控制命令未下发", "重新连接 WebSocket 后再由前端重新点击。"),
                ("422", "请求字段错误", "检查字段名、类型、数值范围。"),
                ("500", "后端或数据库异常", "稍后重试，并让后端同学检查日志。"),
            ],
            [1300, 3600, 4460],
        ),
        _paragraph("十一、硬件侧保护要求", "Heading1"),
        _bullet("ESP32 上电后，电击、爆闪和噪声 GPIO 必须默认 LOW。"),
        _bullet("ESP32 本地必须限制最大 duration_ms，建议先限制在 10000 ms 以内。"),
        _bullet("电击模块不要由 ESP32 引脚直接供电，应使用继电器、MOSFET、光耦隔离或专用刺激模块。"),
        _bullet("建议加实体急停开关，并确保断网或程序异常时输出自动关闭。"),
        _bullet("同一时间建议只执行一条刺激命令，执行期间忽略或排队新命令。"),
    ]
    output_path = _write_docx(PROJECT_ROOT / "硬件端接口文档.docx", title, blocks)
    print(output_path)


if __name__ == "__main__":
    create_hardware_api_doc()
