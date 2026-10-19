from __future__ import annotations

from agent.rag_service import (
    format_retrieved_context,
    get_rag_status,
    load_knowledge_chunks,
    retrieve_knowledge,
)


def test_builtin_knowledge_documents_are_loaded() -> None:
    chunks = load_knowledge_chunks()
    status = get_rag_status()

    assert status["document_count"] >= 4
    assert status["chunk_count"] == len(chunks)
    assert any(item.title == "DANDI 000718 官方数据说明" for item in chunks)
    assert all(item.source_url.startswith("https://") for item in chunks)


def test_keyword_fallback_retrieves_relevant_sources() -> None:
    result = retrieve_knowledge(
        "恐惧条件化足底电击后，如何结合冻结行为和钙活动复核？",
        top_k=3,
        use_embeddings=False,
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
    )
    context = format_retrieved_context(result)

    assert "[资料1]" in context
    assert "来源：https://" in context
