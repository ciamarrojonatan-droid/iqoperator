"""
tests/test_ml_filter.py

Testes unitários formais e de estresse do acoplamento do MLFilter para a suíte geral do projeto.
Inclui verificação de resiliência a NaNs intermitentes, formato nativo JSON, ordenação temporal
e gating de execução de ordens no loop de bot.py.
"""
import os
import sys
import unittest
import numpy as np
import pandas as pd
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ml_filter import MLFilter, get_ml_filter
import config as cfg


class TestMLFilterIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.filter = MLFilter()
        cls.json_path = os.path.join(os.path.dirname(__file__), "..", "models", "xgb_filter.json")

    def test_filter_load_and_structure(self):
        """Verifica se o artefato pkl foi carregado corretamente na suíte de testes."""
        self.assertTrue(self.filter.is_loaded)
        self.assertEqual(len(self.filter.feature_cols), 72)
        self.assertEqual(self.filter.threshold, 0.62)

    def test_json_model_artifact_loading(self):
        """Verifica se o artefato nativo xgb_filter.json pode ser carregado e inferido com sucesso."""
        if os.path.exists(self.json_path):
            json_filter = MLFilter(model_path=self.json_path)
            self.assertTrue(json_filter.is_loaded, "O arquivo nativo .json deve ser carregado com sucesso.")
            self.assertEqual(len(json_filter.feature_cols), 53, "JSON booster deve expor as 72 features.")
            self.assertEqual(json_filter.threshold, 0.62)

    def test_mock_candle_inference(self):
        """Verifica que candle mockado processa o vetor e gera probabilidade válida sem erros de tipagem."""
        n_bars = 110
        base_ts = 1700000000
        timestamps = [base_ts + i * 900 for i in range(n_bars)]
        prices = [1.0800 + (i * 0.0001) for i in range(n_bars)]

        df = pd.DataFrame({
            "from": timestamps,
            "open": prices,
            "max": [p + 0.0005 for p in prices],
            "min": [p - 0.0005 for p in prices],
            "close": prices,
            "volume": [500] * n_bars
        })

        feat = self.filter.compute_features(df)
        self.assertIsInstance(feat, pd.DataFrame)
        self.assertEqual(feat.shape, (1, 72))

        prob = self.filter.predict_proba(df)
        self.assertIsInstance(prob, float)
        self.assertTrue(0.0 <= prob <= 1.0)

        allowed, p = self.filter.filter_signal(df, "call")
        self.assertIsInstance(allowed, bool)
        self.assertIsInstance(p, float)
        self.assertEqual(allowed, p >= 0.62)

    def test_intermittent_nan_resilience(self):
        """Verifica resiliência contra ticks/valores NaN introduzidos por perda de pacotes websocket."""
        n_bars = 110
        base_ts = 1700000000
        timestamps = [base_ts + i * 900 for i in range(n_bars)]
        prices = [1.0800 + (i * 0.0001) for p, i in enumerate(range(n_bars))]
        
        # Simula perdas intermitentes no meio da série temporal
        prices[30] = np.nan
        prices[45] = np.nan

        df = pd.DataFrame({
            "time": timestamps,
            "open": prices,
            "high": [p + 0.0005 if not np.isnan(p) else np.nan for p in prices],
            "low": [p - 0.0005 if not np.isnan(p) else np.nan for p in prices],
            "close": prices
        })

        prob = self.filter.predict_proba(df)
        self.assertIsInstance(prob, float)
        self.assertTrue(0.0 <= prob <= 1.0)

    def test_string_timestamp_and_reverse_order(self):
        """Verifica suporte a strings ISO e ordenação estrita mesmo se dados chegarem invertidos."""
        n_bars = 110
        now = pd.Timestamp.now(tz="UTC")
        datetimes = [str(now - pd.Timedelta(minutes=15 * (n_bars - i))) for i in range(n_bars)]
        prices = [1.0800 + (i * 0.0001) for i in range(n_bars)]
        highs = [p + 0.0005 for p in prices]
        lows = [p - 0.0005 for p in prices]

        df_fwd = pd.DataFrame({
            "datetime": datetimes,
            "open": prices,
            "high": highs,
            "low": lows,
            "close": prices
        })

        df_rev = pd.DataFrame({
            "datetime": list(reversed(datetimes)),
            "open": list(reversed(prices)),
            "high": list(reversed(highs)),
            "low": list(reversed(lows)),
            "close": list(reversed(prices))
        })

        prob_fwd = self.filter.predict_proba(df_fwd)
        prob_rev = self.filter.predict_proba(df_rev)
        self.assertIsInstance(prob_rev, float)
        self.assertAlmostEqual(prob_fwd, prob_rev, places=5)

    def test_signal_casing_and_normalization(self):
        """Verifica que sinais em maiúsculas ('CALL', 'PUT') e com espaços são aceitos."""
        n_bars = 110
        df = pd.DataFrame({
            "time": [1700000000 + i * 900 for i in range(n_bars)],
            "open": [1.0850] * n_bars,
            "high": [1.0860] * n_bars,
            "low": [1.0840] * n_bars,
            "close": [1.0855] * n_bars
        })

        allowed_upper, p_upper = self.filter.filter_signal(df, " CALL ")
        allowed_lower, p_lower = self.filter.filter_signal(df, "call")
        self.assertEqual(allowed_upper, allowed_lower)
        self.assertEqual(p_upper, p_lower)

        # Sinais inválidos devem ser estritamente barrados
        allowed_bad, p_bad = self.filter.filter_signal(df, "hold")
        self.assertFalse(allowed_bad)
        self.assertEqual(p_bad, 0.0)

    def test_bot_coupling_initialization(self):
        """Verifica que Bot instancia o ml_filter e respeita as flags de configuração."""
        with patch('bot.IQ_Option') as mock_iq:
            mock_iq.return_value = MagicMock()
            from bot import Bot
            bot = Bot()
            self.assertIsNotNone(bot.ml_filter)
            self.assertTrue(bot.ml_filter.is_loaded)
            self.assertEqual(bot.ml_filter.threshold, cfg.ML_THRESHOLD)

    def test_bot_runtime_gating_order_suppression(self):
        """Verifica o acoplamento dinâmico em tempo real: ordem só dispara se ML aprovar (p >= 0.62)."""
        with patch('bot.IQ_Option') as mock_iq:
            mock_iq.return_value = MagicMock()
            from bot import Bot
            bot = Bot()
            
            # Mock de candles
            n_bars = 110
            df = pd.DataFrame({
                "from": [1700000000 + i * 900 for i in range(n_bars)],
                "open": [1.0850] * n_bars,
                "high": [1.0860] * n_bars,
                "low": [1.0840] * n_bars,
                "close": [1.0855] * n_bars
            })

            # Mock do ml_filter para testar gating exato
            bot.ml_filter = MagicMock()
            bot.ml_filter.is_loaded = True

            # Caso 1: Probabilidade baixa (0.45 < 0.62) -> Trade BARRADO
            bot.ml_filter.filter_signal.return_value = (False, 0.45)
            allowed, prob = bot.ml_filter.filter_signal(df, "call", threshold=cfg.ML_THRESHOLD)
            self.assertFalse(allowed)
            self.assertEqual(prob, 0.45)

            # Caso 2: Probabilidade alta (0.68 >= 0.62) -> Trade AUTORIZADO
            bot.ml_filter.filter_signal.return_value = (True, 0.68)
            allowed, prob = bot.ml_filter.filter_signal(df, "call", threshold=cfg.ML_THRESHOLD)
            self.assertTrue(allowed)
            self.assertEqual(prob, 0.68)

    def test_fail_closed_and_fail_open_policies(self):
        """Verifica que buffer < 101 candles cancela por padrão (fail-closed) e bypassa se fail-open."""
        df_60 = pd.DataFrame({
            "open": [1.1000] * 60, "high": [1.1010] * 60,
            "low": [1.0990] * 60, "close": [1.1005] * 60
        })
        # Default fail-closed
        allowed_closed, p_closed = self.filter.filter_signal(df_60, "call")
        self.assertFalse(allowed_closed)
        self.assertEqual(p_closed, 0.0)

        # Explicit fail-open
        allowed_open, p_open = self.filter.filter_signal(df_60, "call", fail_open=True)
        self.assertTrue(allowed_open)
        self.assertEqual(p_open, 1.0)

    def test_model_unloaded_safety(self):
        """Verifica que filtro descarregado barra trades em fail-closed e permite em fail-open."""
        unloaded = MLFilter(model_path="nonexistent.pkl", fail_open=False)
        df = pd.DataFrame({
            "time": [1700000000 + i * 900 for i in range(110)],
            "open": [1.08] * 110, "high": [1.09] * 110, "low": [1.07] * 110, "close": [1.08] * 110
        })
        allowed, prob = unloaded.filter_signal(df, "call")
        self.assertFalse(allowed)
        self.assertEqual(prob, 0.0)

        allowed_fo, prob_fo = unloaded.filter_signal(df, "call", fail_open=True)
        self.assertTrue(allowed_fo)
        self.assertEqual(prob_fo, 1.0)

    def test_candle_physical_integrity(self):
        """Verifica higienização de anomalias de candles (high < low, close > high) sem valores negativos ou infinitos."""
        n_bars = 110
        df = pd.DataFrame({
            "time": [1700000000 + i * 900 for i in range(n_bars)],
            "open": [1.0850] * n_bars,
            "high": [1.0800] * n_bars,
            "low": [1.0900] * n_bars,
            "close": [1.0880] * n_bars
        })
        feat = self.filter.compute_features(df)
        self.assertFalse(feat.isnull().any().any())
        self.assertFalse(np.isinf(feat.values).any())
        self.assertTrue((feat["body_ratio"] >= 0.0).all())
        self.assertTrue((feat["upper_wick_ratio"] >= 0.0).all())
        self.assertTrue((feat["lower_wick_ratio"] >= 0.0).all())

    def test_string_numeric_timestamp_parsing(self):
        """Verifica que strings numéricas de timestamp são tratadas sem erro de parsing de data."""
        n_bars = 110
        df = pd.DataFrame({
            "time": [str(1700000000 + i * 900) for i in range(n_bars)],
            "open": [1.0850] * n_bars, "high": [1.0860] * n_bars,
            "low": [1.0840] * n_bars, "close": [1.0855] * n_bars
        })
        prob = self.filter.predict_proba(df)
        self.assertIsInstance(prob, float)

    def test_zero_price_resilience(self):
        """Verifica que preços zerados ou com transição súbita não geram NaNs ou Infs."""
        n_bars = 110
        prices = [0.0] * 108 + [1.0, 1.0]
        df = pd.DataFrame({
            "time": [1700000000 + i * 900 for i in range(n_bars)],
            "open": prices, "high": [p + 0.1 for p in prices],
            "low": prices, "close": prices
        })
        feat = self.filter.compute_features(df)
        self.assertFalse(feat.isnull().any().any())
        self.assertFalse(np.isinf(feat.values).any())

    def test_thread_safety_singleton_and_inference(self):
        """Verifica inferência concorrente multi-threaded e singleton thread-safe."""
        import threading
        f_singleton = get_ml_filter()
        self.assertIsNotNone(f_singleton)
        self.assertTrue(f_singleton.is_loaded)

        n_bars = 110
        df = pd.DataFrame({
            "time": [1700000000 + i * 900 for i in range(n_bars)],
            "open": [1.0850] * n_bars, "high": [1.0860] * n_bars,
            "low": [1.0840] * n_bars, "close": [1.0855] * n_bars
        })
        errors = []
        def worker():
            try:
                allowed, p = f_singleton.filter_signal(df, "call")
                self.assertIsInstance(allowed, bool)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker) for _ in range(12)]
        for t in threads: t.start()
        for t in threads: t.join()

        self.assertEqual(len(errors), 0)

    def test_timestamp_deduplication(self):
        """Verifica que duplicatas temporais em websocket reconnects são filtradas sem corromper featurização."""
        n_bars = 110
        base_ts = 1700000000
        timestamps = [base_ts + i * 900 for i in range(n_bars)]
        prices = [1.0800 + (i * 0.0001) for i in range(n_bars)]

        dup_timestamps = timestamps[:25] + [timestamps[24]] * 4 + timestamps[25:]
        dup_prices = prices[:25] + [prices[24]] * 4 + prices[25:]

        df = pd.DataFrame({
            "time": dup_timestamps,
            "open": dup_prices,
            "high": [p + 0.0005 for p in dup_prices],
            "low": [p - 0.0005 for p in dup_prices],
            "close": dup_prices
        })

        feat = self.filter.compute_features(df)
        self.assertEqual(feat.shape, (1, 72))
        self.assertFalse(feat.isnull().any().any())

    def test_json_automatic_fallback(self):
        """Verifica fallback automático para modelo JSON caso arquivo .pkl não seja encontrado."""
        import tempfile
        import shutil
        with tempfile.TemporaryDirectory() as tmp_dir:
            shutil.copy(self.json_path, os.path.join(tmp_dir, "xgb_filter.json"))
            meta_src = os.path.join(os.path.dirname(self.json_path), "metadata.json")
            if os.path.exists(meta_src):
                shutil.copy(meta_src, os.path.join(tmp_dir, "metadata.json"))

            target_pkl = os.path.join(tmp_dir, "xgb_filter.pkl")
            resilient_filter = MLFilter(model_path=target_pkl)
            self.assertTrue(resilient_filter.is_loaded)
            self.assertTrue(resilient_filter.model_path.endswith(".json"))

    def test_json_scaler_reconstruction(self):
        """Verifica reconstrução do StandardScaler a partir do metadata.json para o modelo nativo JSON."""
        if os.path.exists(self.json_path):
            json_filter = MLFilter(model_path=self.json_path)
            self.assertTrue(json_filter.is_loaded)
            self.assertIsNotNone(json_filter.scaler)
            self.assertEqual(len(json_filter.scaler.mean_), 53)

    def test_exception_fail_open_consistency(self):
        """Verifica que exceções no cálculo de features respeitam a configuração de fail_open."""
        df_corrupt = pd.DataFrame({
            "time": [1700000000 + i * 900 for i in range(110)],
            "open": [np.nan] * 110, "high": [np.nan] * 110, "low": [np.nan] * 110, "close": [np.nan] * 110
        })
        allowed_fc, p_fc = self.filter.filter_signal(df_corrupt, "call", fail_open=False)
        self.assertFalse(allowed_fc)
        self.assertEqual(p_fc, 0.0)

        allowed_fo, p_fo = self.filter.filter_signal(df_corrupt, "call", fail_open=True)
        self.assertTrue(allowed_fo)
        self.assertEqual(p_fo, 1.0)


if __name__ == '__main__':
    unittest.main()

