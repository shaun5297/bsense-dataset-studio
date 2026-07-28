from __future__ import annotations

import hashlib


SART_SEQUENCE_SEEDS = {
    "sart-v1-A": 428_615,
    "sart-v1-B": 731_204,
    "sart-v1-C": 195_087,
    "sart-v1-D": 864_332,
    "sart-v1-E": 509_741,
    "sart-v1-F": 276_953,
    "sart-v1-G": 943_168,
    "sart-v1-H": 617_420,
}


def sequence_seed(sequence_set_id: str) -> int:
    try:
        return SART_SEQUENCE_SEEDS[sequence_set_id]
    except KeyError as exc:
        raise ValueError(f"未知 SART 序列集：{sequence_set_id}") from exc


def assign_sequence_set(
    participant_id: str,
    session_id: str,
    run_id: str,
) -> str:
    """Deterministic rotation across eight validated sequence candidates."""

    participant_key = hashlib.sha256(participant_id.strip().encode("utf-8")).digest()[0]
    session_number = _numeric_component(session_id)
    run_number = _numeric_component(run_id)
    sequence_ids = tuple(SART_SEQUENCE_SEEDS)
    index = (participant_key + session_number + run_number) % len(sequence_ids)
    return sequence_ids[index]


def _numeric_component(value: str) -> int:
    digits = "".join(character for character in value if character.isdigit())
    if digits:
        return int(digits)
    return hashlib.sha256(value.encode("utf-8")).digest()[0]
