from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agent import config
from agent.analysis_service import build_rule_analysis
from agent.conversation_service import create_conversation, send_message
from agent.llm_client import enhance_analysis
from agent.schemas import ConversationMessageRequest, CreateConversationRequest


def _context(*, high_risk: bool = False) -> dict:
    temperature = 38.8 if high_risk else 37.2
    heart_rate = 510 if high_risk else 420
    blood_oxygen = 89 if high_risk else 98
    return {
        "mouse_id": "MOUSE-001",
        "animal": {"mouse_id": "MOUSE-001", "experiment_stage": "应激阶段"},
        "devices": [{"device_id": "ESP32-001", "online": True}],
        "vital_latest": {
            "body_temperature": temperature,
            "heart_rate": heart_rate,
            "blood_oxygen": blood_oxygen,
        },
        "vital_history": [
            {
                "body_temperature": temperature - 0.2,
                "heart_rate": heart_rate - 10,
                "blood_oxygen": blood_oxygen,
            },
            {
                "body_temperature": temperature,
                "heart_rate": heart_rate,
                "blood_oxygen": blood_oxygen,
            },
        ],
        "telemetry_history": [],
        "stimulation_history": [],
        "stimulation_settings": [],
        "vision_summary": {
            "feature_rows": 100,
            "total_movement_distance": 35.5,
            "avg_movement_distance": 0.355,
            "avg_frame_confidence": 0.9,
        },
        "vision_features": [],
    }


class RuleAnalysisTests(unittest.TestCase):
    def test_normal_vitals_produce_normal_risk(self) -> None:
        analysis = build_rule_analysis(_context())
        self.assertEqual(analysis.risk_level, "正常")
        self.assertLess(analysis.risk_score, 30)

    def test_abnormal_vitals_produce_high_risk(self) -> None:
        analysis = build_rule_analysis(_context(high_risk=True))
        self.assertEqual(analysis.risk_level, "高风险")
        self.assertGreaterEqual(analysis.risk_score, 60)
        self.assertIn("小鼠体温明显升高", analysis.factors)

    def test_conversation_uses_rule_fallback_without_api_key(self) -> None:
        conversation = create_conversation(
            CreateConversationRequest(mouse_id="MOUSE-001")
        )
        with (
            patch("agent.conversation_service.load_mouse_context", return_value=_context()),
            patch.object(config, "DASHSCOPE_API_KEY", ""),
            patch.object(config, "AGENT_ALLOW_RULE_FALLBACK", True),
        ):
            result = send_message(
                conversation["session_id"],
                ConversationMessageRequest(message="分析一下当前状态"),
            )

        self.assertIn("answer", result)
        self.assertEqual(result["analysis"]["analysis_source"], "rules")
        self.assertNotIn("规则引擎", result["answer"])
        self.assertNotIn("帧级视觉", result["answer"])

    def test_rule_explanation_uses_experiment_language(self) -> None:
        conversation = create_conversation(
            CreateConversationRequest(mouse_id="MOUSE-001")
        )
        with (
            patch("agent.conversation_service.load_mouse_context", return_value=_context()),
            patch.object(config, "DASHSCOPE_API_KEY", ""),
            patch.object(config, "AGENT_ALLOW_RULE_FALLBACK", True),
        ):
            result = send_message(
                conversation["session_id"],
                ConversationMessageRequest(message="为什么是这个状态"),
            )

        self.assertIn("从身体指标看", result["answer"])
        self.assertIn("从活动情况看", result["answer"])
        self.assertNotIn("规则引擎", result["answer"])
        self.assertNotIn("字段", result["answer"])

    def test_llm_narrative_cannot_override_rule_score(self) -> None:
        context = _context(high_risk=True)
        rule_analysis = build_rule_analysis(context)
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            '{"answer":"建议人工复核。","summary":"模型摘要",'
                            '"vital_analysis":"模型生命体征分析",'
                            '"behavior_analysis":"模型行为分析",'
                            '"stage_analysis":"模型阶段分析",'
                            '"risk_analysis":"模型风险解释",'
                            '"recommendation":"模型建议",'
                            '"control_strategy":"人工确认后执行",'
                            '"factors":["模型补充因素"]}'
                        )
                    )
                )
            ]
        )
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=lambda **_: response)
            )
        )
        with (
            patch("agent.llm_client.OpenAI", return_value=fake_client),
            patch.object(config, "DASHSCOPE_API_KEY", "test-key"),
            patch.object(config, "RAG_ENABLED", False),
        ):
            answer, enhanced = enhance_analysis(
                context=context,
                rule_analysis=rule_analysis,
                question="分析当前状态",
            )

        self.assertEqual(answer, "建议人工复核。")
        self.assertEqual(enhanced.risk_score, rule_analysis.risk_score)
        self.assertEqual(enhanced.risk_level, rule_analysis.risk_level)
        self.assertEqual(enhanced.analysis_source, "bailian_llm+rules")


if __name__ == "__main__":
    unittest.main()

