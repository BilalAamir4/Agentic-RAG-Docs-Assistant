"""Reciprocal Rank Fusion (RRF) for combining ranked document lists."""


def reciprocal_rank_fusion(
    rankings: list[list[int]],
    k: int = 60,
) -> list[tuple[int, float]]:
    """Combine multiple ranked lists of document row indices using Reciprocal Rank Fusion.

    score(row) = sum over rankings of 1 / (k + rank), where rank is 1-based.
    Ties are broken by lower row index for determinism.

    Args:
        rankings: List of ranked lists, where each list contains row indices ordered best first.
        k: Smoothing constant (typically 60).

    Returns:
        List of (row, score) pairs sorted descending by score, tie-broken by row ascending.
    """
    if not rankings:
        return []

    scores: dict[int, float] = {}
    for ranking in rankings:
        for idx, row in enumerate(ranking):
            rank = idx + 1
            scores[row] = scores.get(row, 0.0) + (1.0 / (k + rank))

    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))
