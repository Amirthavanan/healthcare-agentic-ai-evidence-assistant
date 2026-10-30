import pytest

from retrieval.hybrid import HybridRetriever


@pytest.fixture
def retriever():
    return HybridRetriever()


def test_empty_query_returns_no_results(retriever):
    assert retriever.search("") == []
    assert retriever.search("   ") == []


def test_top_k_limits_results(retriever):
    results = retriever.search(
        "clinical evidence",
        top_k=2,
    )
    assert len(results) <= 2


def test_results_include_required_fields(retriever):
    results = retriever.search("clinical evidence", top_k=3)

    for result in results:
        assert "text" in result
        assert "section" in result
        assert "score" in result
        assert "excerpt" in result
        assert 0 <= result["score"] <= 1


def test_invalid_top_k(retriever):
    assert retriever.search("clinical evidence", top_k=0) == []


def test_invalid_score_threshold(retriever):
    with pytest.raises(ValueError):
        retriever.search("clinical evidence", min_score=1.5)


def test_weight_validation():
    with pytest.raises(ValueError):
        HybridRetriever(sparse_weight=0, dense_weight=0)
