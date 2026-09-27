import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import numpy as np

import config as cfg
from strategies import mhi_1_signal, get_signal


class TestMHI1Strategy(unittest.TestCase):
    def _create_candles(self, n=120, base_price=100.0, trend=0.0, last_colors=None, end_minute=4):
        """
        Gera DataFrame sintético com N candles de 1m.
        end_minute: minuto do último candle (padrão 4 -> final do quadrante: 10:04, 10:09, etc.)
        last_colors: lista de strings ('green', 'red', 'doji') para os últimos candles.
        """
        # Timestamp de referência terminando no minuto desejado
        # Ex: end_minute=4 -> timestamp 1700000000 + 4 * 60 = 1700000240
        base_ts = 1700000000
        # Alinha base_ts para minuto 0
        base_ts = (base_ts // 300) * 300
        target_ts = base_ts + (end_minute * 60)
        
        timestamps = [target_ts - (n - 1 - i) * 60 for i in range(n)]
        
        closes = []
        opens = []
        curr = base_price
        for i in range(n):
            curr += trend
            opens.append(curr)
            closes.append(curr + 0.1)  # default green
            
        df = pd.DataFrame({
            "from": timestamps,
            "open": opens,
            "close": closes,
            "high": [max(o, c) + 0.05 for o, c in zip(opens, closes)],
            "low": [min(o, c) - 0.05 for o, c in zip(opens, closes)],
            "volume": [100] * n,
        })
        
        if last_colors:
            k = len(last_colors)
            for idx, color in enumerate(last_colors):
                row_idx = n - k + idx
                o = float(df.loc[row_idx, "open"])
                if color == "green":
                    df.loc[row_idx, "close"] = o + 0.5
                elif color == "red":
                    df.loc[row_idx, "close"] = o - 0.5
                elif color == "doji":
                    df.loc[row_idx, "close"] = o
                    
        return df

    def test_timing_filter(self):
        """Valida que o sinal só é gerado no candle 5 do quadrante (minuto % 5 == 4)."""
        # Minutos 0, 1, 2, 3 não devem disparar entrada
        for m in (0, 1, 2, 3):
            df = self._create_candles(n=120, last_colors=["green", "green", "red"], end_minute=m)
            sig = mhi_1_signal(df, require_trend=False)
            self.assertIsNone(sig, f"Minuto {m} não deveria gerar sinal")

        # Minuto 4 (final do quadrante) deve processar e disparar
        df_valid = self._create_candles(n=120, last_colors=["green", "green", "red"], end_minute=4)
        sig = mhi_1_signal(df_valid, require_trend=False)
        self.assertEqual(sig, "put")

    def test_minority_logic(self):
        """Valida detecção da minoria entre as velas 3, 4 e 5."""
        # 2 verdes, 1 vermelha -> minoria vermelha -> PUT
        df = self._create_candles(n=120, last_colors=["green", "green", "red"], end_minute=4)
        self.assertEqual(mhi_1_signal(df, require_trend=False), "put")

        # 2 vermelhas, 1 verde -> minoria verde -> CALL
        df = self._create_candles(n=120, last_colors=["red", "red", "green"], end_minute=4)
        self.assertEqual(mhi_1_signal(df, require_trend=False), "call")

        # 3 verdes -> minoria vermelha -> PUT
        df = self._create_candles(n=120, last_colors=["green", "green", "green"], end_minute=4)
        self.assertEqual(mhi_1_signal(df, require_trend=False), "put")

        # 3 vermelhas -> minoria verde -> CALL
        df = self._create_candles(n=120, last_colors=["red", "red", "red"], end_minute=4)
        self.assertEqual(mhi_1_signal(df, require_trend=False), "call")

    def test_anti_doji_filter(self):
        """Valida que qualquer Doji (open == close) nas 3 velas de análise descarta o trade."""
        # Doji na vela 3
        df1 = self._create_candles(n=120, last_colors=["doji", "green", "red"], end_minute=4)
        self.assertIsNone(mhi_1_signal(df1, require_trend=False))

        # Doji na vela 4
        df2 = self._create_candles(n=120, last_colors=["green", "doji", "green"], end_minute=4)
        self.assertIsNone(mhi_1_signal(df2, require_trend=False))

        # Doji na vela 5
        df3 = self._create_candles(n=120, last_colors=["green", "green", "doji"], end_minute=4)
        self.assertIsNone(mhi_1_signal(df3, require_trend=False))

    def test_trend_filter_ema(self):
        """Valida o filtro de micro-tendência EMA 100."""
        # Tendência de Alta forte: preço subindo 1.0 por candle
        df_uptrend = self._create_candles(n=120, base_price=10.0, trend=1.0, last_colors=["red", "red", "green"], end_minute=4)
        # Sinal base é CALL. Como estamos em alta, close > EMA100 -> deve aprovar CALL
        sig = mhi_1_signal(df_uptrend, trend_ema=100, require_trend=True)
        self.assertEqual(sig, "call")

        # No mesmo uptrend forte, se o sinal for PUT (2 verdes, 1 vermelha), deve ser bloqueado por ser contra a tendência
        df_uptrend_put = self._create_candles(n=120, base_price=10.0, trend=1.0, last_colors=["green", "green", "red"], end_minute=4)
        sig = mhi_1_signal(df_uptrend_put, trend_ema=100, require_trend=True)
        self.assertIsNone(sig)

        # Tendência de Baixa forte: preço caindo -1.0 por candle
        df_downtrend = self._create_candles(n=120, base_price=500.0, trend=-1.0, last_colors=["green", "green", "red"], end_minute=4)
        # Sinal base é PUT. Como estamos em baixa, close < EMA100 -> deve aprovar PUT
        sig = mhi_1_signal(df_downtrend, trend_ema=100, require_trend=True)
        self.assertEqual(sig, "put")

        # No mesmo downtrend forte, se o sinal for CALL, deve ser bloqueado por ser contra a tendência
        df_downtrend_call = self._create_candles(n=120, base_price=500.0, trend=-1.0, last_colors=["red", "red", "green"], end_minute=4)
        sig = mhi_1_signal(df_downtrend_call, trend_ema=100, require_trend=True)
        self.assertIsNone(sig)

    def test_dispatcher_integration(self):
        """Valida despacho através de get_signal('mhi_1', df, cfg)."""
        df = self._create_candles(n=120, last_colors=["red", "red", "green"], end_minute=4)
        
        class DummyCfg:
            MHI_TREND_EMA = 100
            MHI_REQUIRE_TREND = False
            
        sig = get_signal("mhi_1", df, DummyCfg())
        self.assertEqual(sig, "call")


if __name__ == "__main__":
    unittest.main()
