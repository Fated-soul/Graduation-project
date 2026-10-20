from __future__ import annotations

from unittest.mock import patch

from agent import config
from agent.rag_service import (
    format_retrieved_context,
    get_rag_status,
    load_knowledge_chunks,
    retrieve_knowledge,
)


def test_builtin_knowledge_documents_are_loaded() -> None:
    chunks = load_knowledge_chunks()
    status = get_rag_status()

    assert status["document_count"] >= 18
    assert status["chunk_count"] == len(chunks)
    assert any(item.title == "DANDI 000718 官方数据说明" for item in chunks)
    assert all(item.source_url.startswith("https://") for item in chunks)


def test_keyword_fallback_retrieves_relevant_sources() -> None:
    result = retrieve_knowledge(
        "恐惧条件化足底电击后，如何结合冻结行为和钙活动复核？",
        top_k=3,
        use_embeddings=False,
        use_reranker=False,
    )

    assert result["mode"] == "keyword"
    assert result["sources"]
    combined = " ".join(
        f"{item['title']} {item['section']} {item['excerpt']}"
        for item in result["sources"]
    )
    assert "恐惧条件化" in combined
    assert "冻结" in combined


def test_retrieved_context_uses_stable_citation_numbers() -> None:
    result = retrieve_knowledge(
        "离线会话中的脑电肌电和睡眠状态应该怎样解释？",
        top_k=2,
        use_embeddings=False,
        use_reranker=False,
    )
    context = format_retrieved_context(result)

    assert "[资料1]" in context
    assert "来源：https://" in context


def test_keyword_retrieval_covers_sleep_and_alignment_guidance() -> None:
    sleep_result = retrieve_knowledge(
        "EEG 和 EMG 怎样区分 REM、NREM 和清醒状态？",
        top_k=4,
        use_embeddings=False,
        use_reranker=False,
    )
    sleep_text = " ".join(
        f"{item['title']} {item['section']} {item['excerpt']}"
        for item in sleep_result["sources"]
    )
    assert "睡眠" in sleep_text
    assert "EEG" in sleep_text
    assert "EMG" in sleep_text

    alignment_result = retrieve_knowledge(
        "不同 NWB 会话怎样按真实采集时间对齐，缺失区间怎么办？",
        top_k=4,
        use_embeddings=False,
        use_reranker=False,
    )
    alignment_text = " ".join(
        f"{item['title']} {item['section']} {item['excerpt']}"
        for item in alignment_result["sources"]
    )
    assert "NWB" in alignment_text
    assert "时间" in alignment_text
    assert "缺失" in alignment_text


def test_reranker_reorders_recalled_candidates() -> None:
    def reversed_scores(
        _query: str,
        documents: list[str],
    ) -> list[dict[str, float | int]]:
        return [
            {"index": index, "relevance_score": float(index + 1) / len(documents)}
            for index in range(len(documents))
        ]

    with (
        patch.object(config, "DASHSCOPE_API_KEY", "test-key"),
        patch("agent.rag_service._request_rerank", side_effect=reversed_scores),
    ):
        result = retrieve_knowledge(
            "恐惧条件化冻结行为钙活动",
            top_k=3,
            use_embeddings=False,
            use_reranker=True,
        )

    assert result["mode"] == "keyword_rerank"
    assert result["rerank_applied"] is True
    assert result["candidate_count"] > 3
    assert all("rerank_score" in item for item in result["sources"])
    assert result["sources"][0]["score"] >= result["sources"][1]["score"]


def test_reranker_failure_falls_back_to_initial_ranking() -> None:
    with (
        patch.object(config, "DASHSCOPE_API_KEY", "test-key"),
        patch(
            "agent.rag_service._request_rerank",
            side_effect=RuntimeError("temporary failure"),
        ),
    ):
        result = retrieve_knowledge(
            "EEG EMG 睡眠状态",
            top_k=3,
            use_embeddings=False,
            use_reranker=True,
        )

    assert result["mode"] == "keyword"
    assert result["rerank_applied"] is False
    assert result["sources"]
