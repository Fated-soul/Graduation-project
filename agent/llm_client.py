from __future__ import annotations

import json
import re
from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from agent import config
from agent.analysis_service import compact_context
from agent.dataset_evidence import compact_dataset_context
from agent.rag_service import format_retrieved_context, retrieve_knowledge
from agent.schemas import AnalysisResult


class LLMConfigurationError(RuntimeError):
    pass


class LLMRequestError(RuntimeError):
    pass


SYSTEM_PROMPT = """
你是“明察鼠毫”实验动物多模态智能造模与 Agent 辅助决策系统的实验决策助手。

要求：
1. 只能依据系统提供的实验数据和检索到的研究资料作答，不得补造缺失数据。
2. 风险评分与风险等级必须沿用系统给出的结果，不得自行修改。
3. 清楚区分小鼠体温与环境温度。
4. 参数建议只是候选方案，必须明确说明需要实验人员确认，不能声称已经控制硬件。
5. 你面对的是实验人员，不是软件工程师。先直接说明小鼠目前怎么样，再用自然、易懂的实验语言解释原因和建议。
6. 不要在 answer 或其他展示文本中提及规则引擎、数据库、接口、字段、JSON、算法、阈值命中、上下文载荷等软件实现词语；不要输出代码式英文变量名。
7. 除非用户明确要求详细报告，answer 控制在 150 至 300 字，使用两到四个短段落，避免堆砌术语和重复数字。
8. 对缺少的数据直说“目前没有足够数据”，不要用技术性表述；不作临床诊断。
9. 严格区分当前动物的实验观察与公开研究资料。使用资料解释时在句末标注[资料1]等编号；没有检索资料时不要伪造引用。
10. 只返回一个 JSON 对象，不要使用 Markdown 代码块。这只是返回格式，回答正文中不要谈论 JSON。

JSON 字段：
answer, summary, vital_analysis, behavior_analysis, stage_analysis,
risk_analysis, recommendation, control_strategy, factors。
其中 factors 必须是字符串数组，其他字段必须是字符串。
""".strip()


DATASET_SYSTEM_PROMPT = """
你是“实验动物多模态智能造模与 Agent 辅助决策系统”的证据分析助手。输入来自 DANDI
000718 的一个实验会话，可能包含恐惧条件化刺激、冻结行为、运动、单光子钙成像、EEG、
EMG、睡眠状态和人工复核记录。请结合当前研究阶段判断造模反应与证据一致性：条件化阶段
重点比较电击前后的冻结行为和钙活动；回忆阶段重点观察无电击条件下的冻结反应；离线阶段
重点关注睡眠状态及 EEG、EMG 与钙活动的同步证据。只能依据提供的记录作答，缺少数据时
直接说明，不补造结论，不把相关性表述为因果关系，也不作临床诊断。跨 FC 与 Offline
会话比较时，必须使用“会话开始时间 + 会话内时间”得到的绝对采集时间；不得把两个会话
各自的第 N 秒直接视为同一时刻。若绝对时间不重叠，只能比较先后顺序、间隔和会话级汇总，
不能声称电刺激与离线 EEG、EMG 发生逐秒同步。回答面向实验人员，
使用自然中文，不讨论接口、字段、数据库或程序实现。检索资料只用于解释证据意义，不得用
群体研究结论补造当前动物的数据；引用资料时使用[资料1]等编号。返回一个 JSON 对象，包含 summary、
evidence、recommendation、confidence 四项；evidence 是简短字符串数组，confidence 是
0 到 1 之间的数字。

signal_windows 和事件明细可能是覆盖全程的分层抽样，evidence_coverage 明确各项输入范围；
总量与全程统计以 signal_summary、modeling_event_summary 为准，不能用抽样条数推算总量。
即使统计覆盖完整会话，抽样仍不等于完整原始波形，具体片段判断应说明证据范围与限制。
窗口代表值与样本极值含义不同，不应将样本极值当作窗口均方根幅值。
历史对话用于理解连续追问，不可将历史回答视为已证实的新观测；本轮仍以当前会话证据为准。
""".strip()


def enhance_analysis(
    *,
    context: dict[str, Any],
    rule_analysis: AnalysisResult,
    question: str,
    history: list[dict[str, Any]] | None = None,
    model: str | None = None,
) -> tuple[str, AnalysisResult]:
    if not config.DASHSCOPE_API_KEY:
        raise LLMConfigurationError("DASHSCOPE_API_KEY is not configured")

    selected_model = model or config.DASHSCOPE_MODEL
    retrieval = retrieve_knowledge(_mouse_rag_query(question, context))
    knowledge_context = format_retrieved_context(retrieval)
    client = OpenAI(
        api_key=config.DASHSCOPE_API_KEY,
        base_url=config.DASHSCOPE_BASE_URL,
        timeout=config.DASHSCOPE_TIMEOUT_SECONDS,
        max_retries=2,
    )

    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for item in (history or [])[-config.AGENT_MAX_HISTORY_MESSAGES :]:
        role = str(item.get("role") or "")
        content = str(item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})

    payload = compact_context(context, rule_analysis)
    messages.append(
        {
            "role": "user",
            "content": (
                f"用户问题：{question}\n\n"
                "以下是本次实验记录及系统已经确定的风险结论。请用面向实验人员的自然中文回答，并按指定格式返回：\n"
                + json.dumps(payload, ensure_ascii=False, default=str)
                + "\n\n可引用的研究资料：\n"
                + knowledge_context
            ),
        }
    )

    try:
        completion = client.chat.completions.create(
            model=selected_model,
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=config.DASHSCOPE_MAX_TOKENS,
            reasoning_effort=config.DASHSCOPE_REASONING_EFFORT,
            extra_body={"enable_thinking": config.DASHSCOPE_ENABLE_THINKING},
        )
    except (APIConnectionError, APITimeoutError, APIStatusError, OSError) as exc:
        raise LLMRequestError(f"百炼模型调用失败：{exc}") from exc

    content = completion.choices[0].message.content
    if not content:
        raise LLMRequestError("百炼模型没有返回可用内容")
    parsed = _parse_json_object(content)
    enhanced = _merge_analysis(
        rule_analysis=rule_analysis,
        generated=parsed,
        model=selected_model,
        knowledge_sources=retrieval.get("sources") or [],
    )
    answer = str(parsed.get("answer") or enhanced.summary)
    return answer, enhanced


def analyze_dataset_session(
    *,
    context: dict[str, Any],
    question: str,
    model: str | None = None,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not config.DASHSCOPE_API_KEY:
        raise LLMConfigurationError("DASHSCOPE_API_KEY is not configured")
    selected_model = model or config.DASHSCOPE_MODEL
    retrieval = retrieve_knowledge(_dataset_rag_query(question, context))
    knowledge_context = format_retrieved_context(retrieval)
    client = OpenAI(
        api_key=config.DASHSCOPE_API_KEY,
        base_url=config.DASHSCOPE_BASE_URL,
        timeout=config.DASHSCOPE_TIMEOUT_SECONDS,
        max_retries=2,
    )
    compact = compact_dataset_context(context)
    messages = [{"role": "system", "content": DATASET_SYSTEM_PROMPT}]
    for turn in history or []:
        messages.extend([
            {"role": "user", "content": str(turn.get("question") or "未记录历史问题")},
            {"role": "assistant", "content": json.dumps({
                key: turn.get(key) for key in ("summary", "evidence", "recommendation", "analysis_source")
            }, ensure_ascii=False, default=str)},
        ])
    messages.append({
        "role": "user",
        "content": f"研究问题：{question}\n\n会话证据：\n"
        + json.dumps(compact, ensure_ascii=False, default=str)
        + "\n\n可引用的研究资料：\n" + knowledge_context,
    })
    try:
        completion = client.chat.completions.create(
            model=selected_model,
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=config.DASHSCOPE_MAX_TOKENS,
            # 会话证据摘要需要稳定的结构化正文，关闭长思考以避免输出额度
            # 被推理过程耗尽；常规对话仍使用 enhance_analysis 的配置。
            extra_body={"enable_thinking": False},
        )
    except (APIConnectionError, APITimeoutError, APIStatusError, OSError) as exc:
        raise LLMRequestError(f"百炼模型调用失败：{exc}") from exc
    content = completion.choices[0].message.content
    if not content:
        raise LLMRequestError("百炼模型没有返回可用内容")
    parsed = _parse_json_object(content)
    evidence = parsed.get("evidence")
    if not isinstance(evidence, list):
        evidence = []
    try:
        confidence = min(1.0, max(0.0, float(parsed.get("confidence", 0.6))))
    except (TypeError, ValueError):
        confidence = 0.6
    return {
        "summary": str(parsed.get("summary") or "当前证据不足以形成结论。"),
        "evidence": [str(item) for item in evidence if str(item).strip()][:12],
        "recommendation": str(parsed.get("recommendation") or "建议继续人工复核。"),
        "confidence": confidence,
        "model_name": selected_model,
        "analysis_source": (
            "bailian_rag_multimodal_agent"
            if retrieval.get("sources")
            else "bailian_multimodal_agent"
        ),
        "knowledge_sources": retrieval.get("sources") or [],
        "retrieval_mode": retrieval.get("mode") or "disabled",
    }


def _merge_analysis(
    *,
    rule_analysis: AnalysisResult,
    generated: dict[str, Any],
    model: str,
    knowledge_sources: list[dict[str, Any]],
) -> AnalysisResult:
    data = rule_analysis.model_dump()
    for field in (
        "summary",
        "vital_analysis",
        "behavior_analysis",
        "stage_analysis",
        "risk_analysis",
        "recommendation",
        "control_strategy",
    ):
        value = generated.get(field)
        if isinstance(value, str) and value.strip():
            data[field] = value.strip()

    generated_factors = generated.get("factors")
    if isinstance(generated_factors, list):
        factors = [str(item).strip() for item in generated_factors if str(item).strip()]
        data["factors"] = list(dict.fromkeys(rule_analysis.factors + factors))[:10]

    data.update(
        {
            "analysis_source": (
                "bailian_rag+rules" if knowledge_sources else "bailian_llm+rules"
            ),
            "model_provider": "bailian",
            "model_name": model,
            "knowledge_sources": knowledge_sources,
        }
    )
    return AnalysisResult.model_validate(data)


def _parse_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMRequestError("百炼模型返回的不是有效 JSON") from exc
    if not isinstance(result, dict):
        raise LLMRequestError("百炼模型返回的 JSON 不是对象")
    return result


def _mouse_rag_query(question: str, context: dict[str, Any]) -> str:
    animal = context.get("animal") or {}
    parts = [
        question,
        str(animal.get("experiment_name") or ""),
        str(animal.get("experiment_stage") or ""),
        "实验动物 多模态 行为 生理 人工复核",
    ]
    return " ".join(item for item in parts if item.strip())


def _dataset_rag_query(question: str, context: dict[str, Any]) -> str:
    session = context.get("session") or {}
    modalities = sorted(
        {
            str(item.get("modality"))
            for item in context.get("signal_windows") or []
            if item.get("modality")
        }
    )
    event_types = sorted(
        {
            str(item.get("event_type"))
            for item in context.get("modeling_events") or []
            if item.get("event_type")
        }
    )
    return " ".join(
        item
        for item in (
            question,
            str(session.get("modeling_stage") or ""),
            str(session.get("session_type") or ""),
            " ".join(modalities),
            " ".join(event_types),
            "DANDI 000718 多模态造模证据",
        )
        if item.strip()
    )

