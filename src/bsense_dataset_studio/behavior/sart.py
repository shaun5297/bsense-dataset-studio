from __future__ import annotations

from collections.abc import Iterable, Mapping

from .metrics import reaction_time_metrics, safe_ratio

FALSE_START_SECONDS = 0.1


def classify_trial(
    should_respond: bool,
    response_time_s: float | None,
    *,
    trial: int | None = None,
    stimulus: str | None = None,
    valid: bool = True,
    response_count: int | None = None,
    invalid_reason: str | None = None,
) -> dict[str, object]:
    responded = response_time_s is not None
    false_start = bool(responded and float(response_time_s) < FALSE_START_SECONDS)
    if false_start:
        outcome = "false_start" if should_respond else "commission"
    elif should_respond and responded:
        outcome = "hit"
    elif should_respond:
        outcome = "omission"
    elif responded:
        outcome = "commission"
    else:
        outcome = "correct_rejection"
    return {
        "trial": trial,
        "stimulus": stimulus,
        "should_respond": should_respond,
        "responded": responded,
        "response_count": response_count if response_count is not None else int(responded),
        "multiple_response": bool(response_count is not None and response_count > 1),
        "reaction_time_s": round(float(response_time_s), 6) if responded else None,
        "outcome": outcome,
        "false_start": false_start,
        "correct": outcome in {"hit", "correct_rejection"},
        "valid": valid,
        "invalid_reason": invalid_reason,
    }


def summarize_trials(trials: Iterable[Mapping[str, object]]) -> dict[str, object]:
    rows = [row for row in trials if row.get("valid", True)]
    go_count = sum(bool(row.get("should_respond")) for row in rows)
    no_go_count = len(rows) - go_count
    outcomes = {
        name: sum(row.get("outcome") == name for row in rows)
        for name in ("hit", "omission", "commission", "correct_rejection")
    }
    false_starts = sum(bool(row.get("false_start")) for row in rows)
    reaction_times = [
        float(row["reaction_time_s"])
        for row in rows
        if row.get("outcome") == "hit" and row.get("reaction_time_s") is not None
    ]
    result: dict[str, object] = {
        "valid_trial_count": len(rows),
        "go_trial_count": go_count,
        "no_go_trial_count": no_go_count,
        **{f"{key}_count": value for key, value in outcomes.items()},
        "false_start_count": false_starts,
        "accuracy": safe_ratio(outcomes["hit"] + outcomes["correct_rejection"], len(rows)),
        "omission_rate": safe_ratio(outcomes["omission"], go_count),
        "commission_rate": safe_ratio(outcomes["commission"], no_go_count),
        "false_start_rate": safe_ratio(false_starts, len(rows)),
    }
    result.update(reaction_time_metrics(reaction_times))
    return result
