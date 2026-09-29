"""
degradation.py - Out-of-Sample Performance Degradation & Model Stability Evaluator.

Formulations:
1. Delta EV:
   Delta EV = EV_IS - EV_OOS
2. Degradation Index (DI):
   DI = (EV_IS - EV_OOS) / max(|EV_IS|, eps)
3. Delta Win Rate (Delta WR):
   Delta WR = WR_IS - WR_OOS
4. Composite Stability Score (S_comp in [0, 100]):
   S_comp = 100 * [0.35 * psi_EV + 0.30 * psi_stat + 0.20 * psi_time + 0.15 * psi_DD]
5. Degradation Verdict Matrix:
   - DI <= 0.00: "ANTIFRAGILE" (PASS)
   - 0.00 < DI <= 0.25: "ROBUST" (PASS)
   - 0.25 < DI <= 0.50: "MODERATE_DECAY" (WARNING / CONDITIONAL)
   - 0.50 < DI <= 0.75: "SEVERE_DECAY" (REJECT)
   - DI > 0.75 or EV_OOS <= 0: "REJECTED" (REJECT)
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional, Union
import numpy as np

from iq_regime_adaptive.backtest.metrics import BacktestMetrics


@dataclass(frozen=True)
class DegradationReport:
    """Out-of-sample degradation and stability assessment report."""
    delta_ev: float
    degradation_index: float
    delta_wr: float
    stability_score: float
    verdict: str
    psi_ev: float
    psi_stat: float
    psi_time: float
    psi_dd: float
    is_metrics: Dict[str, Any]
    oos_metrics: Dict[str, Any]
    val_metrics: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converts report to dictionary representation."""
        return asdict(self)


def _extract_metric(source: Union[BacktestMetrics, Dict[str, Any]], key: str, default: float = 0.0) -> float:
    """Extracts a numeric metric from BacktestMetrics or a dictionary."""
    if isinstance(source, BacktestMetrics):
        return float(getattr(source, key, default))
    elif isinstance(source, dict):
        return float(source.get(key, default))
    return default


def compute_degradation(
    is_metrics: Union[BacktestMetrics, Dict[str, Any]],
    oos_metrics: Union[BacktestMetrics, Dict[str, Any]],
    val_metrics: Optional[Union[BacktestMetrics, Dict[str, Any]]] = None,
    eps: float = 1e-6,
) -> DegradationReport:
    """
    Computes mathematical degradation between In-Sample (IS) and Out-of-Sample (OOS) partitions.

    Args:
        is_metrics: Performance metrics on IS partition.
        oos_metrics: Performance metrics on OOS partition.
        val_metrics: Optional performance metrics on Validation partition.
        eps: Small epsilon preventing division by zero.

    Returns:
        DegradationReport containing Delta EV, DI, Delta WR, S_comp, and verdict.
    """
    ev_is = _extract_metric(is_metrics, "expected_value", 0.0)
    ev_oos = _extract_metric(oos_metrics, "expected_value", 0.0)

    wr_is = _extract_metric(is_metrics, "nominal_win_rate", 0.0)
    wr_oos = _extract_metric(oos_metrics, "nominal_win_rate", 0.0)

    wlb_oos = _extract_metric(oos_metrics, "wilson_lower_bound", 0.0)
    p_be = _extract_metric(oos_metrics, "breakeven_win_rate", 0.54054)

    max_dd_is = _extract_metric(is_metrics, "max_drawdown_pct", 0.0)
    max_dd_oos = _extract_metric(oos_metrics, "max_drawdown_pct", 0.0)

    # 1. Delta EV
    delta_ev = ev_is - ev_oos

    # 2. Degradation Index
    denom = max(abs(ev_is), eps)
    degradation_index = delta_ev / denom

    # 3. Delta Win Rate
    delta_wr = wr_is - wr_oos

    # 4. Composite Stability Score Components
    # 4.1 psi_EV: EV Retention Sub-Score
    ev_drop = max(0.0, ev_is - ev_oos)
    ev_scale = max(ev_is, eps)
    psi_ev = float(np.clip(1.0 - (ev_drop / ev_scale), 0.0, 1.0))

    # 4.2 psi_stat: Statistical Significance Margin
    if wlb_oos <= p_be:
        psi_stat = 0.0
    else:
        stat_denom = max(0.01, wr_is - p_be)
        psi_stat = float(np.clip((wlb_oos - p_be) / stat_denom, 0.0, 1.0))

    # 4.3 psi_time: Calendar Consistency
    # Check if monthly_consistency is reported
    psi_time = 1.0
    if isinstance(oos_metrics, BacktestMetrics) and oos_metrics.monthly_consistency != "N/A":
        mc = oos_metrics.monthly_consistency
        if "_OF_" in mc:
            parts = mc.split("_OF_")
            try:
                pos = float(parts[0])
                total = float(parts[1].split("_")[0])
                if total > 0:
                    psi_time = pos / total
            except (ValueError, IndexError):
                psi_time = 1.0
    elif isinstance(oos_metrics, dict) and "monthly_consistency" in oos_metrics:
        mc = str(oos_metrics["monthly_consistency"])
        if "_OF_" in mc:
            parts = mc.split("_OF_")
            try:
                pos = float(parts[0])
                total = float(parts[1].split("_")[0])
                if total > 0:
                    psi_time = pos / total
            except (ValueError, IndexError):
                psi_time = 1.0

    # 4.4 psi_DD: Drawdown Containment
    dd_increase = max(0.0, max_dd_oos - max_dd_is)
    dd_scale = max(max_dd_is, 0.05)
    psi_dd = float(np.clip(1.0 - (dd_increase / dd_scale), 0.0, 1.0))

    # Composite Score S_comp in [0, 100]
    raw_scomp = 100.0 * (
        0.35 * psi_ev
        + 0.30 * psi_stat
        + 0.20 * psi_time
        + 0.15 * psi_dd
    )
    stability_score = float(np.clip(raw_scomp, 0.0, 100.0))

    # 5. Verdict Classification
    if ev_oos <= 0.0 or degradation_index > 0.75:
        verdict = "REJECTED"
    elif degradation_index <= 0.0:
        verdict = "ANTIFRAGILE"
    elif degradation_index <= 0.25:
        verdict = "ROBUST"
    elif degradation_index <= 0.50:
        verdict = "MODERATE_DECAY"
    else:
        verdict = "SEVERE_DECAY"

    is_dict = is_metrics.to_dict() if isinstance(is_metrics, BacktestMetrics) else dict(is_metrics)
    oos_dict = oos_metrics.to_dict() if isinstance(oos_metrics, BacktestMetrics) else dict(oos_metrics)
    val_dict = val_metrics.to_dict() if isinstance(val_metrics, BacktestMetrics) else (dict(val_metrics) if val_metrics else None)

    return DegradationReport(
        delta_ev=float(delta_ev),
        degradation_index=float(degradation_index),
        delta_wr=float(delta_wr),
        stability_score=float(stability_score),
        verdict=verdict,
        psi_ev=float(psi_ev),
        psi_stat=float(psi_stat),
        psi_time=float(psi_time),
        psi_dd=float(psi_dd),
        is_metrics=is_dict,
        oos_metrics=oos_dict,
        val_metrics=val_dict,
    )
