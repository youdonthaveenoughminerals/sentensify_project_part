from __future__ import annotations

from Levenshtein import distance


def calculate_diff_ratio(prev: str, curr: str) -> float:
    """
    Compute normalized diff ratio using Levenshtein distance.

    Args:
        prev: previous snapshot text.
        curr: current snapshot text.

    Returns:
        A float in [0, 1] representing normalized edit distance.
    """
    prev = prev or ""
    curr = curr or ""
    max_len = max(len(prev), 1)
    return min(distance(prev, curr) / max_len, 1.0)
