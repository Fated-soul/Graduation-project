from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from threading import RLock
from typing import Any

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
        "fallback": "keyword",
    }


def retrieve_knowledge(
    query: str,
    *,
    top_k: int | None = None,
    use_embeddings: bool | None = None,
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

    ranked: list[tuple[float, float, KnowledgeChunk]] = []
    for index, chunk in enumerate(chunks):
        lexical = lexical_scores[index]
        if semantic_scores is None:
            score = lexical
        else:
            semantic = max(0.0, semantic_scores[index])
            score = semantic * 0.85 + lexical * 0.15
        ranked.append((score, lexical, chunk))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)

    sources: list[dict[str, Any]] = []
    seen_documents: set[str] = set()
    for score, lexical, chunk in ranked:
        if score < config.RAG_MIN_SCORE:
            continue
        document_key = chunk.title
        if document_key in seen_documents:
            continue
        seen_documents.add(document_key)
        sources.append(
            {
                "chunk_id": chunk.chunk_id,
                "title": chunk.title,
                "section": chunk.section,
                "source_url": chunk.source_url,
                "source_type": chunk.source_type,
                "score": round(score, 4),
                "excerpt": _excerpt(chunk.content),
            }
        )
        if len(sources) >= selected_top_k:
            break

    return {
        "mode": "semantic_keyword" if semantic_scores is not None else "keyword",
        "sources": sources,
    }


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
