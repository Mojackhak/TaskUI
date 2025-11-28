from __future__ import annotations

from statistics import mean
from typing import Dict, Iterable, List, Optional


def _extract_trials(log: Dict) -> List[Dict]:
    blocks = log.get("timing_relative", {}).get("blocks", {})
    trials: List[Dict] = []
    if isinstance(blocks, dict):
        for block in blocks.values():
            block_trials = block.get("trials", [])
            if isinstance(block_trials, Iterable):
                trials.extend([t for t in block_trials if isinstance(t, dict)])
    return trials


def _compute_rt_seconds(trial: Dict) -> Optional[float]:
    times = trial.get("times")
    if not times or len(times) < 2:
        return None
    onset, response = times[0], times[1]
    if onset is None or response is None:
        return None
    try:
        return float(response) - float(onset)
    except (TypeError, ValueError):
        return None


def _safe_mean(values: Iterable[float]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return mean(vals)


def _percent(numerator: int, denominator: int) -> Optional[float]:
    if denominator <= 0:
        return None
    return (numerator / denominator) * 100.0


def compute_go_nogo_metrics(log: Dict) -> Dict[str, Optional[float]]:
    """
    Calculate hit/commission rates and reaction times from the Go/No-Go log structure.

    Returns a dict with:
    - go_hit_percent
    - nogo_commission_percent
    - mean_rt_go_hit (seconds)
    - mean_rt_nogo_commission (seconds)
    """
    trials = _extract_trials(log)
    go_trials = [t for t in trials if t.get("is_go_trial")]
    nogo_trials = [t for t in trials if not t.get("is_go_trial")]

    go_hits = [t for t in go_trials if t.get("outcome") == "hit"]
    nogo_commissions = [t for t in nogo_trials if t.get("outcome") == "commission_error"]

    go_hit_percent = _percent(len(go_hits), len(go_trials))
    nogo_commission_percent = _percent(len(nogo_commissions), len(nogo_trials))

    mean_rt_go_hit = _safe_mean(_compute_rt_seconds(t) for t in go_hits)
    mean_rt_nogo_commission = _safe_mean(_compute_rt_seconds(t) for t in nogo_commissions)

    return {
        "go_hit_percent": go_hit_percent,
        "nogo_commission_percent": nogo_commission_percent,
        "mean_rt_go_hit": mean_rt_go_hit,
        "mean_rt_nogo_commission": mean_rt_nogo_commission,
    }
