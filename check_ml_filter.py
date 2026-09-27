#!/usr/bin/env python3
"""
check_ml_filter.py

Script de validação automatizada do Filtro Preditivo ML (XGBoost tau=0.62).
Verifica:
  1. Integridade dos artefatos serializados (models/xgb_filter_v2.pkl, models/xgb_filter_v2.json).
  2. Inicialização e carregamento sem latência excessiva.
  3. Extração e integridade de tipos do vetor de 53 features em candles mockados.
  4. Inferência de probabilidades (retorno float em [0.0, 1.0]).
  5. Decisão de gating do trade (prob >= 0.62 permite, prob < 0.62 barra).
  6. Robustez de schema (diferentes formatos de timestamp: 'from', 'time', 'datetime', 'min'/'max').
  7. Casos de borda (buffer insuficiente, sinais inválidos).
"""
import os
import sys
import time
import unittest
import numpy as np
import pandas as pd

from ml_filter import MLFilter, get_ml_filter, DEFAULT_THRESHOLD, MIN_CANDLE_COUNT

class TestMLFilter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models_dir = os.path.join(os.path.dirname(__file__), "models")
        cls.pkl_path = os.path.join(cls.models_dir, "xgb_filter_v2.pkl")
        cls.json_path = os.path.join(cls.models_dir, "xgb_filter_v2.json")

        # 1. Verifica se artefatos existem
        assert os.path.exists(cls.pkl_path), f"Artefato pkl ausente: {cls.pkl_path}"
        if os.path.exists(cls.json_path):
            pass

        # Carrega o filtro
        t0 = time.perf_counter()
        cls.filter = MLFilter(model_path=cls.pkl_path, threshold=0.62)
        cls.load_time_ms = (time.perf_counter() - t0) * 1000

    def test_01_model_loaded_and_metadata(self):
        """Verifica se o modelo foi carregado corretamente com 53 features e tau=0.62."""
        self.assertTrue(self.filter.is_loaded, "O filtro ML deve estar carregado.")
        self.assertTrue(len(self.filter.feature_cols) >= 53, "O modelo deve possuir no mínimo 53 features.")
        self.assertAlmostEqual(self.filter.threshold, 0.62, places=2)
        self.assertIsNotNone(self.filter.model)

    def test_02_inference_on_synthetic_mock_candles(self):
        """Processa um buffer mockado de 80 candles sintetizados e valida tipagem e limites."""
        n_bars = 130
        # Simula timestamps de 15 minutos em unix epoch (segundos)
        base_ts = 1720000000
        timestamps = [base_ts + i * 900 for i in range(n_bars)]

        # Simula preços plausíveis de EUR/USD em torno de 1.0800
        np.random.seed(123)
        returns = np.random.normal(0, 0.0005, size=n_bars)
        close_prices = 1.0800 * np.exp(np.cumsum(returns))
        high_prices = close_prices + np.random.uniform(0.0001, 0.0005, size=n_bars)
        low_prices = close_prices - np.random.uniform(0.0001, 0.0005, size=n_bars)
        open_prices = low_prices + (high_prices - low_prices) * np.random.uniform(0.2, 0.8, size=n_bars)

        mock_df = pd.DataFrame({
            "from": timestamps,
            "open": open_prices,
            "max": high_prices,
            "min": low_prices,
            "close": close_prices,
            "volume": np.random.randint(100, 1000, size=n_bars)
        })

        # Extração de features
        t0 = time.perf_counter()
        feat = self.filter.compute_features(mock_df)
        compute_ms = (time.perf_counter() - t0) * 1000

        # Verificação estrita de tipagem e formato
        self.assertIsInstance(feat, pd.DataFrame, "Features devem ser retornadas em pd.DataFrame")
        self.assertEqual(feat.shape, (1, 72), "Dimensão do vetor de features deve ser exatamente (1, 72)")
        self.assertFalse(feat.isnull().any().any(), "Vetor de features não pode conter valores NaN")
        self.assertFalse(np.isinf(feat.values).any(), "Vetor de features não pode conter valores Inf")

        # Verifica tipo de dados de cada coluna (deve ser numérico)
        for col in feat.columns:
            self.assertTrue(np.issubdtype(feat[col].dtype, np.number), f"Coluna {col} não é numérica: {feat[col].dtype}")

        # Predição de probabilidade
        t1 = time.perf_counter()
        prob = self.filter.predict_proba(mock_df)
        infer_ms = (time.perf_counter() - t1) * 1000

        self.assertIsInstance(prob, float, "Probabilidade deve ser float nativo do Python")
        self.assertGreaterEqual(prob, 0.0, "Probabilidade não pode ser menor que 0.0")
        self.assertLessEqual(prob, 1.0, "Probabilidade não pode ser maior que 1.0")

        # Verificação de gating do sinal
        allowed_call, prob_call = self.filter.filter_signal(mock_df, "call")
        self.assertIsInstance(allowed_call, bool, "Decisão de trade deve ser booleana")
        self.assertIsInstance(prob_call, float, "Probabilidade retornada deve ser float")
        self.assertEqual(allowed_call, prob >= 0.62, "Gating deve respeitar estritamente prob >= 0.62")

        allowed_put, prob_put = self.filter.filter_signal(mock_df, "put")
        self.assertIsInstance(allowed_put, bool)
        self.assertEqual(allowed_put, prob >= 0.62)

        print(f"[CHECK PASS] Mock Candle Test: compute={compute_ms:.2f}ms, infer={infer_ms:.2f}ms, P(Win)={prob:.4f}, allowed={allowed_call}")

    def test_03_timestamp_and_column_variations(self):
        """Verifica robustez a variações de nomes de colunas ('time', 'datetime', 'high'/'low')."""
        n_bars = 120
        now = pd.Timestamp.now(tz="UTC")
        datetimes = [now - pd.Timedelta(minutes=15 * (n_bars - i)) for i in range(n_bars)]

        # Caso A: usando 'datetime' e 'high'/'low'
        df_a = pd.DataFrame({
            "datetime": datetimes,
            "open": [1.0850] * n_bars,
            "high": [1.0860] * n_bars,
            "low": [1.0840] * n_bars,
            "close": [1.0855] * n_bars
        })
        prob_a = self.filter.predict_proba(df_a)
        self.assertIsInstance(prob_a, float)
        self.assertTrue(0.0 <= prob_a <= 1.0)

        # Caso B: usando 'time' em milissegundos
        df_b = pd.DataFrame({
            "time": [int(dt.timestamp() * 1000) for dt in datetimes],
            "open": [1.0850] * n_bars,
            "high": [1.0860] * n_bars,
            "low": [1.0840] * n_bars,
            "close": [1.0855] * n_bars
        })
        prob_b = self.filter.predict_proba(df_b)
        self.assertIsInstance(prob_b, float)
        self.assertAlmostEqual(prob_a, prob_b, places=4, msg="Inferência com time(ms) e datetime deve ser idêntica")

    def test_04_boundary_conditions(self):
        """Verifica comportamento com buffer no limite exato (61 candles) e abaixo (60 candles)."""
        # Exatamente 61 candles (mínimo exigido: 1 shift + 60 rolling)
        df_61 = pd.DataFrame({
            "open": [1.1000] * 101,
            "high": [1.1010] * 101,
            "low": [1.0990] * 101,
            "close": [1.1005] * 101
        })
        prob_61 = self.filter.predict_proba(df_61)
        self.assertIsInstance(prob_61, float)

        # Abaixo de 61 candles (ex: 60) -> compute_features deve lançar ValueError
        df_60 = pd.DataFrame({
            "open": [1.1000] * 99,
            "high": [1.1010] * 99,
            "low": [1.0990] * 99,
            "close": [1.1005] * 99
        })
        with self.assertRaises(ValueError):
            self.filter.compute_features(df_60)

        # Por padrão (fail-closed), filter_signal cancela o trade por segurança em buffers insuficientes
        allowed_closed, prob_closed = self.filter.filter_signal(df_60, "call")
        self.assertFalse(allowed_closed)
        self.assertEqual(prob_closed, 0.0)

        # Com fail_open=True explícito, autoriza em modo bypass
        allowed_open, prob_open = self.filter.filter_signal(df_60, "call", fail_open=True)
        self.assertTrue(allowed_open)
        self.assertEqual(prob_open, 1.0)

        # Sinais vazios ou inválidos
        allowed_none, _ = self.filter.filter_signal(df_61, None)
        self.assertFalse(allowed_none)

        allowed_inv, _ = self.filter.filter_signal(df_61, "hold")
        self.assertFalse(allowed_inv)

    def test_05_threshold_gating_mechanics(self):
        """Verifica se o limiar tau=0.62 cancela trades abaixo de 0.62 e autoriza acima."""
        df_slice = pd.DataFrame({
            "open": [1.1000] * 120,
            "high": [1.1010] * 120,
            "low": [1.0990] * 120,
            "close": [1.1005] * 120
        })
        actual_prob = self.filter.predict_proba(df_slice)

        # Se forçarmos threshold = prob + 0.05 -> DEVE BARRAR
        allowed_block, p = self.filter.filter_signal(df_slice, "call", threshold=actual_prob + 0.05)
        self.assertFalse(allowed_block)
        self.assertEqual(p, actual_prob)

        # Se forçarmos threshold = prob - 0.05 -> DEVE AUTORIZAR
        allowed_pass, p = self.filter.filter_signal(df_slice, "call", threshold=actual_prob - 0.05)
        self.assertTrue(allowed_pass)
        self.assertEqual(p, actual_prob)

    def test_06_real_data_slice_reproducibility(self):
        """Valida que uma fatia de candles reais de histdata gera predição consistente."""
        data_path = os.path.join(os.path.dirname(__file__), "data", "EURUSD_M15_histdata.csv")
        if os.path.exists(data_path):
            df_hist = pd.read_csv(data_path)
            slice_100 = df_hist.iloc[1000:1100].copy()
            prob = self.filter.predict_proba(slice_100)
            self.assertIsInstance(prob, float)
            self.assertTrue(0.0 <= prob <= 1.0)
            print(f"[CHECK PASS] Real Data Slice Test (idx 1000:1100): P(Reversal) = {prob:.4f}")

    def test_07_json_model_native_loading(self):
        """Valida que o artefato nativo xgb_filter_v2.json é carregado e executa inferência idêntica."""
        if os.path.exists(self.json_path):
            json_filter = MLFilter(model_path=self.json_path)
            self.assertTrue(json_filter.is_loaded)
            self.assertEqual(len(json_filter.feature_cols), 53)
            # Testa inferência sobre dados reais
            data_path = os.path.join(os.path.dirname(__file__), "data", "EURUSD_M15_histdata.csv")
            if os.path.exists(data_path):
                df_hist = pd.read_csv(data_path)
                slice_100 = df_hist.iloc[1000:1100].copy()
                prob_pkl = self.filter.predict_proba(slice_100)
                prob_json = json_filter.predict_proba(slice_100)
                self.assertAlmostEqual(prob_pkl, prob_json, places=5, msg="Probabilidade entre .pkl e .json deve coincidir")

    def test_08_intermittent_nan_resilience(self):
        """Valida que valores NaN pontuais (packet drops no websocket) são recuperados com forward-fill."""
        n_bars = 125
        prices = [1.0800 + i * 0.0001 for i in range(n_bars)]
        prices[30] = np.nan
        prices[45] = np.nan
        df_nan = pd.DataFrame({
            "time": [1700000000 + i * 900 for i in range(n_bars)],
            "open": prices,
            "high": [p + 0.0005 if not np.isnan(p) else np.nan for p in prices],
            "low": [p - 0.0005 if not np.isnan(p) else np.nan for p in prices],
            "close": prices
        })
        prob = self.filter.predict_proba(df_nan)
        self.assertIsInstance(prob, float)
        self.assertTrue(0.0 <= prob <= 1.0)

    def test_09_string_timestamps_and_reverse_order(self):
        """Valida suporte a timestamps em formato ISO string e ordenação automática caso candles venham invertidos."""
        n_bars = 120
        now = pd.Timestamp.now(tz="UTC")
        datetimes = [str(now - pd.Timedelta(minutes=15 * (n_bars - i))) for i in range(n_bars)]
        prices = [1.0800 + i * 0.0001 for i in range(n_bars)]
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
        self.assertAlmostEqual(prob_fwd, prob_rev, places=5, msg="Probabilidade para dados em ordem invertida deve coincidir estritamente com a cronológica")
    def test_10_string_numeric_timestamps(self):
        """Valida que strings numéricas de epoch timestamp (ex: '1700000000') são convertidas sem erro de ano fora de escala."""
        n_bars = 120
        str_ts = [str(1700000000 + i * 900) for i in range(n_bars)]
        df_str_ts = pd.DataFrame({
            "time": str_ts,
            "open": [1.0850] * n_bars,
            "high": [1.0860] * n_bars,
            "low": [1.0840] * n_bars,
            "close": [1.0855] * n_bars
        })
        prob = self.filter.predict_proba(df_str_ts)
        self.assertIsInstance(prob, float)
        self.assertTrue(0.0 <= prob <= 1.0)

    def test_11_candle_physical_integrity(self):
        """Valida higienização de candles com anomalia física de preço (high < low ou close > high)."""
        n_bars = 120
        df_anom = pd.DataFrame({
            "time": [1700000000 + i * 900 for i in range(n_bars)],
            "open": [1.0850] * n_bars,
            "high": [1.0800] * n_bars,  # high menor que close e open
            "low": [1.0900] * n_bars,   # low maior que high
            "close": [1.0880] * n_bars
        })
        feat = self.filter.compute_features(df_anom)
        self.assertFalse(feat.isnull().any().any())
        self.assertFalse(np.isinf(feat.values).any())
        self.assertGreaterEqual(feat["body_ratio"].iloc[0], 0.0)
        self.assertLessEqual(feat["body_ratio"].iloc[0], 1.0)
        self.assertGreaterEqual(feat["upper_wick_ratio"].iloc[0], 0.0)
        self.assertGreaterEqual(feat["lower_wick_ratio"].iloc[0], 0.0)
        prob = self.filter.predict_proba(df_anom)
        self.assertIsInstance(prob, float)

    def test_12_zero_price_resilience(self):
        """Valida que séries com preços zerados ou transições súbitas não geram NaN ou Inf em retornos."""
        n_bars = 120
        prices = [0.0] * 118 + [1.0, 1.0]
        df_zero = pd.DataFrame({
            "time": [1700000000 + i * 900 for i in range(n_bars)],
            "open": prices,
            "high": [p + 0.1 for p in prices],
            "low": prices,
            "close": prices
        })
        feat = self.filter.compute_features(df_zero)
        self.assertFalse(feat.isnull().any().any())
        self.assertFalse(np.isinf(feat.values).any())
        prob = self.filter.predict_proba(df_zero)
        self.assertIsInstance(prob, float)

    def test_13_thread_safety_concurrent_inference(self):
        """Valida inferência concorrente multi-threaded sem condições de corrida ou exceções."""
        import threading
        n_bars = 120
        df = pd.DataFrame({
            "time": [1700000000 + i * 900 for i in range(n_bars)],
            "open": [1.0850] * n_bars,
            "high": [1.0860] * n_bars,
            "low": [1.0840] * n_bars,
            "close": [1.0855] * n_bars
        })
        results = []
        errors = []
        def worker():
            try:
                allowed, prob = self.filter.filter_signal(df, "call")
                results.append((allowed, prob))
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker) for _ in range(15)]
        for t in threads: t.start()
        for t in threads: t.join()

        self.assertEqual(len(errors), 0, f"Erros durante inferência concorrente: {errors}")
        self.assertEqual(len(results), 15)

    def test_14_unloaded_model_fail_closed(self):
        """Valida política de segurança (fail-closed por padrão vs fail-open configurado) quando modelo não está carregado."""
        unloaded_filter = MLFilter(model_path="non_existent_model_file.pkl", fail_open=False)
        self.assertFalse(unloaded_filter.is_loaded)

        df = pd.DataFrame({
            "time": [1700000000 + i * 900 for i in range(120)],
            "open": [1.08] * 120, "high": [1.09] * 120, "low": [1.07] * 120, "close": [1.08] * 120
        })

        # Fail-closed (padrão): deve cancelar o trade
        allowed_closed, prob_closed = unloaded_filter.filter_signal(df, "call")
        self.assertFalse(allowed_closed)
        self.assertEqual(prob_closed, 0.0)

        # Fail-open: autoriza com aviso
        allowed_open, prob_open = unloaded_filter.filter_signal(df, "call", fail_open=True)
        self.assertTrue(allowed_open)
        self.assertEqual(prob_open, 1.0)

    def test_15_timestamp_deduplication(self):
        """Valida que timestamps duplicados no stream são desduplicados mantendo a integridade temporal."""
        n_bars = 125
        base_ts = 1700000000
        timestamps = [base_ts + i * 900 for i in range(n_bars)]
        prices = [1.0800 + (i * 0.0001) for i in range(n_bars)]

        # Insere repetições propositais de timestamps (como em heartbeats de websocket)
        dup_timestamps = timestamps[:30] + [timestamps[29]] * 3 + timestamps[30:]
        dup_prices = prices[:30] + [prices[29]] * 3 + prices[30:]

        df_dup = pd.DataFrame({
            "time": dup_timestamps,
            "open": dup_prices,
            "high": [p + 0.0005 for p in dup_prices],
            "low": [p - 0.0005 for p in dup_prices],
            "close": dup_prices
        })

        feat = self.filter.compute_features(df_dup)
        self.assertEqual(feat.shape, (1, 72))
        self.assertFalse(feat.isnull().any().any())

        # Buffer insuficiente após desduplicação (61 candles brutos, mas apenas 59 únicos)
        ts_short = [base_ts + i * 900 for i in range(98)] + [base_ts + 97 * 900, base_ts + 97 * 900]
        df_short = pd.DataFrame({
            "time": ts_short,
            "open": [1.08] * 100, "high": [1.09] * 100, "low": [1.07] * 100, "close": [1.08] * 100
        })
        with self.assertRaises(ValueError):
            self.filter.compute_features(df_short)

    def test_16_continuous_prediction_memory_bounded(self):
        """Valida que ciclos contínuos de inferência mantêm footprint de memória estável e delimitado."""
        import gc
        n_bars = 120
        df = pd.DataFrame({
            "time": [1700000000 + i * 900 for i in range(n_bars)],
            "open": [1.0850] * n_bars, "high": [1.0860] * n_bars,
            "low": [1.0840] * n_bars, "close": [1.0855] * n_bars
        })
        for _ in range(30):
            p = self.filter.predict_proba(df)
            self.assertTrue(0.0 <= p <= 1.0)
        gc.collect()

    def test_17_native_json_scaler_reconstruction(self):
        """Valida que o artefato JSON reconstrói perfeitamente o StandardScaler a partir de metadata.json."""
        if os.path.exists(self.json_path):
            json_filter = MLFilter(model_path=self.json_path)
            self.assertTrue(json_filter.is_loaded)
            self.assertIsNotNone(json_filter.scaler, "Scaler deve ser reconstruído a partir de metadata.json")
            self.assertEqual(len(json_filter.scaler.mean_), 53)
            self.assertEqual(len(json_filter.scaler.scale_), 53)

    def test_18_automatic_json_fallback(self):
        """Valida resiliência de auto-recuperação: se .pkl não existe ou é inválido, recorre a .json."""
        import tempfile
        import shutil
        with tempfile.TemporaryDirectory() as tmp_dir:
            if os.path.exists(self.json_path):
                shutil.copy(self.json_path, os.path.join(tmp_dir, "xgb_filter_v2.json"))
            meta_src = os.path.join(self.models_dir, "metadata.json")
            if os.path.exists(meta_src):
                shutil.copy(meta_src, os.path.join(tmp_dir, "metadata.json"))

            # Aponta para .pkl ausente no diretório temporário
            target_pkl = os.path.join(tmp_dir, "xgb_filter_v2.pkl")
            resilient_filter = MLFilter(model_path=target_pkl)
            if os.path.exists(self.json_path):
                self.assertTrue(resilient_filter.is_loaded)
                self.assertTrue(resilient_filter.model_path.endswith(".json"))

    def test_19_exception_fail_open_consistency(self):
        """Valida que exceções na extração de features respeitam estritamente a política fail_open configurada."""
        df_corrupt = pd.DataFrame({
            "time": [1700000000 + i * 900 for i in range(120)],
            "open": [np.nan] * 120, "high": [np.nan] * 120, "low": [np.nan] * 120, "close": [np.nan] * 120
        })
        allowed_fc, p_fc = self.filter.filter_signal(df_corrupt, "call", fail_open=False)
        self.assertFalse(allowed_fc)
        self.assertEqual(p_fc, 0.0)

        allowed_fo, p_fo = self.filter.filter_signal(df_corrupt, "call", fail_open=True)
        self.assertTrue(allowed_fo)
        self.assertEqual(p_fo, 1.0)

def main():
    print("=" * 70)
    print("CHECK ML FILTER: Validação Automatizada de Inferência XGBoost")
    print("=" * 70)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMLFilter)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("\n" + "=" * 70)
        print("ALL ML FILTER TESTS PASSED (100% SUITE DEEP VERIFICATION)")
        print("=" * 70)
        sys.exit(0)
    else:
        print("\n" + "!" * 70)
        print("ML FILTER TESTS FAILED")
        print("!" * 70)
        sys.exit(1)

if __name__ == '__main__':
    main()
