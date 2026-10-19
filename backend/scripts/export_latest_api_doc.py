from __future__ import annotations

from datetime import datetime

from backend.scripts.export_word_docs import (
    PROJECT_ROOT,
    _bullet,
    _code_block,
    _paragraph,
    _table,
    _write_docx,
)


def _section(blocks: list[str], title: str) -> None:
    blocks.append(_paragraph(title, "Heading1"))


def _subsection(blocks: list[str], title: str) -> None:
    blocks.append(_paragraph(title, "Heading2"))


def create_latest_api_doc() -> None:
    title = "明察鼠毫最新接口文档"
    output_path = PROJECT_ROOT / "明察鼠毫_最新接口文档.docx"
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    endpoint_rows = [
        ("GET", "/", "后端根状态", "无", "返回服务名称、运行状态、版本。"),
        ("GET", "/api/health", "健康检查", "无", "返回后端状态、数据库连接状态、当前时间。"),
        ("GET", "/api/camera/info", "摄像头配置", "无", "返回后端摄像头代理地址和源地址。"),
        ("GET", "/api/camera/stream", "摄像头视频流", "无", "返回 MJPEG 视频流。"),
        ("GET", "/api/animals", "实验鼠列表", "status", "status 可筛选 normal、attention、high_risk、offline。"),
        ("GET", "/api/animals/{mouse_id}", "实验鼠详情", "无", "按 mouse_id 查询单只实验鼠。"),
        ("POST", "/api/animals", "创建实验鼠", "JSON", "造模类型只允许“行为无助造模”。"),
        ("PATCH", "/api/animals/{mouse_id}/status", "更新实验鼠状态", "JSON", "同时写入 animal_status_history。"),
        ("GET", "/api/animals/{mouse_id}/status-history", "状态历史", "limit", "查询某只实验鼠状态变化历史。"),
        ("GET", "/api/devices", "设备列表", "online、device_type", "支持按在线状态和设备类型筛选。"),
        ("GET", "/api/devices/{device_id}", "设备详情", "无", "按 device_id 查询单台设备。"),
        ("POST", "/api/devices", "创建设备", "JSON", "可绑定 mouse_id，也可先不绑定。"),
        ("PATCH", "/api/devices/{device_id}/status", "更新设备状态", "JSON", "更新在线状态、电压、电流、last_seen。"),
        ("POST", "/api/telemetry", "写入环境/设备遥测", "JSON", "环境温度、湿度、黑暗环境、电压、电流。"),
        ("GET", "/api/telemetry/latest/{mouse_id}", "最新环境/设备遥测", "无", "查询某只实验鼠最新环境/设备数据。"),
        ("GET", "/api/telemetry/history/{mouse_id}", "历史环境/设备遥测", "hours、limit", "按 recorded_at 升序返回，方便前端画图。"),
        ("GET", "/api/telemetry/device/{device_id}", "设备遥测历史", "hours、limit", "按设备编号查询历史遥测。"),
        ("POST", "/api/vital-signs", "写入生命体征", "JSON", "小鼠体温、心率、血氧。"),
        ("GET", "/api/vital-signs/latest/{mouse_id}", "最新生命体征", "无", "查询某只实验鼠最新体温、心率、血氧。"),
        ("GET", "/api/vital-signs/history/{mouse_id}", "历史生命体征", "hours、limit", "按 recorded_at 升序返回。"),
        ("GET", "/api/vital-signs/device/{device_id}", "设备生命体征历史", "hours、limit", "按设备编号查询历史生命体征。"),
        ("POST", "/api/stimulation", "写入刺激事件", "JSON", "支持 electric_shock、flash、noise。"),
        ("PATCH", "/api/stimulation", "写入刺激事件", "JSON", "兼容 ESP32 端 PATCH 上传。"),
        ("GET", "/api/stimulation/{mouse_id}", "刺激历史", "event_type、hours、limit", "查询电击、爆闪、噪声历史。"),
        ("GET", "/api/stimulation/settings/{device_id}", "读取刺激设置", "无", "读取某台设备三种刺激的随机触发设置。"),
        ("PUT", "/api/stimulation/settings", "保存并下发刺激设置", "JSON", "保存设置，并尝试通过 WebSocket 推送到 ESP32。"),
        ("POST", "/api/control-commands", "立即下发控制命令", "JSON", "前端按钮无视倒计时立即执行某项刺激。"),
        ("GET", "/api/control-commands", "控制命令历史", "device_id、status、limit", "查询控制命令下发和执行状态。"),
        ("GET", "/api/control-commands/connections", "在线 WebSocket 设备", "无", "返回当前已连接控制通道的设备编号。"),
        ("GET", "/api/control-commands/{command_id}", "控制命令详情", "无", "按命令编号查询。"),
        ("POST", "/api/control-commands/{command_id}/ack", "控制命令 HTTP 回执", "JSON", "ESP32 可用 HTTP 方式回传 completed/failed。"),
        ("WebSocket", "/api/ws/devices/{device_id}", "ESP32 实时控制通道", "WebSocket", "后端通过该通道推送控制命令和刺激设置。"),
    ]

    blocks: list[str] = [
        _paragraph(title, "Title"),
        _paragraph(f"生成时间：{generated_at}"),
        _paragraph("用途：给前端、ESP32、测试脚本和后续 Agent 调用接口时使用。本文档只说明当前可调用接口和字段，不包含数据库建表细节。"),
    ]

    _section(blocks, "1. 基础约定")
    blocks.extend(
        [
            _bullet("本地基础地址：http://127.0.0.1:8000"),
            _bullet("ngrok http 8000 暴露后：使用 ngrok 提供的 https 地址作为基础地址；HTTPS/WSS 默认端口为 443。"),
            _bullet("所有普通接口均使用 JSON 请求和 JSON 响应，字段名为英文 snake_case。"),
            _bullet("统一响应结构：success、message、data。错误使用 HTTP 400、404、409、422、500 等状态码，不要把错误当作 HTTP 200 处理。"),
            _bullet("造模类型目前只保留：行为无助造模。"),
            _bullet("telemetry.temperature 是环境温度；小鼠体温使用 vital_signs.body_temperature。"),
        ]
    )

    _subsection(blocks, "统一成功响应示例")
    blocks.append(
        _code_block(
            """
{
  "success": true,
  "message": "ok",
  "data": {}
}
            """
        )
    )

    _section(blocks, "2. 接口总览")
    blocks.append(_table(["方法", "路径", "用途", "参数", "说明"], endpoint_rows, [900, 3000, 1700, 1500, 2260]))

    _section(blocks, "3. 实验鼠接口")
    blocks.append(
        _table(
            ["接口", "请求字段", "说明"],
            [
                ("POST /api/animals", "mouse_id、current_status、experiment_name、experiment_stage", "experiment_name 只允许 行为无助造模；experiment_stage 可为准备阶段、适应阶段、应激阶段、行为测试阶段、观察阶段、完成。"),
                ("PATCH /api/animals/{mouse_id}/status", "status、reason", "status 可为 normal、attention、high_risk、offline；更新后自动写入状态历史。"),
                ("GET /api/animals", "status 可选", "不传 status 返回全部实验鼠。"),
            ],
            [2500, 3300, 3560],
        )
    )
    _subsection(blocks, "创建实验鼠示例")
    blocks.append(
        _code_block(
            """
POST /api/animals

{
  "mouse_id": "MOUSE-001",
  "current_status": "normal",
  "experiment_name": "行为无助造模",
  "experiment_stage": "准备阶段"
}
            """
        )
    )

    _section(blocks, "4. 设备接口")
    blocks.append(
        _table(
            ["接口", "请求字段", "说明"],
            [
                ("POST /api/devices", "device_id、device_type、device_name、mouse_id、online、voltage、current、last_seen", "mouse_id 可为空；online 为 boolean。"),
                ("PATCH /api/devices/{device_id}/status", "online、voltage、current、last_seen", "至少传一个字段；设备上传数据时也会同步 last_seen。"),
                ("GET /api/devices", "online、device_type 可选", "online 示例：true；device_type 示例：esp32_s3。"),
            ],
            [2600, 3300, 3460],
        )
    )

    _section(blocks, "5. 环境/设备遥测接口")
    blocks.append(
        _table(
            ["字段", "类型", "必填", "说明"],
            [
                ("mouse_id", "string/null", "否", "实验鼠编号，设备未绑定时可为空。"),
                ("device_id", "string", "是", "来源设备编号，如 ESP32-001。"),
                ("temperature", "number/null", "否", "环境温度，单位摄氏度；范围 -50 到 100。"),
                ("humidity", "number/null", "否", "环境湿度，单位百分比；范围 0 到 100。"),
                ("is_dark", "boolean/null", "否", "是否黑暗环境。"),
                ("voltage", "number/null", "否", "设备电压，单位 V，不能小于 0。"),
                ("current", "number/null", "否", "设备电流，单位 A，不能小于 0。"),
                ("recorded_at", "string/null", "否", "采集时间，ISO 8601；不传用服务器时间。"),
            ],
            [1700, 1300, 900, 5460],
        )
    )
    _subsection(blocks, "POST /api/telemetry 示例")
    blocks.append(
        _code_block(
            """
{
  "mouse_id": "MOUSE-001",
  "device_id": "ESP32-001",
  "temperature": 24.3,
  "humidity": 58.5,
  "is_dark": false,
  "voltage": 5.02,
  "current": 0.43
}
            """
        )
    )

    _section(blocks, "6. 生命体征接口")
    blocks.append(
        _table(
            ["字段", "类型", "必填", "说明"],
            [
                ("mouse_id", "string", "是", "实验鼠编号。"),
                ("device_id", "string", "是", "来源设备编号。"),
                ("body_temperature", "number/null", "否", "小鼠体温，单位摄氏度；范围 20 到 45。"),
                ("heart_rate", "number/null", "否", "小鼠心率，单位 bpm；范围 0 到 1000。"),
                ("blood_oxygen", "number/null", "否", "小鼠血氧饱和度，单位百分比；范围 0 到 100。"),
                ("recorded_at", "string/null", "否", "采集时间，ISO 8601；不传用服务器时间。"),
            ],
            [1900, 1300, 900, 5260],
        )
    )
    blocks.append(_paragraph("body_temperature、heart_rate、blood_oxygen 至少要传一个。"))
    _subsection(blocks, "POST /api/vital-signs 示例")
    blocks.append(
        _code_block(
            """
{
  "mouse_id": "MOUSE-001",
  "device_id": "ESP32-001",
  "body_temperature": 37.8,
  "heart_rate": 438,
  "blood_oxygen": 97.2
}
            """
        )
    )

    _section(blocks, "7. 刺激事件接口")
    blocks.append(
        _table(
            ["字段", "类型", "必填", "说明"],
            [
                ("mouse_id", "string", "是", "实验鼠编号。"),
                ("device_id", "string", "是", "执行刺激的设备编号。"),
                ("event_type", "string", "是", "electric_shock、flash、noise。"),
                ("duration_ms", "integer", "是", "刺激持续时间，单位毫秒，必须大于 0。"),
                ("intensity", "number/null", "否", "刺激强度，预留字段。"),
                ("is_active", "boolean", "否", "上传这一刻是否正在刺激；默认 true。"),
                ("next_interval_ms", "integer/null", "否", "从请求到达后端开始，距离下一次自动刺激还有多少毫秒。"),
                ("next_delay_ms", "integer/null", "否", "next_interval_ms 的兼容别名。"),
                ("next_trigger_after_ms", "integer/null", "否", "next_interval_ms 的兼容别名。"),
                ("started_at", "string/null", "否", "刺激开始时间；不传则使用服务器当前时间。"),
            ],
            [1900, 1300, 900, 5260],
        )
    )
    blocks.append(_paragraph("后端会根据 started_at + duration_ms 计算 ended_at；根据请求到达时间 + next_interval_ms 计算 next_trigger_at。前端倒计时使用 ended_at 和 next_trigger_at 自动计算，ESP32 不需要每秒上传剩余秒数。"))
    _subsection(blocks, "POST 或 PATCH /api/stimulation 示例")
    blocks.append(
        _code_block(
            """
{
  "mouse_id": "MOUSE-001",
  "device_id": "ESP32-001",
  "event_type": "flash",
  "duration_ms": 4202,
  "is_active": true,
  "next_interval_ms": 30000
}
            """
        )
    )

    _section(blocks, "8. 刺激自动触发设置接口")
    blocks.append(
        _table(
            ["字段", "类型", "必填", "说明"],
            [
                ("mouse_id", "string/null", "否", "当前绑定实验鼠编号。"),
                ("device_id", "string", "是", "目标 ESP32 设备编号。"),
                ("event_type", "string", "是", "electric_shock、flash、noise。"),
                ("enabled", "boolean", "否", "是否启用自动随机触发，默认 true。"),
                ("min_interval_ms", "integer", "是", "最小触发间隔，单位毫秒，不能小于 0。"),
                ("max_interval_ms", "integer", "是", "最大触发间隔，单位毫秒，必须大于等于 min_interval_ms。"),
                ("min_duration_ms", "integer", "是", "最小刺激时间，单位毫秒，必须大于 0。"),
                ("max_duration_ms", "integer", "是", "最大刺激时间，单位毫秒，必须大于等于 min_duration_ms。"),
            ],
            [1900, 1300, 900, 5260],
        )
    )
    _subsection(blocks, "PUT /api/stimulation/settings 示例")
    blocks.append(
        _code_block(
            """
{
  "mouse_id": "MOUSE-001",
  "device_id": "ESP32-001",
  "event_type": "flash",
  "enabled": true,
  "min_interval_ms": 30000,
  "max_interval_ms": 60000,
  "min_duration_ms": 1000,
  "max_duration_ms": 5000
}
            """
        )
    )
    blocks.append(_paragraph("保存成功后，后端会尝试通过 WebSocket 向 ESP32 推送 type=stimulation_settings。响应 data.delivered 表示本次是否已实时送达设备。"))
    _subsection(blocks, "ESP32 收到的 stimulation_settings 消息")
    blocks.append(
        _code_block(
            """
{
  "type": "stimulation_settings",
  "mouse_id": "MOUSE-001",
  "device_id": "ESP32-001",
  "event_type": "flash",
  "enabled": true,
  "min_interval_ms": 30000,
  "max_interval_ms": 60000,
  "min_duration_ms": 1000,
  "max_duration_ms": 5000
}
            """
        )
    )

    _section(blocks, "9. 手动立即刺激控制接口")
    blocks.append(
        _table(
            ["字段", "类型", "必填", "说明"],
            [
                ("mouse_id", "string", "是", "实验鼠编号。"),
                ("device_id", "string", "是", "目标 ESP32 设备编号。"),
                ("command_type", "string", "是", "electric_shock、flash、noise。"),
                ("duration_ms", "integer", "是", "执行持续时间，单位毫秒，范围 1 到 60000。"),
                ("intensity", "number/null", "否", "刺激强度，预留字段。"),
            ],
            [1900, 1300, 900, 5260],
        )
    )
    blocks.append(_paragraph("前端“立即执行”按钮调用 POST /api/control-commands。该接口用于无视倒计时马上执行某项刺激。"))
    _subsection(blocks, "POST /api/control-commands 示例")
    blocks.append(
        _code_block(
            """
{
  "mouse_id": "MOUSE-001",
  "device_id": "ESP32-001",
  "command_type": "noise",
  "duration_ms": 3000
}
            """
        )
    )
    _subsection(blocks, "ESP32 收到的 control_command 消息")
    blocks.append(
        _code_block(
            """
{
  "type": "control_command",
  "command_id": "后端生成的唯一编号",
  "mouse_id": "MOUSE-001",
  "device_id": "ESP32-001",
  "command_type": "noise",
  "duration_ms": 3000,
  "intensity": null
}
            """
        )
    )
    _subsection(blocks, "ESP32 WebSocket 回执")
    blocks.append(
        _code_block(
            """
{
  "command_id": "原样带回收到的 command_id",
  "status": "completed",
  "message": "noise ok"
}
            """
        )
    )
    blocks.append(_paragraph("后端收到 completed 后，会自动写入 stimulation_events，前端刺激历史会显示该事件。"))

    _section(blocks, "10. 查询参数速查")
    blocks.append(
        _table(
            ["接口", "参数", "默认值", "说明"],
            [
                ("/api/telemetry/history/{mouse_id}", "hours", "1", "查询最近多少小时，范围 1 到 168。"),
                ("/api/telemetry/history/{mouse_id}", "limit", "500", "最大返回条数。"),
                ("/api/vital-signs/history/{mouse_id}", "hours", "1", "查询最近多少小时，范围 1 到 168。"),
                ("/api/vital-signs/history/{mouse_id}", "limit", "500", "最大返回条数。"),
                ("/api/stimulation/{mouse_id}", "event_type", "空", "可筛选 electric_shock、flash、noise。"),
                ("/api/stimulation/{mouse_id}", "hours", "24", "查询最近多少小时，范围 1 到 168。"),
                ("/api/stimulation/{mouse_id}", "limit", "100", "最大返回条数。"),
                ("/api/control-commands", "status", "空", "可筛选 pending、sent、completed、failed、expired。"),
                ("/api/control-commands", "device_id", "空", "按设备筛选命令。"),
            ],
            [3300, 1700, 1100, 3260],
        )
    )

    _section(blocks, "11. 状态码")
    blocks.append(
        _table(
            ["状态码", "含义", "处理建议"],
            [
                ("200", "查询、更新或设置保存成功", "读取 data。"),
                ("201", "创建或写入成功", "上传成功，可继续下一次。"),
                ("404", "资源不存在", "检查 mouse_id、device_id、command_id。"),
                ("409", "设备 WebSocket 未在线，控制命令未下发", "让 ESP32 先连上 /api/ws/devices/{device_id}。"),
                ("422", "请求字段校验失败", "检查字段名、类型、取值范围和必填字段。"),
                ("500", "后端或数据库异常", "查看后端日志和 PostgreSQL 状态。"),
            ],
            [1000, 3600, 4760],
        )
    )

    docx_path = _write_docx(output_path, title, blocks)
    print(docx_path)


if __name__ == "__main__":
    create_latest_api_doc()
