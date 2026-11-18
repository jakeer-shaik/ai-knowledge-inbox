"""Vector similarity search (brute-force cosine over an in-memory matrix)."""

import numpy as np


def rank_by_cosine(query: np.ndarray, matrix: np.ndarray, *, top_k: int, min_score: float) -> list[tuple[int, float]]:
    """Return (row_index, score) for the best `top_k` rows scoring at least `min_score`, best first.

    O(n * d) per query: fine for thousands of chunks, the first thing to replace at scale.
    """
    if matrix.size == 0 or top_k <= 0:
        return []

    query_norm = np.linalg.norm(query) or 1.0
    row_norms = np.linalg.norm(matrix, axis=1)
    row_norms[row_norms == 0] = 1.0
    scores = (matrix @ query) / (row_norms * query_norm)

    k = min(top_k, len(scores))
    best = np.argpartition(-scores, k - 1)[:k]
    best = best[np.argsort(-scores[best])]
    return [(int(i), float(scores[i])) for i in best if scores[i] >= min_score]
