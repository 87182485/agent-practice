# tests/test_retrieval_metrics.py
import pytest
from retrieval.metrics import recall_at_k


def test_all_relevant_in_top_k():
    assert recall_at_k(["a", "b", "x"], {"a", "b"}, k=3) == 1.0


def test_none_relevant():
    assert recall_at_k(["x", "y"], {"a"}, k=2) == 0.0


def test_partial():
    assert recall_at_k(["a", "x", "y"], {"a", "b"}, k=3) == 0.5


def test_k_truncates():
    # "a" is retrieved, but at rank 2, outside k=1
    assert recall_at_k(["x", "a"], {"a"}, k=1) == 0.0


def test_fewer_results_than_k():
    assert recall_at_k(["a"], {"a"}, k=5) == 1.0


def test_duplicates_count_once():
    assert recall_at_k(["a", "a"], {"a", "b"}, k=2) == 0.5


def test_empty_relevant_is_an_error():
    # recall is undefined (0/0); a silent 0.0 or 1.0 would corrupt the mean
    with pytest.raises(ValueError):
        recall_at_k(["a"], set(), k=1)


@pytest.mark.parametrize("k", [0, -1])
def test_nonpositive_k_is_an_error(k):
    with pytest.raises(ValueError):
        recall_at_k(["a"], {"a"}, k=k)