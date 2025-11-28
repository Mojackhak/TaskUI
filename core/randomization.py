from __future__ import annotations

import random
from typing import Dict, List


def weighted_sample(candidates: List[int], weights: List[float]) -> int:
    return random.choices(candidates, weights=weights, k=1)[0]


def normalize_weights(weights: List[float]) -> List[float]:
    total = sum(weights)
    if total <= 0:
        return [0.0 for _ in weights]
    return [w / total for w in weights]


def compute_go_ratio(go_digits: List[int], nogo_digits: List[int], digit_weights: Dict[int, float]) -> float:
    total_go = sum(max(digit_weights.get(d, 0.0), 0.0) for d in go_digits)
    total_nogo = sum(max(digit_weights.get(d, 0.0), 0.0) for d in nogo_digits)
    if total_go <= 0 or total_nogo <= 0:
        raise ValueError("Non-zero weights required for both Go and No-Go digits.")
    return total_go / (total_go + total_nogo)


def generate_trial_schedule(
    go_digits: List[int],
    nogo_digits: List[int],
    digit_weights: Dict[int, float],
    go_ratio: float,
    n_trials_per_block: int,
) -> List[Dict[str, object]]:
    overlap = set(go_digits) & set(nogo_digits)
    if overlap:
        raise ValueError("Digits cannot be both Go and No-Go: {}".format(sorted(overlap)))
    if not go_digits or not nogo_digits:
        raise ValueError("At least one Go digit and one No-Go digit are required.")
    n_go = int(round(n_trials_per_block * go_ratio))
    n_go = max(0, min(n_go, n_trials_per_block))
    n_nogo = n_trials_per_block - n_go

    go_candidates: List[int] = []
    go_weights: List[float] = []
    for d in go_digits:
        w = max(float(digit_weights.get(d, 1.0)), 0.0)
        if w > 0:
            go_candidates.append(d)
            go_weights.append(w)

    nogo_candidates: List[int] = []
    nogo_weights: List[float] = []
    for d in nogo_digits:
        w = max(float(digit_weights.get(d, 1.0)), 0.0)
        if w > 0:
            nogo_candidates.append(d)
            nogo_weights.append(w)

    if not go_candidates or not nogo_candidates:
        raise ValueError("Non-zero weights are required for Go and No-Go digits.")

    go_weights = normalize_weights(go_weights)
    nogo_weights = normalize_weights(nogo_weights)

    trials: List[Dict[str, object]] = []
    for _ in range(n_go):
        digit = weighted_sample(go_candidates, go_weights)
        trials.append({"digit": digit, "is_go": True})
    for _ in range(n_nogo):
        digit = weighted_sample(nogo_candidates, nogo_weights)
        trials.append({"digit": digit, "is_go": False})

    random.shuffle(trials)
    return trials
