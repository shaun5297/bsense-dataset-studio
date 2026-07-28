from __future__ import annotations

import math
import statistics
from collections.abc import Sequence


def safe_ratio(numerator: int | float, denominator: int | float) -> float | None:
    return round(float(numerator) / float(denominator), 6) if denominator else None


def linear_slope(values: Sequence[float]) -> float | None:
    if len(values) < 2:
        return None
    mean_x = (len(values) - 1) / 2
    mean_y = statistics.fmean(values)
    denominator = sum((index - mean_x) ** 2 for index in range(len(values)))
    if not denominator:
        return None
    return sum((index - mean_x) * (value - mean_y) for index, value in enumerate(values)) / denominator


def reaction_time_metrics(values: Sequence[float]) -> dict[str, float | None]:
    finite = [float(value) for value in values if math.isfinite(float(value)) and value >= 0]
    if not finite:
        return {
            "median_reaction_time_s": None,
            "mean_reaction_time_s": None,
            "reaction_time_sd_s": None,
            "reaction_time_cv": None,
            "slowest_10_percent_mean_s": None,
            "second_half_minus_first_half_s": None,
            "reaction_time_slope": None,
        }
    mean = statistics.fmean(finite)
    split = max(1, len(finite) // 2)
    slow_count = max(1, math.ceil(len(finite) * 0.1))
    metrics = {
        "median_reaction_time_s": statistics.median(finite),
        "mean_reaction_time_s": mean,
        "reaction_time_sd_s": statistics.pstdev(finite) if len(finite) > 1 else 0.0,
        "reaction_time_cv": statistics.pstdev(finite) / mean if len(finite) > 1 and mean else None,
        "slowest_10_percent_mean_s": statistics.fmean(sorted(finite)[-slow_count:]),
        "second_half_minus_first_half_s": (
            statistics.fmean(finite[split:]) - statistics.fmean(finite[:split])
            if finite[split:]
            else None
        ),
        "reaction_time_slope": linear_slope(finite),
    }
    return {key: round(value, 6) if value is not None else None for key, value in metrics.items()}
