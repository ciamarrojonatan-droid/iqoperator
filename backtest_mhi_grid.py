"""
Grid Search de Backtest para Estrategia Probabilistica MHI 1 em M1.

Interpola dados M5 -> M1 (~525k candles), varre 5 dimensoes de configuracao
(EMA trend, require_trend, payout, kelly_fraction, kelly_max_risk),
e valida cada combinacao com split 50/50 anti-ilusao.

Uso:
  python backtest_mhi_grid.py
  python backtest_mhi_grid.py --csv data/BTCUSDT_M5_2024y.csv --balance 100
"""
import argparse
import csv
import math
import os
import sys
import time
from collections import deque
from itertools import product

from kelly import kelly_fraction_stake


# --- Interpolacao M5 -> M1 ---

def load_m5_csv(path: str) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        for r in rd:
            try:
                rows.append({
                    "time": float(r["time"]),
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                })
            except (ValueError, TypeError, KeyError):
                continue
    return rows


def interpolate_m5_to_m1(m5_rows: list[dict]) -> list[dict]:
    """
    Interpola cada candle M5 em 5 candles M1, preservando OHLC e gerando
    cores variadas (altern?ncia natural de verde/vermelho dentro do bloco).
    """
    m1: list[dict] = []
    for row in m5_rows:
        ts = int(row["time"])
        o5 = row["open"]
        h5 = row["high"]
        l5 = row["low"]
        c5 = row["close"]
        rng = max(h5 - l5, 0.0001)

        # Gera 5 pontos de refer?ncia entre open e close
        refs = [o5 + (c5 - o5) * k / 5 for k in range(6)]  # 6 pontos, 5 intervalos

        for j in range(5):
            sub_o = refs[j]
            sub_c = refs[j + 1]
            # Altern?ncia de micro-ru?do para gerar velas verdes/vermelhas variadas
            noise = rng * 0.04 * ((-1) ** j)
            sub_c += noise * 0.3
            sub_h = max(sub_o, sub_c) + abs(noise) * 0.4
            sub_l = min(sub_o, sub_c) - abs(noise) * 0.4
            # Clampar ao range original
            sub_h = min(sub_h, h5 + rng * 0.01)
            sub_l = max(sub_l, l5 - rng * 0.01)
            m1.append({
                "time": ts + j * 60,
                "open": round(sub_o, 6),
                "high": round(sub_h, 6),
                "low": round(sub_l, 6),
                "close": round(sub_c, 6),
            })
    return m1


# --- Motor de Simulacao MHI 1 -----------------------------------------------

def ema_list(closes: list[float], span: int) -> list[float]:
    k = 2.0 / (span + 1)
    out = [closes[0]]
    for c in closes[1:]:
        out.append(c * k + out[-1] * (1 - k))
    return out


def simulate_mhi(
    candles: list[dict],
    balance: float,
    payout: float,
    ema_period: int,
    require_trend: bool,
    kelly_fraction: float,
    kelly_max_risk: float,
    prior: float = 0.55,
    min_stake: float = 1.0,
    lookback: int = 50,
    prior_weight: float = 20.0,
) -> dict:
    """
    Backtest offline da estrat?gia MHI 1 em M1.
    Retorna m?tricas de performance.
    """
    closes = [c["close"] for c in candles]
    opens = [c["open"] for c in candles]
    timestamps = [int(c["time"]) for c in candles]

    # Pr?-computar EMA
    ema = ema_list(closes, ema_period) if require_trend else None

    bal = balance
    peak = balance
    max_dd = 0.0
    history: deque = deque(maxlen=lookback)
    wins = losses = ties = 0

    for i in range(4, len(candles) - 1):
        ts = timestamps[i]
        minute_mod = (ts // 60) % 5

        # S? processa no final do quadrante (Vela 5: minuto % 5 == 4)
        if minute_mod != 4:
            continue

        # Analisar cores das ?ltimas 3 velas (Velas 3, 4, 5)
        colors = []
        valid = True
        for k in range(i - 2, i + 1):
            o = opens[k]
            c = closes[k]
            if c > o:
                colors.append("green")
            elif c < o:
                colors.append("red")
            else:
                valid = False
                break  # Anti-Doji

        if not valid or len(colors) != 3:
            continue

        greens = colors.count("green")
        reds = colors.count("red")

        if greens > reds:
            signal = "put"
        elif reds > greens:
            signal = "call"
        else:
            continue

        # Filtro de micro-tend?ncia EMA
        if require_trend and ema is not None and i < len(ema):
            last_close = closes[i]
            last_ema = ema[i]
            if signal == "call" and last_close <= last_ema:
                continue
            if signal == "put" and last_close >= last_ema:
                continue

        # Kelly stake
        n = len(history)
        p = (prior * prior_weight + sum(1 for w in history if w)) / (prior_weight + n) if n else prior
        stake, kfull = kelly_fraction_stake(bal, payout, p, kelly_fraction, kelly_max_risk, min_stake)

        # Resultado: comparar close[i] com close[i+1] (expira??o 1m)
        entry = closes[i]
        nxt = closes[i + 1]

        if nxt == entry:
            ties += 1
            profit = 0.0
            won = None
        elif (signal == "call" and nxt > entry) or (signal == "put" and nxt < entry):
            wins += 1
            won = True
            profit = stake * payout
        else:
            losses += 1
            won = False
            profit = -stake

        bal += profit
        if won is not None:
            history.append(won)
        peak = max(peak, bal)
        dd = (peak - bal) / peak if peak > 0 else 0
        max_dd = max(max_dd, dd)

        if bal <= 0:
            break

    tot = wins + losses
    return {
        "trades": tot,
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "winrate": wins / tot if tot else 0.0,
        "start": balance,
        "end": round(bal, 2),
        "profit": round(bal - balance, 2),
        "roi": (bal - balance) / balance if balance else 0.0,
        "max_dd": round(max_dd, 4),
    }


# --- Grid Search Engine -----------------------------------------------------

GRID = {
    "ema": [50, 100, 150, 200],
    "require_trend": [True, False],
    "payout": [0.80, 0.85, 0.87],
    "kelly_fraction": [0.15, 0.25, 0.35],
    "kelly_max_risk": [0.01, 0.02, 0.03],
}


def run_grid(candles: list[dict], balance: float, out_csv: str):
    total_combos = 1
    for v in GRID.values():
        total_combos *= len(v)

    mid = len(candles) // 2
    half1 = candles[:mid]
    half2 = candles[mid:]

    results = []
    done = 0
    t0 = time.time()

    keys = list(GRID.keys())
    for combo in product(*GRID.values()):
        params = dict(zip(keys, combo))
        done += 1

        sim_args = dict(
            balance=balance,
            payout=params["payout"],
            ema_period=params["ema"],
            require_trend=params["require_trend"],
            kelly_fraction=params["kelly_fraction"],
            kelly_max_risk=params["kelly_max_risk"],
        )

        r_total = simulate_mhi(candles, **sim_args)
        r_h1 = simulate_mhi(half1, **sim_args)
        r_h2 = simulate_mhi(half2, **sim_args)

        validated = r_h1["profit"] > 0 and r_h2["profit"] > 0

        row = {
            "ema": params["ema"],
            "require_trend": params["require_trend"],
            "payout": params["payout"],
            "kelly_frac": params["kelly_fraction"],
            "kelly_risk": params["kelly_max_risk"],
            "trades": r_total["trades"],
            "wins": r_total["wins"],
            "losses": r_total["losses"],
            "winrate": round(r_total["winrate"], 4),
            "profit": r_total["profit"],
            "roi": round(r_total["roi"], 4),
            "max_dd": r_total["max_dd"],
            "profit_1h": r_h1["profit"],
            "profit_2h": r_h2["profit"],
            "wr_1h": round(r_h1["winrate"], 4),
            "wr_2h": round(r_h2["winrate"], 4),
            "validated": validated,
        }
        results.append(row)

        if done % 20 == 0 or done == total_combos:
            elapsed = time.time() - t0
            rate = done / elapsed if elapsed > 0 else 0
            eta = (total_combos - done) / rate if rate > 0 else 0
            print(f"  [{done}/{total_combos}] {elapsed:.0f}s elapsed, ~{eta:.0f}s ETA", flush=True)

    # Ordenar por lucro descendente
    results.sort(key=lambda r: r["profit"], reverse=True)

    # Exportar CSV
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)

    return results


def print_results(results: list[dict], balance: float):
    validated = [r for r in results if r["validated"]]
    invalid = [r for r in results if not r["validated"]]

    print(f"\n{'='*90}")
    print(f"  GRID SEARCH MHI 1 ? RESULTADOS COMPLETOS")
    print(f"{'='*90}")
    print(f"  Total de combinacoes: {len(results)}")
    print(f"  Validadas (lucro > 0 em ambas metades): {len(validated)}")
    print(f"  Descartadas (overfitting): {len(invalid)}")

    if validated:
        print(f"\n{'-'*90}")
        print(f"  TOP 10 COMBINA??ES VALIDADAS (por Lucro)")
        print(f"{'-'*90}")
        header = (f"{'#':>2} {'EMA':>4} {'Trend':>5} {'Pay':>4} {'KFrac':>5} "
                  f"{'KRisk':>5} {'Trades':>6} {'WR':>6} {'Profit':>9} "
                  f"{'ROI':>7} {'MaxDD':>6} {'P_1H':>8} {'P_2H':>8}")
        print(header)
        print("-" * 90)

        for i, r in enumerate(validated[:10], 1):
            trend_str = "Y" if r["require_trend"] else "N"
            print(f"{i:>2} {r['ema']:>4} {trend_str:>5} {r['payout']:>4} "
                  f"{r['kelly_frac']:>5} {r['kelly_risk']:>5} "
                  f"{r['trades']:>6} {r['winrate']:>6.2%} "
                  f"{r['profit']:>+9.2f} {r['roi']:>+7.2%} "
                  f"{r['max_dd']:>6.2%} {r['profit_1h']:>+8.2f} "
                  f"{r['profit_2h']:>+8.2f}")

        # Veredito da melhor
        best = validated[0]
        print(f"\n{'='*90}")
        print(f"  MELHOR CONFIGURA??O VALIDADA")
        print(f"{'='*90}")
        print(f"  EMA Trend:      {best['ema']}")
        print(f"  Require Trend:  {best['require_trend']}")
        print(f"  Payout:         {best['payout']}")
        print(f"  Kelly Fraction: {best['kelly_frac']}")
        print(f"  Kelly Max Risk: {best['kelly_risk']}")
        print(f"  Trades:         {best['trades']}")
        print(f"  Winrate:        {best['winrate']:.2%}")
        print(f"  Lucro:          {best['profit']:+.2f}")
        print(f"  ROI:            {best['roi']:+.2%}")
        print(f"  Max Drawdown:   {best['max_dd']:.2%}")

        # Anti-ilusao checklist
        be = 1 / (1 + best["payout"])
        n = best["trades"]
        wr = best["winrate"]
        se = math.sqrt(wr * (1 - wr) / n) if n else 1.0
        lower = wr - 1.96 * se

        print(f"\n  [VEREDITO ANTI-ILUS?O]")
        checks = [
            (f"  trades >= 200 ({n})", n >= 200),
            (f"  WR inf.95% {lower:.2%} > breakeven {be:.2%}", lower > be),
            (f"  lucro 1? metade > 0 ({best['profit_1h']:+.2f})", best["profit_1h"] > 0),
            (f"  lucro 2? metade > 0 ({best['profit_2h']:+.2f})", best["profit_2h"] > 0),
        ]
        all_ok = True
        for label, ok in checks:
            print(f"    {'PASS' if ok else 'FAIL'}  {label}")
            all_ok = all_ok and ok
        print(f"    => {'EDGE VALIDADO OK' if all_ok else 'SEM EDGE (nao opera real) X'}")

        # Sugest?o de .env
        print(f"\n  [CONFIGURA??O .ENV SUGERIDA]")
        print(f"  STRATEGY=mhi_1")
        print(f"  IQ_TIMEFRAME=60")
        print(f"  IQ_EXPIRATION=1")
        print(f"  IQ_MHI_TREND_EMA={best['ema']}")
        print(f"  IQ_MHI_REQUIRE_TREND={'1' if best['require_trend'] else '0'}")
        print(f"  KELLY_FRACTION={best['kelly_frac']}")
        print(f"  KELLY_MAX_RISK={best['kelly_risk']}")
    else:
        print("\n  [!] Nenhuma combinacao passou na valida??o anti-ilusao split 50/50.")
        print("  Considere ampliar os ranges do grid ou usar dados M1 reais.")


def load_m1_csv(path: str) -> list[dict]:
    """Load a CSV with M1 candles directly (time,open,high,low,close)."""
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        for r in rd:
            try:
                rows.append({
                    "time": float(r["time"]),
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                })
            except (ValueError, TypeError, KeyError):
                continue
    return rows


def main():
    ap = argparse.ArgumentParser(description="Grid Search MHI 1 Backtest")
    ap.add_argument("--csv", default="",
                     help="CSV de candles M5 para interpolar em M1")
    ap.add_argument("--m1", default="data/BTCUSDT_M1_90d.csv",
                     help="CSV de candles M1 reais (pula interpolacao)")
    ap.add_argument("--balance", type=float, default=1000.0)
    ap.add_argument("--out", default="data/mhi_grid_results.csv")
    a = ap.parse_args()

    if a.csv:
        # Mode: M5 interpolation
        if not os.path.exists(a.csv):
            sys.exit(f"[ERRO] CSV nao encontrado: {a.csv}")
        print(f"[1/3] Carregando M5 de {a.csv}...")
        m5 = load_m5_csv(a.csv)
        print(f"       {len(m5)} candles M5 carregados.")
        print(f"[2/3] Interpolando M5 -> M1...")
        m1 = interpolate_m5_to_m1(m5)
        print(f"       {len(m1)} candles M1 gerados.")
    else:
        # Mode: direct M1
        if not os.path.exists(a.m1):
            sys.exit(f"[ERRO] CSV M1 nao encontrado: {a.m1}  (use fetch_binance_m1.py para baixar)")
        print(f"[1/2] Carregando M1 reais de {a.m1}...")
        m1 = load_m1_csv(a.m1)
        print(f"       {len(m1)} candles M1 carregados.")

    combos = len(list(product(*GRID.values())))
    print(f"[{'3/3' if a.csv else '2/2'}] Executando Grid Search ({combos} combinacoes)...")
    results = run_grid(m1, a.balance, a.out)

    print_results(results, a.balance)
    print(f"\n[OK] Resultados completos exportados para: {a.out}")


if __name__ == "__main__":
    main()

