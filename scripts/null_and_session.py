"""null_and_session.py - Modelo nulo (binomial exato + Monte Carlo) e análise
condicional por sessão UTC com N poolado (6 ativos x H008).

Sem pré-registro além do óbvio: se H008 ~= moeda, fecha-se o capítulo M5.
Sessão só interessa se alguma hora tiver WLB > breakeven com N>=100.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = [
    "data/EURUSD_M5_iq.csv",
    "data/AUDUSD_M5_iq.csv",
    "data/USDCAD_M5_iq.csv",
    "data/GBPUSD_M5_iq.csv",
    "data/EURGBP_M5_iq.csv",
    "data/USDJPY_M5_iq.csv",
]
PAYOUT = 0.85
BE = 1.0 / (1.0 + PAYOUT)

# --- Parte A: OOS original EURUSD: 12W/6L/1P em 19 (12/18 = 66.67%) ---
WINS, N_DECISIVE = 12, 18


def binom_sf(k, n, p):
    return sum(
        math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i)) for i in range(k, n + 1)
    )


p_single = binom_sf(WINS, N_DECISIVE, BE)
# Correção conservadora por múltiplos testes: 8 hipóteses x 6 ativos = 48 looks.
N_LOOKS = 8 * 6
p_family = 1.0 - (1.0 - p_single) ** N_LOOKS

# Monte Carlo: distribuição de max-WR sob H0 em 48 looks.
rng = np.random.default_rng(42)
sims = 20000
best = np.max(
    rng.binomial(N_DECISIVE, BE, size=(sims, N_LOOKS)) / N_DECISIVE, axis=1
)
mc_p = float(np.mean(best >= WINS / N_DECISIVE))

null_out = {
    "oos_wins": WINS,
    "oos_decisive": N_DECISIVE,
    "breakeven": round(BE, 4),
    "p_single_vs_breakeven": round(p_single, 4),
    "p_familywise_48_looks": round(p_family, 4),
    "mc_familywise": round(mc_p, 4),
}
print("NULL:", json.dumps(null_out))

# --- Parte B: sessão poolada ---
sys.path.insert(0, str(ROOT))
from iq_regime_adaptive.hypotheses.h008_regime_adaptive_router import (
    H008RegimeAdaptiveRouter,
)

router = H008RegimeAdaptiveRouter()
per_hour = {h: {"n": 0, "wins": 0} for h in range(24)}
total_sig = 0
for f in DATA:
    df = pd.read_csv(ROOT / f)
    if "from" not in df.columns and "time" in df.columns:
        df = df.rename(columns={"time": "from"})
    sig = router.generate_signals(df, payout=PAYOUT)
    close = df["close"].to_numpy()
    ts = pd.to_datetime(df["from"].to_numpy(), unit="s", utc=True)
    idx = np.where(sig.to_numpy() != "NO_TRADE")[0]
    idx = idx[idx < len(df) - 1]  # precisa da barra seguinte (fechada)
    total_sig += len(idx)
    for t in idx:
        d = 1 if sig.iloc[t] == "CALL" else -1
        win = int(np.sign(close[t + 1] - close[t]) == d)
        h = int(ts[t].hour)
        per_hour[h]["n"] += 1
        per_hour[h]["wins"] += win

rows = []
for h in range(24):
    n = per_hour[h]["n"]
    w = per_hour[h]["wins"]
    wr = w / n if n else 0.0
    ev = wr * PAYOUT - (1 - wr) if n else 0.0
    # Wilson lower bound 95%
    if n:
        z = 1.96
        den = 1 + z * z / n
        c = wr + z * z / (2 * n)
        m = z * math.sqrt(wr * (1 - wr) / n + z * z / (4 * n * n))
        wlb = (c - m) / den
    else:
        wlb = 0.0
    rows.append(
        {"hour": h, "n": n, "wins": w, "wr": round(wr, 3),
         "ev": round(ev, 3), "wlb": round(wlb, 3)}
    )

out = {"null_model": null_out, "total_signals": total_sig,
       "payout": PAYOUT, "per_hour": rows}
Path("reports/null_session").mkdir(parents=True, exist_ok=True)
json.dump(out, open("reports/null_session/analysis.json", "w"), indent=1)
top = sorted(rows, key=lambda r: r["wr"], reverse=True)[:5]
print("TOTAL_SIG:", total_sig)
print("TOP_HOURS:", json.dumps(top))
print("BOTTOM:", json.dumps(sorted(rows, key=lambda r: r["wr"])[:3]))
