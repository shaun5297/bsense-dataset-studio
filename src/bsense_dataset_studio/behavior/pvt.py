from __future__ import annotations

from collections.abc import Iterable, Mapping

from .metrics import reaction_time_metrics, safe_ratio

FALSE_START_SECONDS = 0.1
LAPSE_SECONDS = 0.355
PVT_B_DURATION_SECONDS = 180.0
PVT_B_ISI_MIN_SECONDS = 1.0
PVT_B_ISI_MAX_SECONDS = 4.0
PVT_B_FALSE_START_SECONDS = FALSE_START_SECONDS
PVT_B_LAPSE_SECONDS = LAPSE_SECONDS
PVT_B_TIMEOUT_SECONDS = 30.0


def classify_response(
    response_time_s: float | None,
    *,
    valid: bool = True,
    timeout: bool | None = None,
) -> dict[str, object]:
    false_start = response_time_s is not None and response_time_s < FALSE_START_SECONDS
    lapse = response_time_s is None or response_time_s >= LAPSE_SECONDS
    return {
        "reaction_time_s": response_time_s,
        "responded": response_time_s is not None,
        "false_start": false_start,
        "lapse": lapse,
        "timeout": response_time_s is None if timeout is None else timeout,
        "valid": valid,
    }


def summarize_trials(trials: Iterable[Mapping[str, object]]) -> dict[str, object]:
    rows = [row for row in trials if row.get("valid", True)]
    response_times = [
        float(row["reaction_time_s"])
        for row in rows
        if row.get("reaction_time_s") is not None and not row.get("false_start")
    ]
    result: dict[str, object] = {
        "valid_trial_count": len(rows),
        "false_start_rate": safe_ratio(sum(bool(row.get("false_start")) for row in rows), len(rows)),
        "lapse_rate": safe_ratio(sum(bool(row.get("lapse")) for row in rows), len(rows)),
    }
    result.update(reaction_time_metrics(response_times))
    return result
