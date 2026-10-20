from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from threading import RLock
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from openai import OpenAI

from agent import config


_METADATA_RE = re.compile(r"^<!--\s*([a-z_]+)\s*:\s*(.*?)\s*-->$")
_HEADING_RE = re.compile(r"^#{1,4}\s+(.+?)\s*$")
_ASCII_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_+.-]*")
_CHINESE_RE = re.compile(r"[\u4e00-\u9fff]+")
_CACHE_LOCK = RLock()


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    title: str
    section: str
    source_url: str
    source_type: str
    content: str


@dataclass(frozen=True)
class RankedChunk:
    chunk: KnowledgeChunk
    retrieval_score: float
    lexical_score: float
    rerank_score: float | None = None


def get_rag_status() -> dict[str, Any]:
    chunks = load_knowledge_chunks()
    documents = {item.title for item in chunks}
    return {
        "enabled": config.RAG_ENABLED,
        "document_count": len(documents),
        "chunk_count": len(chunks),
        "semantic_retrieval_available": bool(
            config.RAG_ENABLED
            and config.RAG_USE_EMBEDDINGS
            and config.DASHSCOPE_API_KEY
        ),
        "embedding_model": config.RAG_EMBEDDING_MODEL,
        "reranking_available": bool(
            config.RAG_ENABLED
            and config.RAG_USE_RERANKER
            and config.DASHSCOPE_API_KEY
        ),
        "rerank_model": config.RAG_RERANK_MODEL,
        "rerank_candidates": config.RAG_RERANK_CANDIDATES,
        "fallback": "keyword",
    }


def retrieve_knowledge(
    query: str,
    *,
    top_k: int | None = None,
    use_embeddings: bool | None = None,
    use_reranker: bool | None = None,
) -> dict[str, Any]:
    if not config.RAG_ENABLED or not query.strip():
        return {"mode": "disabled", "sources": []}

    chunks = load_knowledge_chunks()
    if not chunks:
        return {"mode": "empty", "sources": []}

    selected_top_k = max(1, min(10, top_k or config.RAG_TOP_K))
    lexical_scores = [_lexical_score(query, item) for item in chunks]
    semantic_scores: list[float] | None = None
    semantic_requested = (
        config.RAG_USE_EMBEDDINGS if use_embeddings is None else use_embeddings
    )
    if semantic_requested and config.DASHSCOPE_API_KEY:
        semantic_scores = _semantic_scores(query, chunks)

    ranked: list[RankedChunk] = []
    for index, chunk in enumerate(chunks):
        lexical = lexical_scores[index]
        if semantic_scores is None:
            score = lexical
        else:
            semantic = max(0.0, semantic_scores[index])
            score = semantic * 0.85 + lexical * 0.15
        ranked.append(
            RankedChunk(
                chunk=chunk,
                retrieval_score=score,
                lexical_score=lexical,
            )
        )
    ranked.sort(
        key=lambda item: (item.retrieval_score, item.lexical_score),
        reverse=True,
    )

    candidate_limit = max(selected_top_k, config.RAG_RERANK_CANDIDATES)
    candidates = _select_candidates(ranked, candidate_limit)
    rerank_requested = (
        config.RAG_USE_RERANKER if use_reranker is None else use_reranker
    )
    rerank_applied = False
    if rerank_requested and config.DASHSCOPE_API_KEY and len(candidates) > 1:
        reranked = _rerank_candidates(query, candidates)
        if reranked is not None:
            candidates = reranked
            rerank_applied = True

    sources: list[dict[str, Any]] = []
    seen_documents: set[str] = set()
    for candidate in candidates:
        chunk = candidate.chunk
        document_key = chunk.title
        if document_key in seen_documents:
            continue
        seen_documents.add(document_key)
        source = {
            "chunk_id": chunk.chunk_id,
            "title": chunk.title,
            "section": chunk.section,
            "source_url": chunk.source_url,
            "source_type": chunk.source_type,
            "score": round(
                candidate.rerank_score
                if candidate.rerank_score is not None
                else candidate.retrieval_score,
                4,
            ),
            "retrieval_score": round(candidate.retrieval_score, 4),
            "excerpt": _excerpt(chunk.content),
        }
        if candidate.rerank_score is not None:
            source["rerank_score"] = round(candidate.rerank_score, 4)
        sources.append(source)
        if len(sources) >= selected_top_k:
            break

    base_mode = "semantic_keyword" if semantic_scores is not None else "keyword"
    return {
        "mode": f"{base_mode}_rerank" if rerank_applied else base_mode,
        "rerank_applied": rerank_applied,
        "candidate_count": len(candidates),
        "sources": sources,
    }


def _select_candidates(
    ranked: list[RankedChunk],
    limit: int,
    *,
    per_document: int = 2,
) -> list[RankedChunk]:
    selected: list[RankedChunk] = []
    document_counts: dict[str, int] = {}
    for candidate in ranked:
        if candidate.retrieval_score < config.RAG_MIN_SCORE:
            continue
        title = candidate.chunk.title
        if document_counts.get(title, 0) >= per_document:
            continue
        selected.append(candidate)
        document_counts[title] = document_counts.get(title, 0) + 1
        if len(selected) >= limit:
            break
    return selected


def _rerank_candidates(
    query: str,
    candidates: list[RankedChunk],
) -> list[RankedChunk] | None:
    documents = [
        f"{item.chunk.title}\n{item.chunk.section}\n{item.chunk.content}"
        for item in candidates
    ]
    try:
        results = _request_rerank(query, documents)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
        return None

    scores: dict[int, float] = {}
    for result in results:
        index = result.get("index")
        score = result.get("relevance_score")
        if (
            isinstance(index, int)
            and 0 <= index < len(candidates)
            and isinstance(score, (int, float))
            and math.isfinite(float(score))
        ):
            scores[index] = float(score)
    if not scores:
        return None

    reranked = [
        RankedChunk(
            chunk=candidate.chunk,
            retrieval_score=candidate.retrieval_score,
            lexical_score=candidate.lexical_score,
            rerank_score=scores.get(index, -1.0),
        )
        for index, candidate in enumerate(candidates)
    ]
    reranked.sort(
        key=lambda item: (
            item.rerank_score if item.rerank_score is not None else -1.0,
            item.retrieval_score,
        ),
        reverse=True,
    )
    return reranked


def _request_rerank(query: str, documents: list[str]) -> list[dict[str, Any]]:
    payload = {
        "model": config.RAG_RERANK_MODEL,
        "input": {"query": query, "documents": documents},
        "parameters": {
            "top_n": len(documents),
            "return_documents": False,
            "instruct": config.RAG_RERANK_INSTRUCT,
        },
    }
    request = Request(
        config.RAG_RERANK_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.DASHSCOPE_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=config.RAG_RERANK_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"rerank request failed with HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError("rerank service is unavailable") from exc

    if data.get("code"):
        raise RuntimeError(f"rerank request failed: {data['code']}")
    results = data.get("output", {}).get("results")
    if not isinstance(results, list):
        raise ValueError("rerank response does not contain results")
    return [item for item in results if isinstance(item, dict)]


def format_retrieved_context(retrieval: dict[str, Any]) -> str:
    sources = retrieval.get("sources") or []
    if not sources:
        return "本次没有检索到可引用的研究资料。"
    blocks: list[str] = []
    for index, source in enumerate(sources, start=1):
        blocks.append(
            f"[资料{index}] {source['title']}｜{source['section']}\n"
            f"来源：{source['source_url']}\n"
            f"内容：{source['excerpt']}"
        )
    return "\n\n".join(blocks)


def load_knowledge_chunks() -> list[KnowledgeChunk]:
    directory = config.RAG_KNOWLEDGE_DIR
    if not directory.exists():
        return []
    chunks: list[KnowledgeChunk] = []
    for path in sorted(directory.glob("*.md")):
        chunks.extend(_read_document(path))
    return chunks


def _read_document(path: Path) -> list[KnowledgeChunk]:
    text = path.read_text(encoding="utf-8")
    metadata: dict[str, str] = {}
    content_lines: list[str] = []
    for line in text.splitlines():
        match = _METADATA_RE.match(line.strip())
        if match:
            metadata[match.group(1)] = match.group(2).strip()
        else:
            content_lines.append(line)

    title = metadata.get("title") or path.stem
    source_url = metadata.get("source_url") or ""
    source_type = metadata.get("source_type") or "研究资料"
    sections: list[tuple[str, str]] = []
    current_section = "概述"
    buffer: list[str] = []

    def flush() -> None:
        body = "\n".join(buffer).strip()
        if body:
            sections.extend(_split_section(current_section, body))
        buffer.clear()

    for line in content_lines:
        heading = _HEADING_RE.match(line.strip())
        if heading:
            flush()
            current_section = heading.group(1).strip()
        else:
            buffer.append(line)
    flush()

    chunks: list[KnowledgeChunk] = []
    for index, (section, body) in enumerate(sections):
        chunk_id = hashlib.sha1(
            f"{path.name}:{section}:{index}:{body}".encode("utf-8")
        ).hexdigest()[:20]
        chunks.append(
            KnowledgeChunk(
                chunk_id=chunk_id,
                title=title,
                section=section,
                source_url=source_url,
                source_type=source_type,
                content=body,
            )
        )
    return chunks


def _split_section(section: str, body: str) -> list[tuple[str, str]]:
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n", body) if item.strip()]
    if not paragraphs:
        return []
    results: list[tuple[str, str]] = []
    current: list[str] = []
    current_size = 0
    for paragraph in paragraphs:
        if current and current_size + len(paragraph) > config.RAG_CHUNK_SIZE:
            results.append((section, "\n\n".join(current)))
            current = []
            current_size = 0
        current.append(paragraph)
        current_size += len(paragraph)
    if current:
        results.append((section, "\n\n".join(current)))
    return results


def _semantic_scores(
    query: str,
    chunks: list[KnowledgeChunk],
) -> list[float] | None:
    try:
        vectors = _load_or_build_vectors(chunks)
        query_vector = _embed_texts([query])[0]
    except Exception:
        return None
    return [_cosine_similarity(query_vector, vectors[item.chunk_id]) for item in chunks]


def _load_or_build_vectors(
    chunks: list[KnowledgeChunk],
) -> dict[str, list[float]]:
    fingerprint = _knowledge_fingerprint(chunks)
    with _CACHE_LOCK:
        cached = _read_cache()
        if (
            cached.get("fingerprint") == fingerprint
            and cached.get("model") == config.RAG_EMBEDDING_MODEL
            and cached.get("dimensions") == config.RAG_EMBEDDING_DIMENSIONS
        ):
            vectors = cached.get("vectors")
            if isinstance(vectors, dict) and all(item.chunk_id in vectors for item in chunks):
                return {key: [float(value) for value in vector] for key, vector in vectors.items()}

        vectors: dict[str, list[float]] = {}
        for offset in range(0, len(chunks), 10):
            batch = chunks[offset : offset + 10]
            embedded = _embed_texts(
                [f"{item.title}\n{item.section}\n{item.content}" for item in batch]
            )
            for item, vector in zip(batch, embedded, strict=True):
                vectors[item.chunk_id] = vector
        _write_cache(
            {
                "fingerprint": fingerprint,
                "model": config.RAG_EMBEDDING_MODEL,
                "dimensions": config.RAG_EMBEDDING_DIMENSIONS,
                "vectors": vectors,
            }
        )
        return vectors


def _embed_texts(texts: list[str]) -> list[list[float]]:
    client = OpenAI(
        api_key=config.DASHSCOPE_API_KEY,
        base_url=config.DASHSCOPE_BASE_URL,
        timeout=config.DASHSCOPE_TIMEOUT_SECONDS,
        max_retries=2,
    )
    response = client.embeddings.create(
        model=config.RAG_EMBEDDING_MODEL,
        input=texts,
        dimensions=config.RAG_EMBEDDING_DIMENSIONS,
        encoding_format="float",
    )
    ordered = sorted(response.data, key=lambda item: item.index)
    return [[float(value) for value in item.embedding] for item in ordered]


def _read_cache() -> dict[str, Any]:
    try:
        value = json.loads(config.RAG_CACHE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _write_cache(payload: dict[str, Any]) -> None:
    config.RAG_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = config.RAG_CACHE_PATH.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    temporary.replace(config.RAG_CACHE_PATH)


def _knowledge_fingerprint(chunks: list[KnowledgeChunk]) -> str:
    payload = json.dumps(
        [asdict(item) for item in chunks],
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _lexical_score(query: str, chunk: KnowledgeChunk) -> float:
    query_terms = _terms(query)
    if not query_terms:
        return 0.0
    document_terms = _terms(
        f"{chunk.title} {chunk.section} {chunk.content}"
    )
    overlap = query_terms & document_terms
    if not overlap:
        return 0.0
    weighted = sum(min(4, len(term)) for term in overlap)
    denominator = max(1, sum(min(4, len(term)) for term in query_terms))
    return min(1.0, weighted / denominator)


def _terms(text: str) -> set[str]:
    normalized = text.lower().replace("offline", "离线巩固").replace("fc", "恐惧条件化")
    terms = set(_ASCII_TOKEN_RE.findall(normalized))
    for sequence in _CHINESE_RE.findall(normalized):
        if len(sequence) <= 4:
            terms.add(sequence)
        for size in (2, 3, 4):
            terms.update(
                sequence[index : index + size]
                for index in range(max(0, len(sequence) - size + 1))
            )
    return terms


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _excerpt(content: str, limit: int = 650) -> str:
    compact = re.sub(r"\s+", " ", content).strip()
    return compact if len(compact) <= limit else compact[: limit - 1].rstrip() + "…"
