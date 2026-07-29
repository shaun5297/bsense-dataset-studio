from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


REFERENCE_LABEL_VERSION = "reference-label-v1-provisional"


@dataclass(frozen=True)
class ReferenceLabel:
    reference_state_label: str
    reference_state_score: float
    reference_label_version: str
    reference_label_sources: tuple[str, ...]
    reference_label_confidence: str
    rationale: tuple[str, ...]
    provisional: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["reference_label_sources"] = list(self.reference_label_sources)
        payload["rationale"] = list(self.rationale)
        return payload


def generate_reference_label(
    context: Mapping[str, object],
    sart: Mapping[str, object],
    pvt: Mapping[str, object],
) -> ReferenceLabel:
    """Generate a conservative research label without using EEG-derived features."""

    signed_score = 0.0
    sources: list[str] = []
    rationale: list[str] = []

    kss = _number(context.get("kss_post_score") or context.get("kss_score"))
    if kss is not None:
        sources.append("kss_post" if context.get("kss_post_score") is not None else "kss_pre")
        if kss >= 7:
            signed_score += 2.0
            rationale.append("KSS≥7")
        elif kss <= 4:
            signed_score -= 2.0
            rationale.append("KSS≤4")

    pvt_trials = _number(pvt.get("valid_trial_count")) or 0
    pvt_lapse = _number(pvt.get("lapse_rate"))
    pvt_median = _number(pvt.get("median_reaction_time_s"))
    if pvt_trials >= 10 and pvt_lapse is not None and pvt_median is not None:
        sources.append("pvt")
        if pvt_lapse >= 0.20 or pvt_median >= 0.50:
            signed_score += 2.0
            rationale.append("PVT 警觉表现受损")
        elif pvt_lapse <= 0.10 and pvt_median <= 0.40:
            signed_score -= 2.0
            rationale.append("PVT 警觉表现稳定")

    practice_criterion_met = context.get("practice_criterion_met")
    sart_trials = _number(sart.get("valid_trial_count")) or 0
    omission = _number(sart.get("omission_rate"))
    commission = _number(sart.get("commission_rate"))
    if practice_criterion_met is False:
        rationale.append("SART 练习未达标，未作为标签来源")
    elif sart_trials >= 30 and omission is not None and commission is not None:
        sources.append("sart")
        if omission >= 0.10 or commission >= 0.25:
            signed_score += 1.0
            rationale.append("SART 错误率偏高")
        elif omission <= 0.03 and commission <= 0.10:
            signed_score -= 1.0
            rationale.append("SART 错误率较低")

    sleep = _number(context.get("sleep_duration_hours"))
    awake = _number(context.get("continuous_awake_hours"))
    if sleep is not None or awake is not None:
        sources.append("sleep_context")
        if (sleep is not None and sleep < 5) or (awake is not None and awake >= 18):
            signed_score += 1.0
            rationale.append("睡眠不足或连续清醒时间较长")
        elif (
            sleep is not None
            and sleep >= 7
            and awake is not None
            and awake < 16
        ):
            signed_score -= 1.0
            rationale.append("睡眠与连续清醒时长处于参考范围")

    independent_sources = len(set(sources))
    if independent_sources >= 2 and signed_score >= 3:
        label = "impaired"
    elif independent_sources >= 2 and signed_score <= -3:
        label = "alert"
    else:
        label = "uncertain"
    confidence = (
        "high"
        if independent_sources >= 4 and abs(signed_score) >= 4
        else "medium"
        if label != "uncertain" and independent_sources >= 2
        else "low"
    )
    risk_index = round(max(0.0, min(1.0, 0.5 + signed_score / 12.0)), 6)
    return ReferenceLabel(
        reference_state_label=label,
        reference_state_score=risk_index,
        reference_label_version=REFERENCE_LABEL_VERSION,
        reference_label_sources=tuple(dict.fromkeys(sources)),
        reference_label_confidence=confidence,
        rationale=tuple(rationale),
    )


def _number(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
