#!/usr/bin/env python3
"""compare_signal_parity.py - Compara sinais backtest vs live em nivel de SINAL.

Join key: (asset, signal_bar_time).

Entrada A (backtest): CSV de candidates com colunas
    t, signal_bar_time, direction, payout_t, veto_code
    (+ opcional: asset, regime). Se --candidates ausente/inexistente,
    gera candidates via H008RegimeAdaptiveRouter sobre --data
    (ex.: data/EURUSD_M5_iq.csv, com rename time->from) como fallback
    demonstrativo.

Entrada B (live): log com linhas [CHECK] contendo `regime=` e
    `-> call|put|None`, ex. (bot.py):
      [CHECK] EURUSD from:1782123600 close=1.14 H008 regime=RANGE src=... -> call (payout 0.85)
    --live-log pode nao existir: trata gracefully com aviso.

Saida: taxa de match, listas so-backtest / so-live, distribuicao de
regimes e veto_codes; impresso no stdout + CSV opcional via --out.

Uso:
    python scripts/compare_signal_parity.py --help
    python scripts/compare_signal_parity.py --data data/EURUSD_M5_iq.csv --limit 500
    python scripts/compare_signal_parity.py --candidates cands.csv --live-log bot.log --out parity.csv
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import warnings

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    print("ERRO: pandas nao instalado no ambiente.", file=sys.stderr)
    sys.exit(2)


# ---------------------------------------------------------------------------
# Entrada A: candidates do backtest
# ---------------------------------------------------------------------------

CANDIDATE_COLS = ["t", "signal_bar_time", "direction", "payout_t", "veto_code"]


def _norm_direction(v) -> str:
    s = str(v).strip().upper()
    if s in ("CALL", "C"):
        return "CALL"
    if s in ("PUT", "P"):
        return "PUT"
    if s in ("NONE", "NO_TRADE", "NO-TRADE", "NOTRADE", "NAN", "NONE", ""):
        return "NONE"
    return s  # preserva valor inesperado para diagnostico


def _norm_bar_time(v):
    """Normaliza signal_bar_time para int epoch quando possivel, senao str."""
    try:
        f = float(str(v).strip())
        return int(f)
    except (TypeError, ValueError):
        return str(v).strip()


def load_candidates_csv(path: str, default_asset: str) -> "pd.DataFrame":
    df = pd.read_csv(path)
    # tolera variacoes de caixa/espaco nos headers
    df.columns = [str(c).strip() for c in df.columns]
    lower = {c.lower(): c for c in df.columns}
    rename = {}
    for want in list(CANDIDATE_COLS) + ["asset", "regime"]:
        if want not in df.columns and want.lower() in lower:
            rename[lower[want.lower()]] = want
    if rename:
        df = df.rename(columns=rename)
    missing = [c for c in CANDIDATE_COLS if c not in df.columns]
    if missing:
        raise ValueError(
            f"CSV {path} sem colunas obrigatorias {missing}. "
            f"Colunas encontradas: {list(df.columns)}"
        )
    if "asset" not in df.columns:
        df["asset"] = default_asset
    if "regime" not in df.columns:
        df["regime"] = "?"
    df["asset"] = df["asset"].astype(str).str.strip()
    df["direction"] = df["direction"].apply(_norm_direction)
    df["signal_bar_time"] = df["signal_bar_time"].apply(_norm_bar_time)
    df["veto_code"] = df["veto_code"].fillna("").astype(str)
    return df


def generate_candidates_fallback(
    data_path: str, asset: str, payout: float, limit: int | None = None
) -> "pd.DataFrame":
    """Fallback demonstrativo: roda H008RegimeAdaptiveRouter sobre --data.

    data/EURUSD_M5_iq.csv tem colunas time,open,high,low,close; o bot usa
    'from' como chave de candle, entao faz rename time->from quando 'from'
    ausente (apenas demonstrativo; o router exige open/high/low/close).
    """
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    try:
        from iq_regime_adaptive.hypotheses.h008_regime_adaptive_router import (
            H008RegimeAdaptiveRouter,
        )
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"Falha ao importar H008RegimeAdaptiveRouter: {exc}")

    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Arquivo de dados nao encontrado: {data_path}")
    df = pd.read_csv(data_path)
    if limit is not None and limit > 0:
        df = df.head(limit).copy()
    # rename time->from demonstrativo (chave de candle do bot)
    if "from" not in df.columns and "time" in df.columns:
        df["from"] = df["time"]
    router = H008RegimeAdaptiveRouter()
    signals = router.generate_signals(df, payout=payout)
    try:
        regimes = router.classifier.classify_series(df)
        regime_list = list(regimes)
    except Exception:
        regime_list = ["?"] * len(df)
    time_col = "from" if "from" in df.columns else ("time" if "time" in df.columns else None)

    rows = []
    n_vetoed_chaos = 0
    for i in range(len(df)):
        sig = str(signals.iloc[i]).strip().upper()
        reg = str(regime_list[i]).strip().upper() if i < len(regime_list) else "?"
        # valor do enum pode vir como 'MarketRegime.CHAOS'; extrai sufixo
        reg = reg.split(".")[-1]
        if reg == "CHAOS":
            n_vetoed_chaos += 1
        if sig not in ("CALL", "PUT"):
            continue
        bt = _norm_bar_time(df[time_col].iloc[i]) if time_col else i
        rows.append(
            {
                "t": bt,
                "signal_bar_time": bt,
                "asset": asset,
                "direction": sig,
                "payout_t": payout,
                "veto_code": "PASS",
                "regime": reg,
            }
        )
    out = pd.DataFrame(rows, columns=CANDIDATE_COLS + ["asset", "regime"])
    out.attrs["n_vetoed_chaos"] = n_vetoed_chaos
    out.attrs["n_bars"] = len(df)
    return out


# ---------------------------------------------------------------------------
# Entrada B: live log ([CHECK])
# ---------------------------------------------------------------------------

# Ex.: [CHECK] EURUSD from:1782123600 close=1.14 H008 regime=RANGE src=api -> call (payout 0.85)
CHECK_RE = re.compile(
    r"\[CHECK\]\s+(?P<asset>\S+)\s+(?P<candle_key>\S+)\s+"
    r"(?P<detail>.*?regime=(?P<regime>\S+).*?)\->\s*(?P<signal>\S+)",
    re.IGNORECASE,
)


def parse_live_log(path: str) -> "pd.DataFrame":
    """Parseia linhas [CHECK] -> DataFrame(asset, signal_bar_time, direction, regime, raw)."""
    rows = []
    n_check_total = 0
    n_unjoinable = 0
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "[CHECK]" not in line:
                continue
            m = CHECK_RE.search(line)
            if not m:
                continue
            n_check_total += 1
            asset = m.group("asset").strip()
            ckey = m.group("candle_key").strip()
            regime = m.group("regime").strip().rstrip(",;:)").upper()
            sig_raw = m.group("signal").strip().rstrip(",;:)").lower()
            if sig_raw in ("call",):
                direction = "CALL"
            elif sig_raw in ("put",):
                direction = "PUT"
            else:  # None / no_trade / outros
                direction = "NONE"
            # candle_key formato col:valor (ex. from:1782123600)
            if ":" in ckey:
                _, _, val = ckey.partition(":")
                bar_time = _norm_bar_time(val)
            else:
                bar_time = None
                n_unjoinable += 1
            rows.append(
                {
                    "asset": asset,
                    "signal_bar_time": bar_time,
                    "direction": direction,
                    "regime": regime,
                    "raw": line.strip()[:300],
                }
            )
    df = pd.DataFrame(rows, columns=["asset", "signal_bar_time", "direction", "regime", "raw"])
    df.attrs["n_check_total"] = n_check_total
    df.attrs["n_unjoinable"] = n_unjoinable
    return df


# ---------------------------------------------------------------------------
# Comparacao
# ---------------------------------------------------------------------------

def compare(backtest: "pd.DataFrame", live: "pd.DataFrame | None"):
    bt = backtest.copy()
    # so sinais acionaveis no backtest (candidates ja sao CALL/PUT; filtra por seguranca)
    bt_sig = bt[bt["direction"].isin(["CALL", "PUT"])].copy()
    bt_sig["_key"] = bt_sig["asset"].astype(str) + "|" + bt_sig["signal_bar_time"].astype(str)

    result = {
        "n_backtest_total": len(bt),
        "n_backtest_signals": len(bt_sig),
        "bt_keys": set(bt_sig["_key"].tolist()),
        "bt_by_key": {r["_key"]: r for r in bt_sig.to_dict("records")},
    }
    if live is None or len(live) == 0:
        result.update({"live": None})
        return result

    lv = live.copy()
    lv_joinable = lv[lv["signal_bar_time"].notna()].copy()
    lv_joinable["_key"] = (
        lv_joinable["asset"].astype(str) + "|" + lv_joinable["signal_bar_time"].astype(str)
    )
    # propaga _key ao frame completo (None p/ linhas nao-joineaveis) p/ build_output_table
    lv["_key"] = lv["asset"].astype(str) + "|" + lv["signal_bar_time"].astype(str)
    lv.loc[lv["signal_bar_time"].isna(), "_key"] = None
    lv_sig = lv_joinable[lv_joinable["direction"].isin(["CALL", "PUT"])].copy()
    live_keys_all = set(lv_joinable["_key"].tolist())
    live_keys_sig = set(lv_sig["_key"].tolist())

    bt_keys = result["bt_keys"]
    # match em nivel de SINAL: mesma chave E mesma direcao (apenas sinais acionaveis)
    bt_dir = {k: v["direction"] for k, v in result["bt_by_key"].items()}
    lv_dir = {r["_key"]: r["direction"] for r in lv_sig.to_dict("records")}
    common_keys = bt_keys & live_keys_sig
    match_keys = {k for k in common_keys if bt_dir.get(k) == lv_dir.get(k)}
    conflict_keys = {k for k in common_keys if bt_dir.get(k) != lv_dir.get(k)}

    union_keys = bt_keys | live_keys_sig
    result.update(
        {
            "live": lv,
            "n_live_total": len(lv),
            "n_live_joinable": len(lv_joinable),
            "n_live_signals": len(lv_sig),
            "n_live_unjoinable": int(lv["signal_bar_time"].isna().sum()),
            "live_keys_all": live_keys_all,
            "live_keys_sig": live_keys_sig,
            "match_keys": match_keys,
            "conflict_keys": conflict_keys,
            "only_bt_keys": bt_keys - live_keys_all,  # ausente no live (qualquer direcao)
            "only_live_keys": live_keys_sig - bt_keys,  # ausente no backtest
            "union_keys": union_keys,
            "match_rate_union": (len(match_keys) / len(union_keys) if union_keys else float("nan")),
            "match_rate_vs_backtest": (
                len(match_keys) / len(bt_keys) if bt_keys else float("nan")
            ),
            "match_rate_vs_live": (
                len(match_keys) / len(live_keys_sig) if live_keys_sig else float("nan")
            ),
        }
    )
    return result


def _dist(series) -> dict:
    return series.fillna("?").astype(str).value_counts().to_dict()


def report(cmp: dict, backtest: "pd.DataFrame", live, verbose_lists: int = 20):
    L = []
    L.append("=== PARIDADE DE SINAIS backtest x live ===")
    L.append(f"backtest: {cmp['n_backtest_total']} linhas ({cmp['n_backtest_signals']} CALL/PUT)")
    L.append(f"  regimes(backtest): {_dist(backtest.get('regime', pd.Series(['?'])))}")
    if "veto_code" in backtest.columns:
        L.append(f"  veto_codes(backtest): {_dist(backtest['veto_code'])}")
    if backtest.attrs.get("n_bars") is not None:
        L.append(
            f"  (fallback: {backtest.attrs['n_bars']} candles, "
            f"{backtest.attrs.get('n_vetoed_chaos', '?')} barras CHAOS vetadas)"
        )
    if cmp.get("live") is None:
        L.append("live: AUSENTE (sem --live-log ou vazio) — parity N/A.")
        return "\n".join(L)
    n_u = cmp["live"].attrs.get("n_unjoinable", cmp["n_live_unjoinable"])
    L.append(
        f"live: {cmp['n_live_total']} linhas [CHECK] "
        f"({cmp['n_live_signals']} CALL/PUT joinable; {n_u} sem chave joineavel)"
    )
    L.append(f"  regimes(live): {_dist(cmp['live']['regime'])}")
    L.append(f"  direcoes(live): {_dist(cmp['live']['direction'])}")
    L.append(f"chaves backtest(CALL/PUT): {len(cmp['bt_keys'])} | live(CALL/PUT): {len(cmp['live_keys_sig'])}")
    L.append(f"matches (mesma chave + mesma direcao): {len(cmp['match_keys'])}")
    L.append(f"conflitos (mesma chave, direcao diferente): {len(cmp['conflict_keys'])}")
    L.append(f"match/union (Jaccard): {cmp['match_rate_union']:.3f}")
    L.append(f"match/backtest: {cmp['match_rate_vs_backtest']:.3f}")
    L.append(f"match/live:     {cmp['match_rate_vs_live']:.3f}")
    only_bt = sorted(cmp["only_bt_keys"])
    only_lv = sorted(cmp["only_live_keys"])
    L.append(f"so-backtest ({len(only_bt)}): {only_bt[:verbose_lists]}{'...' if len(only_bt) > verbose_lists else ''}")
    L.append(f"so-live ({len(only_lv)}): {only_lv[:verbose_lists]}{'...' if len(only_lv) > verbose_lists else ''}")
    if cmp["conflict_keys"]:
        conf = sorted(cmp["conflict_keys"])[:verbose_lists]
        L.append(f"conflitos: {conf}")
    return "\n".join(L)


def build_output_table(cmp: dict) -> "pd.DataFrame | None":
    if cmp.get("live") is None:
        return None
    rows = []
    for k in sorted(cmp["union_keys"]):
        b = cmp["bt_by_key"].get(k)
        asset, _, bt_time = k.partition("|")
        lrows = cmp["live"]
        lm = lrows[lrows["_key"] == k]
        ldir = lm["direction"].iloc[0] if len(lm) else None
        lreg = lm["regime"].iloc[0] if len(lm) else None
        if k in cmp["match_keys"]:
            status = "MATCH"
        elif k in cmp["conflict_keys"]:
            status = "CONFLICT"
        elif k in cmp["only_bt_keys"]:
            status = "ONLY_BACKTEST"
        else:
            status = "ONLY_LIVE"
        rows.append(
            {
                "asset": asset,
                "signal_bar_time": bt_time,
                "backtest_direction": b["direction"] if b else None,
                "backtest_regime": b.get("regime") if b else None,
                "backtest_veto": b.get("veto_code") if b else None,
                "live_direction": ldir,
                "live_regime": lreg,
                "status": status,
            }
        )
    return pd.DataFrame(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Compara sinais backtest (candidates CSV ou fallback H008) vs live ([CHECK] log) "
        "com join em (asset, signal_bar_time)."
    )
    ap.add_argument("--candidates", default=None,
                    help="CSV de candidates do backtest (t,signal_bar_time,direction,payout_t,veto_code). "
                         "Se ausente/inexistente, gera via H008 sobre --data (fallback).")
    ap.add_argument("--live-log", default=None,
                    help="Arquivo de log live com linhas [CHECK] (regime=... -> call|put|None). "
                         "Se ausente, analisa so o backtest com aviso.")
    ap.add_argument("--data", default=os.path.join("data", "EURUSD_M5_iq.csv"),
                    help="CSV OHLC para fallback H008 (default: data/EURUSD_M5_iq.csv).")
    ap.add_argument("--asset", default="EURUSD", help="Ativo default (default: EURUSD).")
    ap.add_argument("--payout", type=float, default=0.85, help="Payout do fallback H008 (default: 0.85).")
    ap.add_argument("--limit", type=int, default=None,
                    help="Limita N primeiros candles/linhas no fallback (demo rapida).")
    ap.add_argument("--out", default=None, help="CSV opcional com tabela joineada (coluna status).")
    ap.add_argument("--show", type=int, default=20,
                    help="N max de chaves listadas no relatorio (default: 20).")
    args = ap.parse_args(argv)

    # ---- Entrada A ----
    if args.candidates and os.path.exists(args.candidates):
        print(f"[A] candidates: {args.candidates}")
        try:
            backtest = load_candidates_csv(args.candidates, args.asset)
        except Exception as exc:
            print(f"ERRO ao ler candidates: {exc}", file=sys.stderr)
            return 2
    else:
        if args.candidates:
            warnings.warn(f"--candidates '{args.candidates}' nao encontrado; usando fallback H008.")
            print(f"AVISO: --candidates '{args.candidates}' nao encontrado; usando fallback H008.")
        else:
            print("[A] sem --candidates; usando fallback H008 (demonstrativo).")
        print(f"[A] fallback: H008 sobre {args.data} (asset={args.asset}, payout={args.payout}, "
              f"limit={args.limit}) — rename time->from quando aplicavel.")
        try:
            backtest = generate_candidates_fallback(args.data, args.asset, args.payout, args.limit)
        except Exception as exc:
            print(f"ERRO no fallback H008: {exc}", file=sys.stderr)
            return 2

    # ---- Entrada B ----
    live = None
    if args.live_log:
        if os.path.exists(args.live_log):
            print(f"[B] live-log: {args.live_log}")
            try:
                live = parse_live_log(args.live_log)
            except Exception as exc:
                print(f"AVISO: falha ao parsear live-log ({exc}); seguindo sem live.")
                live = None
        else:
            warnings.warn(f"--live-log '{args.live_log}' nao encontrado; seguindo sem live.")
            print(f"AVISO: --live-log '{args.live_log}' nao encontrado; seguindo sem live.")
    else:
        print("AVISO: --live-log nao informado; paridade live N/A (analise so-backtest).")

    cmp = compare(backtest, live)
    print(report(cmp, backtest, live, verbose_lists=args.show))

    if args.out:
        tbl = build_output_table(cmp)
        if tbl is None:
            print(f"(--out ignorado: sem live, nada para joinear; backtest tem {len(backtest)} linhas.)")
        else:
            tbl.to_csv(args.out, index=False)
            print(f"Tabela joineada salva em: {args.out} ({len(tbl)} linhas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
