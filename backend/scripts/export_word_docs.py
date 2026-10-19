from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


PROJECT_ROOT = Path(__file__).resolve().parents[2]

NS_WORD = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _x(text: object) -> str:
    return escape(str(text), {'"': "&quot;"})


def _run(text: object, bold: bool = False, monospace: bool = False) -> str:
    font = "Consolas" if monospace else "Microsoft YaHei"
    weight = "<w:b/>" if bold else ""
    return (
        "<w:r><w:rPr>"
        f'<w:rFonts w:ascii="{font}" w:hAnsi="{font}" w:eastAsia="Microsoft YaHei"/>'
        f"{weight}</w:rPr><w:t>{_x(text)}</w:t></w:r>"
    )


def _paragraph(text: object = "", style: str | None = None, bold: bool = False, monospace: bool = False) -> str:
    style_xml = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f"<w:p>{style_xml}{_run(text, bold=bold, monospace=monospace)}</w:p>"


def _bullet(text: object) -> str:
    return (
        '<w:p><w:pPr><w:pStyle w:val="ListParagraph"/>'
        '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr>'
        f"{_run(text)}</w:p>"
    )


def _code_block(text: str) -> str:
    lines = text.strip().splitlines()
    body = "".join(_paragraph(line, monospace=True) for line in lines)
    return (
        '<w:tbl><w:tblPr><w:tblW w:w="9360" w:type="dxa"/>'
        '<w:tblBorders><w:top w:val="single" w:sz="4" w:color="DADCE0"/>'
        '<w:left w:val="single" w:sz="4" w:color="DADCE0"/>'
        '<w:bottom w:val="single" w:sz="4" w:color="DADCE0"/>'
        '<w:right w:val="single" w:sz="4" w:color="DADCE0"/>'
        '<w:insideH w:val="single" w:sz="4" w:color="DADCE0"/>'
        '<w:insideV w:val="single" w:sz="4" w:color="DADCE0"/></w:tblBorders>'
        '<w:tblCellMar><w:top w:w="120" w:type="dxa"/><w:left w:w="160" w:type="dxa"/>'
        '<w:bottom w:w="120" w:type="dxa"/><w:right w:w="160" w:type="dxa"/></w:tblCellMar></w:tblPr>'
        '<w:tblGrid><w:gridCol w:w="9360"/></w:tblGrid><w:tr>'
        '<w:tc><w:tcPr><w:tcW w:w="9360" w:type="dxa"/><w:shd w:fill="F8FAFC"/></w:tcPr>'
        f"{body}</w:tc></w:tr></w:tbl>"
    )


def _cell(text: object, width: int, header: bool = False) -> str:
    fill = '<w:shd w:fill="E8EEF5"/>' if header else ""
    bold = header
    return (
        "<w:tc><w:tcPr>"
        f'<w:tcW w:w="{width}" w:type="dxa"/>{fill}'
        '<w:vAlign w:val="center"/></w:tcPr>'
        f"{_paragraph(text, bold=bold)}</w:tc>"
    )


def _table(headers: list[str], rows: Iterable[Iterable[object]], widths: list[int]) -> str:
    grid = "".join(f'<w:gridCol w:w="{width}"/>' for width in widths)
    table_rows = ["<w:tr>" + "".join(_cell(text, widths[index], header=True) for index, text in enumerate(headers)) + "</w:tr>"]
    for row in rows:
        cells = list(row)
        table_rows.append("<w:tr>" + "".join(_cell(cells[index], widths[index]) for index in range(len(widths))) + "</w:tr>")

    return (
        '<w:tbl><w:tblPr><w:tblW w:w="9360" w:type="dxa"/>'
        '<w:tblInd w:w="120" w:type="dxa"/>'
        '<w:tblBorders><w:top w:val="single" w:sz="4" w:color="B7C4D4"/>'
        '<w:left w:val="single" w:sz="4" w:color="B7C4D4"/>'
        '<w:bottom w:val="single" w:sz="4" w:color="B7C4D4"/>'
        '<w:right w:val="single" w:sz="4" w:color="B7C4D4"/>'
        '<w:insideH w:val="single" w:sz="4" w:color="D7DEE8"/>'
        '<w:insideV w:val="single" w:sz="4" w:color="D7DEE8"/></w:tblBorders>'
        '<w:tblCellMar><w:top w:w="90" w:type="dxa"/><w:left w:w="120" w:type="dxa"/>'
        '<w:bottom w:w="90" w:type="dxa"/><w:right w:w="120" w:type="dxa"/></w:tblCellMar>'
        "</w:tblPr>"
        f"<w:tblGrid>{grid}</w:tblGrid>{''.join(table_rows)}</w:tbl>"
    )


def _styles_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="{NS_WORD}">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:pPr><w:spacing w:after="120" w:line="300" w:lineRule="auto"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:hAnsi="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/><w:sz w:val="22"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title"/>
    <w:pPr><w:spacing w:before="0" w:after="200"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:hAnsi="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/><w:b/><w:color w:val="0B2545"/><w:sz w:val="36"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr><w:spacing w:before="280" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:hAnsi="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/><w:b/><w:color w:val="2E74B5"/><w:sz w:val="30"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr><w:spacing w:before="200" w:after="100"/><w:outlineLvl w:val="1"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:hAnsi="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/><w:b/><w:color w:val="2E74B5"/><w:sz w:val="26"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="ListParagraph">
    <w:name w:val="List Paragraph"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr><w:ind w:left="540" w:hanging="260"/><w:spacing w:after="80" w:line="300" w:lineRule="auto"/></w:pPr>
  </w:style>
</w:styles>"""


def _numbering_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="{NS_WORD}">
  <w:abstractNum w:abstractNumId="0">
    <w:multiLevelType w:val="hybridMultilevel"/>
    <w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/><w:lvlJc w:val="left"/><w:pPr><w:tabs><w:tab w:val="num" w:pos="540"/></w:tabs><w:ind w:left="540" w:hanging="260"/></w:pPr></w:lvl>
  </w:abstractNum>
  <w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>
</w:numbering>"""


def _content_types_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""


def _package_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""


def _document_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
</Relationships>"""


def _core_xml(title: str) -> str:
    now = datetime.now().isoformat(timespec="seconds")
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>{_x(title)}</dc:title>
  <dc:creator>Codex</dc:creator>
  <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>"""


def _app_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Codex</Application>
</Properties>"""


def _document_xml(blocks: list[str]) -> str:
    body = "".join(blocks)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{NS_WORD}" xmlns:r="{NS_REL}">
  <w:body>
    {body}
    <w:sectPr>
      <w:pgSz w:w="12240" w:h="15840"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="708" w:footer="708" w:gutter="0"/>
      <w:cols w:space="720"/>
      <w:docGrid w:linePitch="360"/>
    </w:sectPr>
  </w:body>
</w:document>"""


def _write_docx(path: Path, title: str, blocks: list[str]) -> Path:
    target = path
    try:
        docx_file = ZipFile(target, "w", ZIP_DEFLATED)
    except PermissionError:
        target = path.with_name(f"{path.stem}（新版）{path.suffix}")
        docx_file = ZipFile(target, "w", ZIP_DEFLATED)

    with docx_file as docx:
        docx.writestr("[Content_Types].xml", _content_types_xml())
        docx.writestr("_rels/.rels", _package_rels_xml())
        docx.writestr("word/_rels/document.xml.rels", _document_rels_xml())
        docx.writestr("word/document.xml", _document_xml(blocks))
        docx.writestr("word/styles.xml", _styles_xml())
        docx.writestr("word/numbering.xml", _numbering_xml())
        docx.writestr("docProps/core.xml", _core_xml(title))
        docx.writestr("docProps/app.xml", _app_xml())
    return target


def create_api_doc() -> None:
    title = "明察鼠毫后端接口使用说明"
    rows = [
        ("GET", "/", "后端根状态", "返回 name、status、version"),
        ("GET", "/api/health", "健康检查", "返回后端状态、数据库连接状态、当前时间"),
        ("GET", "/api/animals", "实验鼠列表", "可用 status 筛选"),
        ("GET", "/api/animals/{mouse_id}", "单只实验鼠", "mouse_id 示例：MOUSE-002"),
        ("PATCH", "/api/animals/{mouse_id}/status", "更新实验鼠状态", "写入 animal_status_history"),
        ("GET", "/api/devices", "设备列表", "可用 online、device_type 筛选"),
        ("PATCH", "/api/devices/{device_id}/status", "更新设备状态", "更新 online、voltage、current、last_seen"),
        ("POST", "/api/telemetry", "写入环境/设备遥测", "只写环境温度、湿度、黑暗环境、电压、电流"),
        ("GET", "/api/telemetry/latest/{mouse_id}", "最新环境/设备遥测", "获取某只实验鼠最新一条环境/设备数据"),
        ("GET", "/api/telemetry/history/{mouse_id}", "历史环境/设备遥测", "支持 hours、limit，按 recorded_at 升序"),
        ("POST", "/api/vital-signs", "写入生命体征", "写入小鼠体温、心率、血氧；和 telemetry 不同频"),
        ("GET", "/api/vital-signs/latest/{mouse_id}", "最新生命体征", "获取某只实验鼠最新体温、心率、血氧"),
        ("GET", "/api/vital-signs/history/{mouse_id}", "历史生命体征", "支持 hours、limit，按 recorded_at 升序"),
        ("POST", "/api/stimulation", "写入刺激事件", "event_type 当前支持 electric_shock、flash、noise"),
        ("GET", "/api/stimulation/{mouse_id}", "刺激历史", "支持 event_type、hours、limit"),
        ("POST", "/api/control-commands", "下发控制命令", "前端点击电击/爆闪/噪声后调用；设备 WebSocket 在线时立即推送"),
        ("GET", "/api/control-commands", "控制命令历史", "支持 device_id、status、limit 筛选"),
        ("GET", "/api/control-commands/connections", "控制通道在线设备", "返回已连接 WebSocket 的设备编号"),
        ("POST", "/api/control-commands/{command_id}/ack", "控制命令回执", "ESP32 可通过 HTTP 回传执行完成或失败"),
        ("WebSocket", "/api/ws/devices/{device_id}", "ESP32 实时控制通道", "ESP32 连接后等待后端推送控制命令"),
    ]
    telemetry_fields = [
        ("mouse_id", "string", "否", "实验鼠编号，如 MOUSE-002"),
        ("device_id", "string", "是", "来源设备编号，如 ESP32-002"),
        ("temperature", "number", "否", "环境温度，单位 ℃。注意：这不是小鼠体温。"),
        ("humidity", "number", "否", "环境湿度，单位 %。"),
        ("is_dark", "boolean", "否", "是否为黑暗环境。"),
        ("voltage", "number", "否", "设备电压，单位 V。"),
        ("current", "number", "否", "设备电流，单位 A。"),
        ("recorded_at", "string", "否", "采集时间，ISO 8601；不传则使用服务器当前时间。"),
    ]
    vital_fields = [
        ("mouse_id", "string", "是", "实验鼠编号，如 MOUSE-002"),
        ("device_id", "string", "是", "来源设备编号，如 ESP32-002"),
        ("body_temperature", "number", "否", "小鼠体温，单位 ℃。"),
        ("heart_rate", "number", "否", "小鼠心率，单位 bpm。"),
        ("blood_oxygen", "number", "否", "小鼠血氧饱和度，单位 %。"),
        ("recorded_at", "string", "否", "采集时间，ISO 8601；不传则使用服务器当前时间。"),
    ]
    blocks = [
        _paragraph(title, "Title"),
        _paragraph("适用对象：ESP32-S3 程序、测试脚本、后续 Streamlit 前端和 Agent 调用方。"),
        _paragraph("基础地址", "Heading1"),
        _bullet("本地调试：SERVER_HOST = http://127.0.0.1，SERVER_PORT = 8000。"),
        _bullet("使用 ngrok http 8000 时：SERVER_HOST 使用 ngrok 提供的 https 地址，SERVER_PORT = 443，接口路径不变。"),
        _bullet("请求和响应均为 JSON，字段名统一使用英文 snake_case。"),
        _paragraph("核心接口", "Heading1"),
        _table(["方法", "路径", "用途", "说明"], rows, [1000, 3100, 1800, 3460]),
        _paragraph("环境/设备遥测写入字段", "Heading1"),
        _table(["字段", "类型", "必填", "中文说明"], telemetry_fields, [1700, 1200, 900, 5560]),
        _paragraph("POST /api/telemetry 示例", "Heading2"),
        _code_block(
            """
{
  "mouse_id": "MOUSE-002",
  "device_id": "ESP32-002",
  "temperature": 24.1,
  "humidity": 62.0,
  "is_dark": true,
  "voltage": 5.02,
  "current": 0.44
}
            """
        ),
        _paragraph("生命体征写入字段", "Heading1"),
        _table(["字段", "类型", "必填", "中文说明"], vital_fields, [1700, 1200, 900, 5560]),
        _paragraph("POST /api/vital-signs 示例", "Heading2"),
        _code_block(
            """
{
  "mouse_id": "MOUSE-002",
  "device_id": "ESP32-002",
  "body_temperature": 38.6,
  "heart_rate": 492,
  "blood_oxygen": 92.8
}
            """
        ),
        _paragraph("注意：/api/telemetry 不再接收 body_temperature、heart_rate、blood_oxygen；多传这些字段会返回 HTTP 422。"),
        _paragraph("刺激事件字段", "Heading1"),
        _table(
            ["字段", "类型", "必填", "中文说明"],
            [
                ("mouse_id", "string", "是", "实验鼠编号。"),
                ("device_id", "string", "是", "执行刺激的设备编号。"),
                ("event_type", "string", "是", "刺激类型：electric_shock、flash 或 noise。"),
                ("duration_ms", "integer", "是", "刺激持续时间，单位毫秒，必须大于 0。"),
                ("intensity", "number", "否", "刺激强度，预留给电压、亮度或等级。"),
                ("started_at", "string", "否", "刺激开始时间；不传则使用服务器当前时间。"),
            ],
            [1700, 1200, 900, 5560],
        ),
        _paragraph("统一返回格式", "Heading1"),
        _code_block(
            """
{
  "success": true,
  "message": "ok",
  "data": {}
}
            """
        ),
        _paragraph("错误时使用 HTTP 状态码区分原因，例如 400、404、422、500；不要把错误当作 HTTP 200 处理。"),
    ]
    return _write_docx(PROJECT_ROOT / "接口使用说明.docx", title, blocks)


def create_database_doc() -> None:
    title = "明察鼠毫数据库表字段说明（含字段解释）"
    table_map = {
        "animals：实验鼠基础信息表": [
            ("id", "BIGSERIAL", "否", "数据库内部自增主键。"),
            ("mouse_id", "VARCHAR(50)", "否", "实验鼠编号，如 MOUSE-001，唯一。"),
            ("current_status", "VARCHAR(50)", "否", "当前状态：normal、attention、high_risk、offline。"),
            ("experiment_name", "VARCHAR(100)", "是", "当前实验名称，统一为行为无助造模。"),
            ("experiment_stage", "VARCHAR(100)", "是", "当前实验阶段，如准备阶段、适应阶段、应激阶段、行为测试阶段、观察阶段。"),
            ("created_at", "TIMESTAMPTZ", "否", "记录创建时间。"),
            ("updated_at", "TIMESTAMPTZ", "否", "记录更新时间。"),
        ],
        "devices：物联网设备基础信息表": [
            ("id", "BIGSERIAL", "否", "数据库内部自增主键。"),
            ("device_id", "VARCHAR(50)", "否", "设备编号，如 ESP32-001，唯一。"),
            ("device_type", "VARCHAR(50)", "否", "设备类型，如 esp32_s3、camera、environment_sensor。"),
            ("device_name", "VARCHAR(100)", "是", "设备显示名称，如 1号实验箱 ESP32-S3。"),
            ("mouse_id", "VARCHAR(50)", "是", "当前绑定的实验鼠编号，可为空；外键关联 animals.mouse_id。"),
            ("online", "BOOLEAN", "否", "设备是否在线，数据库中使用 true/false。"),
            ("voltage", "DOUBLE PRECISION", "是", "设备当前电压，单位 V。"),
            ("current", "DOUBLE PRECISION", "是", "设备当前电流，单位 A。"),
            ("last_seen", "TIMESTAMPTZ", "是", "设备最后通信时间。"),
            ("created_at", "TIMESTAMPTZ", "否", "记录创建时间。"),
            ("updated_at", "TIMESTAMPTZ", "否", "记录更新时间。"),
        ],
        "telemetry：环境/设备遥测历史数据表": [
            ("id", "BIGSERIAL", "否", "数据库内部自增主键。"),
            ("mouse_id", "VARCHAR(50)", "是", "实验鼠编号；允许为空以兼容未绑定设备数据。"),
            ("device_id", "VARCHAR(50)", "否", "来源设备编号；外键关联 devices.device_id。"),
            ("temperature", "DOUBLE PRECISION", "是", "环境温度，单位 ℃。注意：不是小鼠体温。"),
            ("humidity", "DOUBLE PRECISION", "是", "环境湿度，单位 %。"),
            ("is_dark", "BOOLEAN", "是", "是否为黑暗环境。"),
            ("voltage", "DOUBLE PRECISION", "是", "设备电压，单位 V。"),
            ("current", "DOUBLE PRECISION", "是", "设备电流，单位 A。"),
            ("recorded_at", "TIMESTAMPTZ", "否", "设备采集时间；不传时由后端填入当前时间。"),
            ("created_at", "TIMESTAMPTZ", "否", "数据入库时间。"),
        ],
        "vital_signs：小鼠生命体征历史数据表": [
            ("id", "BIGSERIAL", "否", "数据库内部自增主键。"),
            ("mouse_id", "VARCHAR(50)", "否", "实验鼠编号；外键关联 animals.mouse_id。"),
            ("device_id", "VARCHAR(50)", "否", "来源设备编号；外键关联 devices.device_id。"),
            ("body_temperature", "DOUBLE PRECISION", "是", "小鼠体温，单位 ℃。"),
            ("heart_rate", "DOUBLE PRECISION", "是", "小鼠心率，单位 bpm。"),
            ("blood_oxygen", "DOUBLE PRECISION", "是", "小鼠血氧饱和度，单位 %。"),
            ("recorded_at", "TIMESTAMPTZ", "否", "生命体征采集时间；可与 telemetry 不同频。"),
            ("created_at", "TIMESTAMPTZ", "否", "数据入库时间。"),
        ],
        "stimulation_events：实验刺激事件表": [
            ("id", "BIGSERIAL", "否", "数据库内部自增主键。"),
            ("mouse_id", "VARCHAR(50)", "否", "实验鼠编号；外键关联 animals.mouse_id。"),
            ("device_id", "VARCHAR(50)", "否", "执行刺激的设备编号；外键关联 devices.device_id。"),
            ("event_type", "VARCHAR(50)", "否", "刺激类型：electric_shock 表示电击，flash 表示爆闪，noise 表示噪声。"),
            ("duration_ms", "INTEGER", "否", "刺激持续时间，单位毫秒。"),
            ("intensity", "DOUBLE PRECISION", "是", "刺激强度，预留给电压、亮度或等级。"),
            ("started_at", "TIMESTAMPTZ", "否", "刺激开始时间。"),
            ("ended_at", "TIMESTAMPTZ", "否", "刺激结束时间，由 started_at 与 duration_ms 计算。"),
            ("created_at", "TIMESTAMPTZ", "否", "事件入库时间。"),
        ],
        "animal_status_history：实验鼠状态历史表": [
            ("id", "BIGSERIAL", "否", "数据库内部自增主键。"),
            ("mouse_id", "VARCHAR(50)", "否", "实验鼠编号；外键关联 animals.mouse_id。"),
            ("status", "VARCHAR(50)", "否", "变化后的状态，如 normal、attention、high_risk、offline。"),
            ("reason", "TEXT", "是", "状态变化原因，如体温持续升高、Agent 风险评分超过 80。"),
            ("recorded_at", "TIMESTAMPTZ", "否", "状态变化发生时间。"),
            ("created_at", "TIMESTAMPTZ", "否", "状态历史记录入库时间。"),
        ],
        "control_commands：硬件控制命令表": [
            ("id", "BIGSERIAL", "否", "数据库内部自增主键。"),
            ("command_id", "VARCHAR(64)", "否", "控制命令唯一编号，由后端生成，ESP32 回执时原样带回。"),
            ("mouse_id", "VARCHAR(50)", "否", "本次控制对应的实验鼠编号；外键关联 animals.mouse_id。"),
            ("device_id", "VARCHAR(50)", "否", "执行命令的 ESP32 设备编号；外键关联 devices.device_id。"),
            ("command_type", "VARCHAR(50)", "否", "命令类型：electric_shock 表示电击，flash 表示爆闪，noise 表示噪声。"),
            ("duration_ms", "INTEGER", "否", "控制持续时间，单位毫秒。"),
            ("intensity", "DOUBLE PRECISION", "是", "刺激强度，预留给电击强度、爆闪亮度或噪声音量。"),
            ("status", "VARCHAR(50)", "否", "命令状态：pending、sent、completed、failed、expired。"),
            ("requested_at", "TIMESTAMPTZ", "否", "前端请求创建命令的时间。"),
            ("dispatched_at", "TIMESTAMPTZ", "是", "后端通过 WebSocket 下发命令的时间。"),
            ("acknowledged_at", "TIMESTAMPTZ", "是", "ESP32 回传执行结果的时间。"),
            ("error_message", "TEXT", "是", "命令失败原因或硬件回传的错误信息。"),
            ("created_at", "TIMESTAMPTZ", "否", "记录创建时间。"),
            ("updated_at", "TIMESTAMPTZ", "否", "记录更新时间。"),
        ],
    }
    blocks = [
        _paragraph(title, "Title"),
        _paragraph('数据库名称：IOT。连接配置位于 backend/config.py，当前本地比赛原型使用 user=postgres、password=123、host=localhost、port=5432。'),
        _paragraph("字段语义重点", "Heading1"),
        _bullet("telemetry.temperature 表示环境温度，不表示小鼠体温。"),
        _bullet("vital_signs.body_temperature 表示小鼠体温。"),
        _bullet("vital_signs.heart_rate 表示小鼠心率，vital_signs.blood_oxygen 表示小鼠血氧饱和度。"),
        _bullet("telemetry 和 vital_signs 可按不同采样频率上传，互不强制同步。"),
    ]
    for table_name, rows in table_map.items():
        blocks.append(_paragraph(table_name, "Heading1"))
        blocks.append(_table(["字段名", "SQL 类型", "允许为空", "中文解释"], rows, [1800, 2200, 900, 4460]))

    blocks.extend(
        [
            _paragraph("主要索引", "Heading1"),
            _bullet("telemetry(mouse_id)、telemetry(device_id)、telemetry(recorded_at)、telemetry(mouse_id, recorded_at)。"),
            _bullet("vital_signs(mouse_id)、vital_signs(device_id)、vital_signs(recorded_at)、vital_signs(mouse_id, recorded_at)。"),
            _bullet("stimulation_events(mouse_id)、stimulation_events(started_at)。"),
            _bullet("control_commands(device_id)、control_commands(status)、control_commands(requested_at)、control_commands(command_id)。"),
            _bullet("animal_status_history(mouse_id)、animal_status_history(recorded_at)。"),
        ]
    )
    return _write_docx(PROJECT_ROOT / "数据库表字段说明（含字段解释）.docx", title, blocks)


def main() -> None:
    api_doc = create_api_doc()
    database_doc = create_database_doc()
    print("Word docs exported:")
    print(api_doc)
    print(database_doc)


if __name__ == "__main__":
    main()
