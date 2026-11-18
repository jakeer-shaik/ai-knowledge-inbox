import numpy as np

from app.services.retrieval import rank_by_cosine


def test_ranks_by_cosine_similarity():
    matrix = np.array([[1, 0], [0.7, 0.7], [0, 1]], dtype=np.float32)
    ranked = rank_by_cosine(np.array([1, 0], dtype=np.float32), matrix, top_k=3, min_score=-1)
    assert [i for i, _ in ranked] == [0, 1, 2]
    assert ranked[0][1] == 1.0


def test_filters_below_min_score_and_limits_k():
    matrix = np.array([[1, 0], [0.7, 0.7], [0, 1]], dtype=np.float32)
    ranked = rank_by_cosine(np.array([1, 0], dtype=np.float32), matrix, top_k=2, min_score=0.5)
    assert [i for i, _ in ranked] == [0, 1]


def test_empty_index_returns_nothing():
    assert rank_by_cosine(np.array([1.0]), np.empty((0, 0), dtype=np.float32), top_k=5, min_score=0) == []
