from __future__ import annotations


def calculate_maturity_score(text_length: int) -> float:
    """
    Map raw text length to a normalized maturity score [0, 1].
    """
    normalized = (text_length - 50) / 450
    return max(0.0, min(normalized, 1.0))


def calculate_alpha(maturity: float, base_alpha: float = 0.4) -> float:
    """
    Compute adaptive macro weight alpha using maturity and base weight.
    """
    maturity_clamped = max(0.0, min(maturity, 1.0))
    return maturity_clamped * base_alpha
