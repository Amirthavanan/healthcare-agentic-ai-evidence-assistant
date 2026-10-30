
import pytest

from evaluation.metrics import (
    recall_at_k,
    precision_at_k,
    reciprocal_rank,
    mean_reciprocal_rank,
)


def test_recall_at_k():
    assert recall_at_k(
        ["A", "B", "C"],
        {"A", "C", "D"},
        k=2,
    ) == pytest.approx(1 / 3)


def test_precision_at_k():
    assert precision_at_k(
        ["A", "B", "C"],
        {"A", "C"},
        k=2,
    ) == pytest.approx(0.5)


def test_reciprocal_rank():
    assert reciprocal_rank(
        ["X", "B", "A"],
        {"A", "B"},
    ) == pytest.approx(0.5)


def test_no_relevant_result():
    assert reciprocal_rank(
        ["X", "Y"],
        {"A"},
    ) == 0.0


def test_mean_reciprocal_rank():
    assert mean_reciprocal_rank(
        [["A", "B"], ["X", "B"]],
        [{"A"}, {"B"}],
    ) == pytest.approx(0.75)


def test_invalid_k():
    with pytest.raises(ValueError):
        precision_at_k(["A"], {"A"}, k=0)
