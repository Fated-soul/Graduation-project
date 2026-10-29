from __future__ import annotations


def analysis_source_label(analysis: dict) -> tuple[str, str]:
    source = str(analysis.get("analysis_source") or "")
    if source in {"multimodal_modeling_evidence", "evidence_rules", "rule_fallback"}:
        return (
            "本地证据评估",
            "本轮为本地基础评估，未使用云端模型或知识库资料，不替代实验人员判断。",
        )
    if source.startswith("bailian") or analysis.get("model_name"):
        if analysis.get("knowledge_sources"):
            return "Agent 辅助结论", "基于当前会话多模态证据与检索到的研究资料形成。"
        return "Agent 辅助结论", "基于当前会话多模态证据形成，本轮未引用外部研究资料。"
    return "历史评估结论", "本轮未记录完整的生成来源，请结合原始证据复核。"
