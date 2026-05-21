"""Few-shot retrieval — Snowflake Cortex VECTOR similarity + MMR re-rank.

Per architecture.md §8.1: top-20 via cosine similarity, MMR re-rank with
λ=0.5 returns top-5. Doc-independent build wires the seam; live Titan
embeddings + Snowflake queries are exercised when real exemplars exist in
few_shot_exemplars_silver (Sprint 3 in the actual plan).

`embed_query` returns zeros until Titan integration; that's the correct
no-op for the empty-pool MVP — `retrieve_top_k` returns [] either way.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

EMBEDDING_DIM = 1024  # Titan v2 — see .claude/rules/snowflake-migrations.md rule 5


@dataclass(frozen=True)
class Exemplar:
    id: str
    class_: str
    field_values_json: dict[str, Any]
    synopsis_200tok: str
    embedding: tuple[float, ...]


def embed_query(_text: str) -> tuple[float, ...]:
    """Titan v2 embedding stub. Returns a zero vector of the canonical dim.

    Replaced with the live Bedrock embedding call in real Sprint 3.
    """
    return tuple(0.0 for _ in range(EMBEDDING_DIM))


def cosine_similarity(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def mmr_rerank(
    *,
    query_vec: tuple[float, ...],
    candidates: list[Exemplar],
    k: int = 5,
    lambda_: float = 0.5,
) -> list[Exemplar]:
    """Maximal Marginal Relevance re-rank.

    Iteratively pick the candidate that maximizes:
        λ * sim(q, c) - (1-λ) * max_{s in selected} sim(c, s)
    """
    selected: list[Exemplar] = []
    pool = list(candidates)
    while pool and len(selected) < k:
        scored: list[tuple[float, Exemplar]] = []
        for cand in pool:
            relevance = cosine_similarity(query_vec, cand.embedding)
            redundancy = max(
                (cosine_similarity(cand.embedding, s.embedding) for s in selected),
                default=0.0,
            )
            scored.append((lambda_ * relevance - (1 - lambda_) * redundancy, cand))
        scored.sort(key=lambda t: t[0], reverse=True)
        chosen = scored[0][1]
        selected.append(chosen)
        pool.remove(chosen)
    return selected


def retrieve_top_k(
    *,
    query_vec: tuple[float, ...],
    class_: str,
    k_initial: int = 20,
    k_final: int = 5,
    fetch_candidates: Callable[[str, int], list[Exemplar]] | None = None,
) -> list[Exemplar]:
    """Top-k retrieval. `fetch_candidates` is a callable that runs the
    Cortex VECTOR_COSINE_SIMILARITY query; injected so unit tests can stub
    Snowflake completely.

    Default fetch returns [] (no Snowflake, no exemplars) — safe for the
    empty-pool MVP.
    """
    if fetch_candidates is None:
        candidates: list[Exemplar] = []
    else:
        candidates = fetch_candidates(class_, k_initial)
    return mmr_rerank(query_vec=query_vec, candidates=candidates, k=k_final)
