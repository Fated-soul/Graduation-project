from __future__ import annotations

from pathlib import Path
import sys


FRONTEND_DIR = Path(__file__).resolve().parents[1]
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

from utils.analysis_report_pdf import (
    build_analysis_report_pdf,
    build_analysis_thread_report_pdf,
)


def test_analysis_report_is_generated_as_a_nonempty_pdf() -> None:
    session = {
        "subject_code": "Ca-EEG3-4",
        "modeling_stage": "恐惧条件化造模",
        "session_started_at": "2022-09-19T21:18:41+08:00",
    }
    analysis = {
        "question": "本次会话是否支持恐惧记忆形成？",
        "summary": "刺激、冻结行为与钙活动共同提供了支持性证据。",
        "evidence": ["记录到足底电击。", "电击后冻结行为增加。"],
        "recommendation": "建议继续复核电击前后的钙活动变化。",
        "confidence": 0.82,
        "created_at": "2026-10-19T16:30:00+08:00",
        "knowledge_sources": [
            {
                "title": "DANDI 000718 官方数据说明",
                "section": "数据模态",
                "source_url": "https://dandiarchive.org/dandiset/000718",
            }
        ],
    }

    pdf = build_analysis_report_pdf(session, analysis)

    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 10_000


def test_thread_report_keeps_followups_in_the_same_pdf() -> None:
    session = {
        "subject_code": "Ca-EEG3-4",
        "modeling_stage": "恐惧条件化造模",
        "session_started_at": "2022-09-19T21:18:41+08:00",
    }
    root = {
        "id": 10,
        "question": "本次会话是否支持恐惧记忆形成？",
        "summary": "当前多模态证据提供初步支持。",
        "evidence": ["电击后冻结行为增加。"],
        "recommendation": "继续复核钙活动。",
        "confidence": 0.76,
        "created_at": "2026-10-19T16:30:00+08:00",
        "knowledge_sources": [],
    }
    follow_up = {
        "id": 11,
        "parent_analysis_id": 10,
        "question": "这一结论还有哪些局限？",
        "summary": "样本量与跨会话时间差限制了结论范围。",
        "evidence": ["不同会话并非同时采集。"],
        "recommendation": "增加同条件重复会话。",
        "confidence": 0.68,
        "created_at": "2026-10-19T16:35:00+08:00",
        "knowledge_sources": [],
    }

    single_pdf = build_analysis_report_pdf(session, root)
    thread_pdf = build_analysis_thread_report_pdf(session, [root, follow_up])

    assert thread_pdf.startswith(b"%PDF-")
    assert len(thread_pdf) > len(single_pdf)
