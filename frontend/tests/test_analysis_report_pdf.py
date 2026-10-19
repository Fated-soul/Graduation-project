from __future__ import annotations

from pathlib import Path
import sys


FRONTEND_DIR = Path(__file__).resolve().parents[1]
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

from utils.analysis_report_pdf import build_analysis_report_pdf


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
