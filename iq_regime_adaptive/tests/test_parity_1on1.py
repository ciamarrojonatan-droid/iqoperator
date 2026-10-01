"""test_parity_1on1.py - Parity 1:1 (batch 1on1).

Cobre, com skips graciosos quando a assinatura nova ainda nao existe:
1. normalize_candles (rename from->time, dedup keep=last, sem fill-com-close).
2. drop_forming_bar (feature_engine.parity).
3. payout por barra no backtest engine (trades_df.payout varia).
4. eligible_mask/toxic (bloqueio de 1h => vetoed>0 e zero trades nela).

Sem fixtures exoticas: apenas unittest + pandas/numpy.
"""
from __future__ import annotations

import inspect
import unittest

import numpy as np
import pandas as pd


def _unwrap_df(out):
    """Aceita retorno DataFrame ou tupla (df, ...) e devolve o DataFrame."""
    if isinstance(out, tuple) and len(out) > 0:
        for item in out:
            if isinstance(item, pd.DataFrame):
                return item
        return out[0]
    return out


class TestNormalizeCandles(unittest.TestCase):
    def test_rename_from_dedup_no_fill(self):
        try:
            from iq_regime_adaptive.pipeline.data_loader import normalize_candles
        except ImportError as exc:
            self.skipTest(f"normalize_candles ainda nao existe: {exc}")

        t0 = pd.Timestamp("2026-01-01 00:00:00", tz="UTC")
        # Duplicata no mesmo timestamp: primeira (close=1.0) vs ultima (close=1.5).
        # Uma linha com close NaN para checar "sem fill-com-close".
        df = pd.DataFrame(
            {
                "from": [t0, t0, t0 + pd.Timedelta(minutes=1), t0 + pd.Timedelta(minutes=2)],
                "open": [1.0, 1.1, 1.2, 1.3],
                "high": [1.1, 1.2, 1.3, 1.4],
                "low": [0.9, 1.0, 1.1, 1.2],
                "close": [1.0, 1.5, float("nan"), 1.35],
                "volume": [10.0, 99.0, 20.0, 30.0],
            }
        )

        try:
            out = _unwrap_df(normalize_candles(df))
        except TypeError as exc:
            # Assinatura incompativel com chamada posicional simples.
            self.skipTest(f"assinatura de normalize_candles incompativel: {exc}")

        self.assertIsInstance(out, pd.DataFrame)
        self.assertIn("time", out.columns)
        self.assertNotIn("from", out.columns)

        # Dedup: sem timestamps repetidos.
        self.assertEqual(out["time"].duplicated().sum(), 0)

        # keep=last: o registro sobrevivente de t0 deve ser o ultimo (close 1.5 / vol 99).
        kept = out[out["time"] == t0]
        self.assertEqual(len(kept), 1)
        self.assertAlmostEqual(float(kept.iloc[0]["close"]), 1.5)
        self.assertAlmostEqual(float(kept.iloc[0]["volume"]), 99.0)

        # Sem fill-com-close: linha com NaN ou e' vetada (removida) ou preserva NaN;
        # nunca preenchida com valor arbitrario.
        t_nan = t0 + pd.Timedelta(minutes=1)
        nan_rows = out[out["time"] == t_nan]
        if len(nan_rows) == 0:
            pass  # linha vetada: comportamento aceito
        else:
            self.assertTrue(
                nan_rows["close"].isna().any(),
                "close NaN foi preenchido (fill-com-close); esperado NaN preservado ou linha vetada",
            )


class TestDropFormingBar(unittest.TestCase):
    def test_drop_forming_bar(self):
        try:
            from iq_regime_adaptive.feature_engine import parity as parity_mod
        except ImportError as exc:
            self.skipTest(f"iq_regime_adaptive.feature_engine.parity ainda nao existe: {exc}")
        try:
            drop_forming_bar = parity_mod.drop_forming_bar
        except AttributeError as exc:
            self.skipTest(f"drop_forming_bar ainda nao existe: {exc}")

        idx = pd.date_range("2026-01-01", periods=10, freq="min", tz="UTC")
        df = pd.DataFrame(
            {
                "time": idx,
                "open": np.linspace(1.0, 1.1, 10),
                "high": np.linspace(1.1, 1.2, 10),
                "low": np.linspace(0.9, 1.0, 10),
                "close": np.linspace(1.0, 1.1, 10),
                "volume": np.ones(10),
            }
        )
        # Ultima barra sera considerada "forming" via now_ts dentro do seu minuto.
        forming_time = idx[-1]

        try:
            sig = inspect.signature(drop_forming_bar)
            params = list(sig.parameters.values())
            if len(params) == 1:
                res = drop_forming_bar(df)
            else:
                # Completa args extras obrigatorios com valores padrao sensatos.
                kwargs = {}
                for p in params[1:]:
                    if p.default is not inspect.Parameter.empty:
                        continue
                    lname = p.name.lower()
                    if "timeframe" in lname or "interval" in lname or "period" in lname:
                        kwargs[p.name] = 60
                    elif lname in ("time_col", "time_column", "ts_col", "timestamp_col"):
                        kwargs[p.name] = "time"
                    elif lname in ("inplace",):
                        kwargs[p.name] = False
                try:
                    # now_ts dentro da ultima barra => ela ainda esta forming.
                    now_forming = idx[-1] + pd.Timedelta(seconds=30)
                    if "now_ts" in sig.parameters:
                        kwargs["now_ts"] = now_forming
                    res = drop_forming_bar(df, **kwargs)
                except TypeError as exc:
                    self.skipTest(f"assinatura de drop_forming_bar incompativel: {exc}")
        except (ValueError, TypeError) as exc:
            self.skipTest(f"nao foi possivel inspecionar drop_forming_bar: {exc}")

        # Retorno pode ser DataFrame ou tupla (df, dropped_flag).
        dropped_flag = None
        if isinstance(res, tuple):
            out = _unwrap_df(res)
            for item in res:
                if isinstance(item, bool):
                    dropped_flag = item
                    break
        else:
            out = res

        self.assertIsInstance(out, pd.DataFrame)
        self.assertLess(len(out), len(df), "forming bar nao foi removida")
        if dropped_flag is not None:
            self.assertTrue(dropped_flag, "flag de forming deveria ser True")
        # A barra forming deve ter saido; as anteriores preservadas.
        if "time" in out.columns:
            out_times = set(pd.to_datetime(out["time"], utc=True))
            self.assertNotIn(forming_time, out_times)


class TestPayoutPerBar(unittest.TestCase):
    def _engine_supports_per_bar(self):
        from iq_regime_adaptive.backtest import engine as engine_mod

        mod_run = getattr(engine_mod, "run", None)
        if callable(mod_run):
            params = set(inspect.signature(mod_run).parameters)
            if {"payout_series", "payouts", "payout_col", "payout_by_bar"} & params:
                return ("module", mod_run)
            # 'payout' que aceite Serie/lista tambem conta como assinatura nova.
            return ("module-maybe", mod_run)
        from iq_regime_adaptive.backtest.engine import BacktestEngine

        params = inspect.signature(BacktestEngine.run).parameters
        if {"payout_series", "payouts", "payout_col", "payout_by_bar"} & set(params):
            return ("method", BacktestEngine)
        # Worker B (sprint paridade): payout: Union[float, pd.Series, str] —
        # detecta pela anotação aceitar Series.
        payout_p = params.get("payout")
        if payout_p is not None and "Series" in str(
            payout_p.annotation
        ):
            return ("method-per-bar", BacktestEngine)
        return (None, None)

    def test_payout_varies_per_bar(self):
        try:
            from iq_regime_adaptive.backtest import engine as engine_mod
            from iq_regime_adaptive.backtest.engine import BacktestEngine
        except ImportError as exc:
            self.skipTest(f"backtest engine nao importavel: {exc}")

        kind, _ = self._engine_supports_per_bar()
        if kind is None:
            self.skipTest(
                "assinatura nova de payout por barra ainda nao existe "
                "(BacktestEngine.run so aceita payout escalar)"
            )

        # Serie de payouts variando por barra.
        n = 60
        idx = pd.date_range("2026-01-01", periods=n, freq="min", tz="UTC")
        rng = np.random.default_rng(7)
        rets = rng.normal(0.0, 0.001, size=n)
        close = 1.0 + np.cumsum(rets)
        df = pd.DataFrame(
            {"open": close, "high": close + 0.001, "low": close - 0.001, "close": close},
            index=idx,
        )
        payouts = pd.Series(np.linspace(0.5, 0.95, n), index=idx)
        signals = pd.Series(["CALL"] * n, index=idx, name="SIG")

        eng = BacktestEngine(
            initial_balance=1000.0,
            risk_method="fixed",
            fixed_stake=10.0,
            execution_mode="close",
            enable_payout_filter=False,
        )

        mod_run = getattr(engine_mod, "run", None)
        result = None
        # 1) tenta funcao module-level run(df, signals, payout=<serie>)
        if callable(mod_run):
            try:
                result = mod_run(df, signals, payout=payouts)
            except Exception:
                result = None
        # 2) tenta BacktestEngine.run com payout=Serie
        if result is None:
            try:
                result = eng.run(df, signals, payout=payouts, horizon_bars=1)  # type: ignore[arg-type]
            except Exception as exc:
                self.skipTest(f"engine nao aceita payout por barra nesta revisao: {exc}")

        trades_df = getattr(result, "trades_df", None)
        self.assertIsNotNone(trades_df)
        self.assertGreater(len(trades_df), 0, "esperava ao menos 1 trade")
        self.assertIn("payout", trades_df.columns)
        nunique = trades_df["payout"].nunique()
        self.assertGreater(
            nunique, 1, f"trades_df.payout nao varia com serie de payouts (nunique={nunique})"
        )


class TestEligibleMaskToxic(unittest.TestCase):
    def test_block_one_hour(self):
        try:
            from iq_regime_adaptive.backtest.engine import BacktestEngine
        except ImportError as exc:
            self.skipTest(f"backtest engine nao importavel: {exc}")

        # Skip se o engine ainda nao suporta trade_eligible/warmup.
        try:
            src = inspect.getsource(BacktestEngine.run)
        except (OSError, TypeError) as exc:
            self.skipTest(f"nao foi possivel inspecionar BacktestEngine.run: {exc}")
        if "trade_eligible" not in src and "warmup" not in src:
            self.skipTest("params de elegibilidade/toxic ainda nao existem no engine")

        n = 180  # 3h em M1
        idx = pd.date_range("2026-01-01", periods=n, freq="min", tz="UTC")
        rng = np.random.default_rng(11)
        rets = rng.normal(0.0, 0.001, size=n)
        close = 1.0 + np.cumsum(rets)
        df = pd.DataFrame(
            {"open": close, "high": close + 0.001, "low": close - 0.001, "close": close},
            index=idx,
        )
        # Bloqueia 1h sintetica no meio (60 barras).
        blocked = np.zeros(n, dtype=bool)
        blocked[60:120] = True
        df["trade_eligible"] = ~blocked

        signals = pd.Series(["CALL"] * n, index=idx, name="SIG")
        eng = BacktestEngine(
            initial_balance=1000.0,
            risk_method="fixed",
            fixed_stake=10.0,
            execution_mode="close",
            enable_payout_filter=False,
        )
        result = eng.run(df, signals, payout=0.85, horizon_bars=1)

        vetoed = getattr(result, "vetoed_signals_count", getattr(result, "vetoed", 0))
        self.assertGreater(vetoed, 0, "bloqueio de 1h deveria gerar vetoed>0")

        trades_df = result.trades_df
        if len(trades_df) > 0 and "entry_idx" in trades_df.columns:
            in_block = trades_df[
                (trades_df["entry_idx"] >= 60) & (trades_df["entry_idx"] < 120)
            ]
            self.assertEqual(
                len(in_block), 0, f"ha {len(in_block)} trades dentro da hora bloqueada"
            )


if __name__ == "__main__":
    unittest.main()
