"""Small statistics helpers (no numpy/scipy dependency)."""
from __future__ import annotations

import math


def normal_cdf(z: float) -> float:
    return 0.5 * math.erfc(-z / math.sqrt(2.0))


def two_proportion_z_test(success_a: int, n_a: int, success_b: int, n_b: int) -> dict:
    """Two-sided z-test for a difference in proportions."""
    if n_a <= 0 or n_b <= 0:
        return {"z": None, "p_value": None, "significant": False}
    p_a = success_a / n_a
    p_b = success_b / n_b
    pooled = (success_a + success_b) / (n_a + n_b)
    denom = math.sqrt(pooled * (1 - pooled) * (1 / n_a + 1 / n_b))
    if denom == 0:
        return {"z": None, "p_value": None, "significant": False}
    z = (p_a - p_b) / denom
    p_value = 2 * (1 - normal_cdf(abs(z)))
    return {"z": round(z, 4), "p_value": p_value, "significant": p_value < 0.05}


def proportion_diff_ci(success_a: int, n_a: int, success_b: int, n_b: int,
                       z: float = 1.96) -> dict:
    """Confidence interval for (p_a - p_b), unpooled standard error.

    The client workbooks quote a low / point / high band rather than a bare
    point estimate, because an uplift whose interval crosses zero should not be
    read as a result. Returns fractions, not percentage points.
    """
    if n_a <= 0 or n_b <= 0:
        return {"low": None, "point": None, "high": None, "crosses_zero": None}
    p_a = success_a / n_a
    p_b = success_b / n_b
    se = math.sqrt(p_a * (1 - p_a) / n_a + p_b * (1 - p_b) / n_b)
    point = p_a - p_b
    low, high = point - z * se, point + z * se
    return {"low": low, "point": point, "high": high, "crosses_zero": low <= 0 <= high}


def safe_rate(numerator: float, denominator: float) -> float:
    return (numerator / denominator) if denominator else 0.0


def relative_delta(rate: float, baseline: float) -> float | None:
    """Relative change vs baseline; None when the baseline carries no signal."""
    if baseline == 0:
        return None
    return (rate - baseline) / baseline
