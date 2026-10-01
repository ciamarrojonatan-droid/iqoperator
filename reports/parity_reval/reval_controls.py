"""Revalidacao H008 sob paridade - controles negativos (GBPUSD, EURGBP, USDJPY).

Paridade: DataLoader().load_csv, barras fechadas (drop_forming_bar, timeframe 300s),
DatetimeIndex UTC a partir da coluna time, BacktestEngine().run(df,
H008RegimeAdaptiveRouter(), payout=0.87, horizon_bars=1,
blocked_hours_utc=[5,8,12,21,23]).
Nao edita codigo-fonte; apenas gera JSONs em reports/parity_reval/.
"""
import json
import time
from collections import Counter
from pathlib import Path

import pandas as pd

from iq_regime_adaptive.pipeline.data_loader import DataLoader
from iq_regime_adaptive.backtest.engine import BacktestEngine
from iq_regime_adaptive.hypotheses.h008_regime_adaptive_router import H008RegimeAdaptiveRouter
from iq_regime_adaptive.feature_engine.regime_classifier import RegimeClassifier
from iq_regime_adaptive.feature_engine.parity import drop_forming_bar

ASSETS = [
    ("GBPUSD", "data/GBPUSD_M5_iq.csv"),
    ("EURGBP", "data/EURGBP_M5_iq.csv"),
    ("USDJPY", "data/USDJPY_M5_iq.csv"),
]

PAYOUT = 0.87
HORIZON = 1
BLOCKED = [5, 8, 12, 21, 23]
OUTDIR = Path("reports/parity_reval")
OUTDIR.mkdir(parents=True, exist_ok=True)


def run_asset(name: str, csv_path: str) -> dict:
    t_start = time.time()
    df_raw = DataLoader().load_csv(csv_path)
    n_full = len(df_raw)

    # Barras tratadas como fechadas (paridade live/backtest, M5 = 300s).
    df_closed, dropped = drop_forming_bar(df_raw, timeframe_sec=300)

    # Engine exige DatetimeIndex: monta da coluna time (UTC).
    df = df_closed.copy()
    df.index = pd.DatetimeIndex(pd.to_datetime(df["time"], utc=True))

    # Uma unica classificacao de regimes, reutilizada pelo router (cache, sem
    # editar fonte: o router chamaria classify_series de novo com o mesmo df).
    clf = RegimeClassifier()
    regime_series = clf.classify_series(df)
    _orig_classify = clf.classify_series
    clf.classify_series = lambda d: regime_series  # noqa: E731 - mesmo df
    router = H008RegimeAdaptiveRouter(classifier=clf)

    engine = BacktestEngine()
    result = engine.run(
        df, router, payout=PAYOUT, horizon_bars=HORIZON,
        blocked_hours_utc=BLOCKED,
    )
    clf.classify_series = _orig_classify

    veto_dist = dict(Counter(c["veto_code"] for c in result.candidates))
    regime_dist = {str(k): int(v) for k, v in regime_series.value_counts().items()}
    m = result.metrics

    out = {
        "ativo": name,
        "csv": csv_path,
        "hipotese": "H008RegimeAdaptiveRouter",
        "paridade": {
            "loader": "DataLoader().load_csv",
            "barras_fechadas": True,
            "forming_bar_descartada": bool(dropped),
            "datetime_index": "coluna time (UTC)",
            "payout": PAYOUT,
            "horizon_bars": HORIZON,
            "blocked_hours_utc": BLOCKED,
        },
        "subset": {"usou_tail": False, "tail_n": None, "motivo": None},
        "n_barras": int(n_full),
        "n_barras_usadas": int(len(df)),
        "n_candidates": int(len(result.candidates)),
        "n_trades": int(len(result.trades)),
        "vetoed": int(result.vetoed_signals_count),
        "purged": int(result.purged_signals_count),
        "winrate": float(m.nominal_win_rate),
        "ev": float(m.expected_value),
        "wilson_lb": float(m.wilson_lower_bound),
        "ev_wlb": float(m.ev_wlb),
        "breakeven_wr": float(m.breakeven_win_rate),
        "wins": int(m.wins),
        "losses": int(m.losses),
        "pushes": int(m.pushes),
        "veto_code_dist": veto_dist,
        "regime_dist": regime_dist,
        "elapsed_sec": round(time.time() - t_start, 1),
    }
    with open(OUTDIR / f"{name}.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False, default=str)
    return out


if __name__ == "__main__":
    for name, path in ASSETS:
        r = run_asset(name, path)
        print(f"{name}: barras={r['n_barras']} cand={r['n_candidates']} "
              f"trades={r['n_trades']} vetoed={r['vetoed']} "
              f"WR={r['winrate']:.4f} EV={r['ev']:.4f} "
              f"vetos={r['veto_code_dist']} regimes={r['regime_dist']} "
              f"({r['elapsed_sec']}s)")
