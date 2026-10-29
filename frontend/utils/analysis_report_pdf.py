from __future__ import annotations

from html import escape
from io import BytesIO
import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from utils.analysis_source import analysis_source_label

NAVY = colors.HexColor("#17364E")
TEAL = colors.HexColor("#087EAE")
TEXT = colors.HexColor("#334E63")
MUTED = colors.HexColor("#6B7F90")
LINE = colors.HexColor("#D9E4EA")
PALE_BLUE = colors.HexColor("#EEF7FA")
PALE_GREEN = colors.HexColor("#EDF8F4")


def build_analysis_report_pdf(session: dict, analysis: dict) -> bytes:
    return build_analysis_thread_report_pdf(session, [analysis])


def build_analysis_thread_report_pdf(session: dict, analyses: list[dict]) -> bytes:
    if not analyses:
        raise ValueError("analysis thread must contain at least one record")

    normal_font, bold_font = _register_fonts()
    styles = _build_styles(normal_font, bold_font)
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=19 * mm,
        leftMargin=19 * mm,
        topMargin=24 * mm,
        bottomMargin=20 * mm,
        title="实验动物多模态智能造模辅助决策报告",
        author="明察鼠毫",
        subject="Agent 辅助决策完整对话记录",
    )

    latest = analyses[-1]
    confidence = _normalise_confidence(latest.get("confidence"))
    confidence_text = f"{confidence:.0%}" if confidence is not None else "未评定"
    story = [
        Paragraph("实验动物多模态智能造模辅助决策报告", styles["title"]),
        Spacer(1, 2 * mm),
        Paragraph("COMPLETE AGENT DECISION DIALOGUE", styles["subtitle"]),
        Spacer(1, 5 * mm),
        HRFlowable(width="100%", thickness=1.2, color=TEAL),
        Spacer(1, 5 * mm),
        _metadata_table(
            session,
            latest,
            len(analyses),
            confidence_text,
            styles,
        ),
        Spacer(1, 3 * mm),
        Paragraph(
            "报告说明：本报告汇集各轮问题与答复，并分别注明模型分析、本地评估或未记录的来源。"
            "参考资料以各轮实际记录为准；报告用于辅助复核，不替代专业研究判断。",
            styles["note"],
        ),
        Spacer(1, 6 * mm),
        _section_heading("完整辅助决策对话", styles),
    ]

    for index, analysis in enumerate(analyses):
        if index:
            story.extend(
                [
                    Spacer(1, 5 * mm),
                    HRFlowable(width="100%", thickness=0.7, color=LINE),
                    Spacer(1, 5 * mm),
                ]
            )
        story.extend(_analysis_exchange_story(index, analysis, styles))

    def draw_page(canvas, doc) -> None:
        canvas.saveState()
        width, height = A4
        canvas.setFont(normal_font, 8.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(19 * mm, height - 13 * mm, "明察鼠毫 · 多模态智能造模")
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.5)
        canvas.line(19 * mm, height - 15 * mm, width - 19 * mm, height - 15 * mm)
        canvas.line(19 * mm, 14 * mm, width - 19 * mm, 14 * mm)
        canvas.drawString(19 * mm, 9 * mm, "Agent 辅助决策完整对话报告")
        canvas.drawRightString(width - 19 * mm, 9 * mm, f"第 {doc.page} 页")
        canvas.restoreState()

    document.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    return buffer.getvalue()


def _analysis_exchange_story(
    index: int,
    analysis: dict,
    styles: dict[str, ParagraphStyle],
) -> list:
    confidence = _normalise_confidence(analysis.get("confidence"))
    confidence_text = f"{confidence:.0%}" if confidence is not None else "未评定"
    question_label = "初始问题" if index == 0 else f"第 {index} 次追问"
    source_label, source_description = analysis_source_label(analysis)
    answer_label = source_label if index == 0 else f"{source_label} · 第 {index} 次追问答复"
    story = [
        Paragraph(f"{index + 1:02d}  {question_label}", styles["exchange_title"]),
        _content_box(
            analysis.get("question") or "未记录问题",
            styles["question"],
            PALE_BLUE,
        ),
        Spacer(1, 4 * mm),
        Paragraph(_text(answer_label), styles["exchange_title"]),
        Paragraph(_text(source_description), styles["answer_meta"]),
        Paragraph(
            _text(
                f"形成时间：{_format_datetime(analysis.get('created_at'))}    "
                f"证据充分度：{confidence_text}"
            ),
            styles["answer_meta"],
        ),
        Spacer(1, 2.5 * mm),
        Paragraph(
            _paragraph_text(analysis.get("summary") or "本次分析未返回可显示的结论。"),
            styles["body"],
        ),
        Spacer(1, 3.5 * mm),
        Paragraph("判断依据", styles["subsection"]),
    ]

    evidence = analysis.get("evidence") or []
    if evidence:
        story.append(_bullet_list(evidence, styles))
    else:
        story.append(Paragraph("本轮回答未附带独立判断依据。", styles["muted"]))

    story.extend(
        [
            Spacer(1, 3.5 * mm),
            Paragraph("后续建议", styles["subsection"]),
            _content_box(
                analysis.get("recommendation") or "暂无进一步建议。",
                styles["body"],
                PALE_GREEN,
            ),
            Spacer(1, 3.5 * mm),
            Paragraph("参考资料", styles["subsection"]),
        ]
    )
    sources = analysis.get("knowledge_sources") or []
    if sources:
        story.append(_source_list(sources, styles))
    else:
        story.append(Paragraph("本轮回答未引用外部研究资料。", styles["muted"]))
    return story


def _register_fonts() -> tuple[str, str]:
    normal_name = "MCRH-Normal"
    bold_name = "MCRH-Bold"
    if normal_name in pdfmetrics.getRegisteredFontNames():
        return normal_name, bold_name

    normal_path, bold_path = _find_font_files()
    if normal_path:
        try:
            pdfmetrics.registerFont(TTFont(normal_name, str(normal_path)))
            pdfmetrics.registerFont(TTFont(bold_name, str(bold_path or normal_path)))
            pdfmetrics.registerFontFamily(
                "MCRH",
                normal=normal_name,
                bold=bold_name,
                italic=normal_name,
                boldItalic=bold_name,
            )
            return normal_name, bold_name
        except Exception:
            pass

    fallback_name = "STSong-Light"
    if fallback_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(fallback_name))
    return fallback_name, fallback_name


def _find_font_files() -> tuple[Path | None, Path | None]:
    custom = os.getenv("AGENT_REPORT_FONT")
    custom_bold = os.getenv("AGENT_REPORT_FONT_BOLD")
    if custom and Path(custom).is_file():
        return Path(custom), Path(custom_bold) if custom_bold and Path(custom_bold).is_file() else None

    candidates = (
        (Path("C:/Windows/Fonts/Deng.ttf"), Path("C:/Windows/Fonts/Dengb.ttf")),
        (Path("C:/Windows/Fonts/simhei.ttf"), Path("C:/Windows/Fonts/simhei.ttf")),
        (
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
        ),
        (
            Path("/System/Library/Fonts/PingFang.ttc"),
            Path("/System/Library/Fonts/PingFang.ttc"),
        ),
    )
    for normal, bold in candidates:
        if normal.is_file():
            return normal, bold if bold.is_file() else None
    return None, None


def _build_styles(normal_font: str, bold_font: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontName=bold_font,
            fontSize=22,
            leading=30,
            textColor=NAVY,
            alignment=TA_CENTER,
            spaceAfter=0,
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle",
            parent=base["Normal"],
            fontName=normal_font,
            fontSize=8.5,
            leading=12,
            textColor=MUTED,
            alignment=TA_CENTER,
            tracking=1.2,
        ),
        "section": ParagraphStyle(
            "SectionHeading",
            parent=base["Heading2"],
            fontName=bold_font,
            fontSize=12.5,
            leading=18,
            textColor=NAVY,
            spaceBefore=0,
            spaceAfter=3 * mm,
        ),
        "exchange_title": ParagraphStyle(
            "ExchangeTitle",
            parent=base["Heading3"],
            fontName=bold_font,
            fontSize=11.5,
            leading=17,
            textColor=TEAL,
            spaceBefore=0,
            spaceAfter=2.5 * mm,
        ),
        "subsection": ParagraphStyle(
            "Subsection",
            parent=base["Heading4"],
            fontName=bold_font,
            fontSize=10.5,
            leading=16,
            textColor=NAVY,
            spaceBefore=0,
            spaceAfter=2 * mm,
        ),
        "answer_meta": ParagraphStyle(
            "AnswerMeta",
            parent=base["Normal"],
            fontName=normal_font,
            fontSize=8.5,
            leading=13,
            textColor=MUTED,
            wordWrap="CJK",
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName=normal_font,
            fontSize=10.5,
            leading=18,
            textColor=TEXT,
            alignment=TA_LEFT,
            wordWrap="CJK",
        ),
        "question": ParagraphStyle(
            "Question",
            parent=base["BodyText"],
            fontName=bold_font,
            fontSize=11,
            leading=18,
            textColor=NAVY,
            wordWrap="CJK",
        ),
        "meta_label": ParagraphStyle(
            "MetaLabel",
            parent=base["Normal"],
            fontName=normal_font,
            fontSize=8,
            leading=11,
            textColor=MUTED,
        ),
        "meta_value": ParagraphStyle(
            "MetaValue",
            parent=base["Normal"],
            fontName=bold_font,
            fontSize=10.5,
            leading=15,
            textColor=NAVY,
            wordWrap="CJK",
        ),
        "muted": ParagraphStyle(
            "Muted",
            parent=base["BodyText"],
            fontName=normal_font,
            fontSize=9.5,
            leading=16,
            textColor=MUTED,
            wordWrap="CJK",
        ),
        "note": ParagraphStyle(
            "Note",
            parent=base["BodyText"],
            fontName=normal_font,
            fontSize=8.3,
            leading=13,
            textColor=MUTED,
            wordWrap="CJK",
        ),
    }


def _metadata_table(
    session: dict,
    latest: dict,
    turn_count: int,
    confidence_text: str,
    styles: dict[str, ParagraphStyle],
) -> Table:
    fields = (
        ("实验动物", session.get("subject_code") or "未记录"),
        ("研究阶段", session.get("modeling_stage") or "未分类"),
        ("会话时间", _format_datetime(session.get("session_started_at"))),
        ("报告形成", _format_datetime(latest.get("created_at"))),
        ("最新充分度", confidence_text),
        ("对话轮次", f"{turn_count} 轮"),
    )
    cells = []
    for start in range(0, len(fields), 3):
        cells.append(
            [
                [
                    Paragraph(_text(label), styles["meta_label"]),
                    Spacer(1, 1.2 * mm),
                    Paragraph(_text(value), styles["meta_value"]),
                ]
                for label, value in fields[start : start + 3]
            ]
        )
    table = Table(cells, colWidths=[56 * mm] * 3, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.7, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 3.5 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5 * mm),
            ]
        )
    )
    return table


def _section_heading(value: str, styles: dict[str, ParagraphStyle]) -> Paragraph:
    return Paragraph(_text(value), styles["section"])


def _content_box(
    value: str,
    style: ParagraphStyle,
    background: colors.Color,
) -> Table:
    table = Table([[Paragraph(_paragraph_text(value), style)]], colWidths=[168 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("BOX", (0, 0), (-1, -1), 0.7, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
            ]
        )
    )
    return table


def _bullet_list(items: list, styles: dict[str, ParagraphStyle]) -> ListFlowable:
    return ListFlowable(
        [
            ListItem(
                Paragraph(_paragraph_text(item), styles["body"]),
                leftIndent=5 * mm,
            )
            for item in items
        ],
        bulletType="bullet",
        start="circle",
        leftIndent=5 * mm,
        bulletFontName=styles["body"].fontName,
        bulletFontSize=7,
        bulletColor=TEAL,
        spaceAfter=1.5 * mm,
    )


def _source_list(sources: list[dict], styles: dict[str, ParagraphStyle]) -> ListFlowable:
    entries = []
    for source in sources:
        title = str(source.get("title") or "研究资料")
        section = str(source.get("section") or "").strip()
        label = f"{title} · {section}" if section else title
        url = str(source.get("source_url") or "").strip()
        content = _text(label)
        if url.startswith(("https://", "http://")):
            content = f'<link href="{escape(url, quote=True)}" color="#087EAE">{content}</link>'
        entries.append(
            ListItem(
                Paragraph(content, styles["body"]),
                leftIndent=6 * mm,
            )
        )
    return ListFlowable(
        entries,
        bulletType="1",
        leftIndent=6 * mm,
        bulletFontName=styles["body"].fontName,
        bulletFontSize=9,
        bulletColor=TEAL,
    )


def _normalise_confidence(value: object) -> float | None:
    if value is None:
        return None
    confidence = float(value)
    if confidence > 1:
        confidence /= 100
    return min(1.0, max(0.0, confidence))


def _format_datetime(value: object) -> str:
    if not value:
        return "未记录"
    return str(value).replace("T", " ")[:19]


def _text(value: object) -> str:
    return escape(str(value or "").strip())


def _paragraph_text(value: object) -> str:
    return _text(value).replace("\n", "<br/>")
