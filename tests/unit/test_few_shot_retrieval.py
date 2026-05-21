"""Tests for cc_distribution_parser.services.few_shot_retrieval."""

from __future__ import annotations

from cc_distribution_parser.services.few_shot_retrieval import (
    EMBEDDING_DIM,
    Exemplar,
    cosine_similarity,
    embed_query,
    mmr_rerank,
    retrieve_top_k,
)


def test_embed_query_returns_titan_dim_zero_vector():
    v = embed_query("anything")
    assert len(v) == EMBEDDING_DIM
    assert all(x == 0.0 for x in v)


def test_cosine_similarity_zero_vec_handled():
    assert cosine_similarity((0.0, 0.0), (1.0, 1.0)) == 0.0


def test_cosine_similarity_known_vectors():
    assert cosine_similarity((1.0, 0.0), (1.0, 0.0)) == 1.0
    assert abs(cosine_similarity((1.0, 0.0), (0.0, 1.0))) < 1e-9


def _ex(id_: str, embedding: tuple[float, ...]) -> Exemplar:
    return Exemplar(
        id=id_,
        class_="capital_call",
        field_values_json={},
        synopsis_200tok="syn",
        embedding=embedding,
    )


def test_mmr_picks_diverse_top_k():
    """MMR favors diversity when lambda is small.

    a and b are identical (max redundancy); c is orthogonal. With lambda=0.2
    (diversity-heavy), c should beat b for the second slot.
    """
    q = (1.0, 0.0)
    a = _ex("a", (1.0, 0.0))
    b = _ex("b", (1.0, 0.0))
    c = _ex("c", (0.0, 1.0))
    result = mmr_rerank(query_vec=q, candidates=[a, b, c], k=2, lambda_=0.2)
    ids = [r.id for r in result]
    assert ids[0] == "a"
    assert ids[1] == "c"


def test_retrieve_top_k_empty_pool_returns_empty():
    out = retrieve_top_k(query_vec=(0.0,), class_="capital_call")
    assert out == []


def test_retrieve_top_k_uses_injected_fetcher():
    """Verify the fetcher seam works; exact MMR ordering is covered separately."""
    pool = [
        _ex("relevant", (1.0, 0.0)),
        _ex("diverse", (0.0, 1.0)),
        _ex("medium", (0.7, 0.7)),
    ]

    def fake_fetch(_class, _k):
        return pool

    out = retrieve_top_k(
        query_vec=(1.0, 0.0),
        class_="capital_call",
        k_initial=3,
        k_final=2,
        fetch_candidates=fake_fetch,
    )
    assert len(out) == 2
    assert out[0].id == "relevant"  # max relevance wins slot 1
