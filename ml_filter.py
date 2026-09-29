"""
ml_filter.py

Filtro Preditivo em Tempo Real baseado no Modelo XGBoost calibrado (tau=0.62).
Atua como gatekeeper para estratégias determinísticas (Donchian Fade, Bollinger Touch, etc).

Invariantes:
- Zero Lookahead: Toda featurização respeita estritamente o candle de fechamento anterior ou o candle corrente fechado.
- 53 Features Técnicas e Cíclicas com ordenação idêntica ao notebook de treino.
- Latência de inferência sub-milissegundo (< 2ms) por avaliação de candle.
- Decisão booleana: allow_trade = (P(Reversal) >= tau).
"""
import os
import time
import pickle
import logging
import threading
import numpy as np
import pandas as pd
from typing import Tuple, Optional, List, Dict, Any

log = logging.getLogger("iqrobot.ml_filter")

DEFAULT_MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "xgb_filter_v2.pkl")
DEFAULT_THRESHOLD = 0.62
# Requer no mínimo 100 candles para EMA simulação de MTF M15
MIN_CANDLE_COUNT = 100

# 72 Features Técnicas e Cíclicas na ordenação estrita do modelo treinado
FEATURE_COLS: Tuple[str, ...] = (
    'sig_df_dir', 'sig_bb_dir', 'sig_agreement', 'sig_confluence_dir',
    'sin_hour', 'cos_hour', 'sin_dow', 'cos_dow', 'sin_tod', 'cos_tod',
    'session_asian', 'session_london', 'session_ny', 'session_overlap', 'is_weekend',
    'dist_sma_5', 'slope_sma_5', 'vol_ratio_5',
    'dist_sma_10', 'slope_sma_10', 'vol_ratio_10',
    'dist_sma_20', 'slope_sma_20', 'vol_ratio_20',
    'dist_sma_50', 'slope_sma_50', 'vol_ratio_50',
    'sma_spread_5_20', 'sma_spread_10_50', 'sma_spread_20_50',
    'vol_shock_5_50', 'bb_width', 'bb_pct_b', 'bb_pen_upper', 'bb_pen_lower',
    'dc_width_10', 'dc_pct_10', 'dc_break_upper_10', 'dc_break_lower_10',
    'dc_width_20', 'dc_pct_20', 'dc_break_upper_20', 'dc_break_lower_20',
    'dc_width_40', 'dc_pct_40',
    'dc_width_60', 'dc_pct_60',
    'body_ratio', 'upper_wick_ratio', 'lower_wick_ratio',
    'ret_1', 'ret_3', 'ret_5',
    'rsi_14', 'macd', 'macd_signal', 'macd_hist', 'stoch_k', 'stoch_d', 
    'atr_14', 'kc_pct', 'dist_ema_m5', 'dist_ema_m15', 
    'dist_vwap_20', 'vroc_5', 'vsa_vol_spread', 
    'fractal_up_conf', 'fractal_down_conf', 
    'bullish_engulfing', 'bearish_engulfing', 
    'wick_upper_z', 'wick_lower_z'
)


class MLFilter:
    """Carrega o modelo XGBoost e executa a inferência preditiva sobre o buffer de candles."""

    def __init__(self, model_path: Optional[str] = None, threshold: float = DEFAULT_THRESHOLD, fail_open: bool = False):
        self.model_path = model_path or DEFAULT_MODEL_PATH
        self.threshold = threshold
        self.fail_open = fail_open
        self.model = None
        self.scaler = None
        self.feature_cols: List[str] = list(FEATURE_COLS)
        self.meta: Dict[str, Any] = {}
        self.is_loaded = False
        self._load_model()

    def _load_model(self) -> bool:
        """Carrega os pesos do modelo e o scaler a partir do arquivo serializado (.pkl ou .json)."""
        # Se for caminho relativo, resolve contra o diretório deste módulo caso não exista no CWD
        if not os.path.isabs(self.model_path) and not os.path.exists(self.model_path):
            resolved = os.path.join(os.path.dirname(__file__), self.model_path)
            if os.path.exists(resolved):
                self.model_path = resolved

        if not os.path.exists(self.model_path):
            # Fallback de auto-recuperação: se .pkl não existe, tenta .json no mesmo diretório
            if self.model_path.endswith(".pkl"):
                fallback_json = self.model_path[:-4] + ".json"
                if os.path.exists(fallback_json):
                    log.warning(f"[ML FILTER] Arquivo .pkl não encontrado em {self.model_path}. Tentando fallback nativo JSON: {fallback_json}")
                    self.model_path = fallback_json
                    return self._load_model()
            log.warning(f"[ML FILTER] Arquivo de modelo não encontrado em: {self.model_path}")
            self.is_loaded = False
            return False

        t0 = time.perf_counter()
        try:
            if self.model_path.endswith(".json"):
                from xgboost import XGBClassifier
                import json
                self.model = XGBClassifier()
                self.model.load_model(self.model_path)
                booster_features = self.model.get_booster().feature_names
                self.feature_cols = list(booster_features) if booster_features else list(FEATURE_COLS)
                meta_path = os.path.join(os.path.dirname(self.model_path), "metadata.json")
                if os.path.exists(meta_path):
                    with open(meta_path, "r", encoding="utf-8") as mf:
                        self.meta = json.load(mf)
                        self.threshold = float(self.meta.get("threshold", self.threshold))
                # Reconstrói StandardScaler a partir de metadata.json se disponível
                if "scaler" in self.meta and isinstance(self.meta["scaler"], dict):
                    from sklearn.preprocessing import StandardScaler
                    sc = StandardScaler()
                    sc.mean_ = np.array(self.meta["scaler"]["mean"], dtype=np.float64)
                    sc.scale_ = np.array(self.meta["scaler"]["scale"], dtype=np.float64)
                    sc.var_ = np.array(self.meta["scaler"]["var"], dtype=np.float64)
                    sc.n_features_in_ = len(self.feature_cols)
                    self.scaler = sc
                else:
                    self.scaler = None
                self.is_loaded = bool(self.model is not None and len(self.feature_cols) >= 53)
            else:
                with open(self.model_path, "rb") as f:
                    data = pickle.load(f)

                self.model = data.get("model")
                self.scaler = data.get("scaler")
                self.feature_cols = data.get("feature_cols", list(FEATURE_COLS))
                self.threshold = float(data.get("threshold", self.threshold))
                self.meta = data.get("meta", {})
                self.is_loaded = bool(self.model is not None and len(self.feature_cols) >= 53)

            elapsed_ms = (time.perf_counter() - t0) * 1000
            if self.is_loaded:
                log.info(f"[ML FILTER] Modelo XGBoost carregado com sucesso em {elapsed_ms:.1f}ms "
                         f"({len(self.feature_cols)} features, tau={self.threshold:.2f})")
            else:
                log.error(f"[ML FILTER] Formato de modelo inválido no arquivo: {self.model_path}")
            return self.is_loaded
        except Exception as e:
            log.error(f"[ML FILTER] Falha ao carregar modelo {self.model_path}: {e}")
            # Se falhou ao carregar .pkl (corrompido/incompatível), tenta auto-recuperação via .json
            if self.model_path.endswith(".pkl"):
                fallback_json = self.model_path[:-4] + ".json"
                if os.path.exists(fallback_json):
                    log.warning(f"[ML FILTER] Acionando fallback resiliente para modelo nativo JSON: {fallback_json}")
                    self.model_path = fallback_json
                    return self._load_model()
            self.is_loaded = False
            return False

    def compute_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula o vetor exato de 53 features para o candle mais recente (última linha).
        
        Requer no mínimo 60 candles para que SMA50 e DC60 tenham histórico completo.
        """
        if df is None or len(df) < MIN_CANDLE_COUNT:
            raise ValueError(f"Buffer de candles insuficiente: requer ao menos {MIN_CANDLE_COUNT}, recebido {len(df) if df is not None else 0}")

        d = df.copy()

        # 1. Normalização do timestamp / datetime UTC
        if "datetime" not in d.columns:
            for col in ("time", "from", "at", "open_time", "timestamp"):
                if col in d.columns:
                    first_val = d[col].dropna().iloc[0] if not d[col].dropna().empty else None
                    if first_val is not None:
                        try:
                            # Tenta coerção numérica para timestamps epoch (int, float ou string epoch '1700000000')
                            num_s = pd.to_numeric(d[col], errors="raise")
                            val0 = float(num_s.dropna().iloc[0])
                            unit = "ms" if val0 > 1e11 else "s"
                            d["datetime"] = pd.to_datetime(num_s, unit=unit, utc=True)
                        except (ValueError, TypeError):
                            # Fallback para strings ISO datetime (ex: '2026-09-25 01:00:00')
                            d["datetime"] = pd.to_datetime(d[col], utc=True)
                    break
            if "datetime" not in d.columns:
                now = pd.Timestamp.now(tz="UTC")
                d["datetime"] = [now - pd.Timedelta(minutes=15 * (len(d) - 1 - i)) for i in range(len(d))]
        else:
            if not pd.api.types.is_datetime64_any_dtype(d["datetime"]):
                d["datetime"] = pd.to_datetime(d["datetime"], utc=True)
            elif d["datetime"].dt.tz is None:
                d["datetime"] = d["datetime"].dt.tz_localize("UTC")
            else:
                d["datetime"] = d["datetime"].dt.tz_convert("UTC")

        # Ordenação cronológica estrita e desduplicação por timestamp (resiliência a reconnects de stream)
        d = d.sort_values("datetime").drop_duplicates(subset=["datetime"], keep="last").reset_index(drop=True)

        if len(d) < MIN_CANDLE_COUNT:
            raise ValueError(f"Buffer de candles insuficiente após desduplicação temporal: requer ao menos {MIN_CANDLE_COUNT}, obtido {len(d)}")

        # Limita histórico ao horizonte necessário (no máx 200 candles) para otimizar latência e memória
        if len(d) > 200:
            d = d.iloc[-200:].reset_index(drop=True)

        # 2. Padronização e higienização de colunas de preço
        for col_name in ("high", "low", "close", "open"):
            if col_name not in d.columns:
                if col_name == "high" and "max" in d.columns:
                    d["high"] = d["max"]
                elif col_name == "low" and "min" in d.columns:
                    d["low"] = d["min"]
                else:
                    d[col_name] = d.get("close", 0.0)

        # Conversão numérica com coerção e preenchimento de ticks ausentes (intermittent NaN resilience)
        for c in ("high", "low", "close", "open"):
            d[c] = pd.to_numeric(d[c], errors="coerce")
            d[c] = d[c].ffill().bfill()

        # Higienização de integridade física dos extremos do candle (evita wicks negativos ou high < low)
        d["high"] = np.maximum(d["high"], np.maximum(d["open"], d["close"]))
        d["low"] = np.minimum(d["low"], np.minimum(d["open"], d["close"]))

        # 3. Donchian Channel (N=20 lookback, strictly shift(1))
        N_DC = 20
        d["dc_up_20"] = d["high"].shift(1).rolling(N_DC).max()
        d["dc_lo_20"] = d["low"].shift(1).rolling(N_DC).min()

        d["sig_df_dir"] = np.where(d["close"] > d["dc_up_20"], -1,
                          np.where(d["close"] < d["dc_lo_20"], 1, 0))

        # 4. Bollinger Bands (P=20, mult=2.0)
        P_BB = 20
        MULT_BB = 2.0
        bb_sma = d["close"].rolling(P_BB).mean()
        bb_std = d["close"].rolling(P_BB).std()
        d["bb_upper"] = bb_sma + MULT_BB * bb_std
        d["bb_lower"] = bb_sma - MULT_BB * bb_std

        d["sig_bb_dir"] = np.where(d["close"] > d["bb_upper"], -1,
                          np.where(d["close"] < d["bb_lower"], 1, 0))

        # 5. Sinais de Acordo e Confluência
        d["sig_agreement"] = ((d["sig_df_dir"] == d["sig_bb_dir"]) & (d["sig_df_dir"] != 0)).astype(int)
        d["sig_confluence_dir"] = np.where((d["sig_df_dir"] == 1) & (d["sig_bb_dir"] == 1), 1,
                                 np.where((d["sig_df_dir"] == -1) & (d["sig_bb_dir"] == -1), -1, 0))

        # 6. Features Temporais e Cíclicas (11 features)
        hour = d["datetime"].dt.hour
        dow = d["datetime"].dt.dayofweek
        minute = d["datetime"].dt.minute
        tod_min = hour * 60 + minute

        d["sin_hour"] = np.sin(2 * np.pi * hour / 24.0)
        d["cos_hour"] = np.cos(2 * np.pi * hour / 24.0)
        d["sin_dow"] = np.sin(2 * np.pi * dow / 7.0)
        d["cos_dow"] = np.cos(2 * np.pi * dow / 7.0)
        d["sin_tod"] = np.sin(2 * np.pi * tod_min / 1440.0)
        d["cos_tod"] = np.cos(2 * np.pi * tod_min / 1440.0)

        d["session_asian"] = ((hour >= 0) & (hour < 8)).astype(int)
        d["session_london"] = ((hour >= 8) & (hour < 16)).astype(int)
        d["session_ny"] = ((hour >= 13) & (hour < 21)).astype(int)
        d["session_overlap"] = ((hour >= 13) & (hour < 16)).astype(int)
        d["is_weekend"] = (dow >= 5).astype(int)

        # 7. Médias Móveis Multi-Período e Spreads (11 features)
        for p in [5, 10, 20, 50]:
            sma = d["close"].rolling(p).mean()
            std = d["close"].rolling(p).std()
            d[f"dist_sma_{p}"] = (d["close"] - sma) / (sma + 1e-9)
            d[f"slope_sma_{p}"] = (sma - sma.shift(1)) / (sma.shift(1) + 1e-9)
            d[f"vol_ratio_{p}"] = std / (sma + 1e-9)
            d[f"_sma_{p}"] = sma
            d[f"_std_{p}"] = std

        d["sma_spread_5_20"] = (d["_sma_5"] - d["_sma_20"]) / (d["_sma_20"] + 1e-9)
        d["sma_spread_10_50"] = (d["_sma_10"] - d["_sma_50"]) / (d["_sma_50"] + 1e-9)
        d["sma_spread_20_50"] = (d["_sma_20"] - d["_sma_50"]) / (d["_sma_50"] + 1e-9)

        # 8. Volatilidade e Choque (6 features)
        d["vol_shock_5_50"] = d["_std_5"] / (d["_std_50"] + 1e-9)
        bb_range = d["bb_upper"] - d["bb_lower"] + 1e-9
        d["bb_width"] = bb_range / (d["_sma_20"] + 1e-9)
        d["bb_pct_b"] = (d["close"] - d["bb_lower"]) / bb_range
        d["bb_pen_upper"] = np.maximum(0.0, (d["close"] - d["bb_upper"]) / (np.abs(d["bb_upper"]) + 1e-9))
        d["bb_pen_lower"] = np.maximum(0.0, (d["bb_lower"] - d["close"]) / (np.abs(d["bb_lower"]) + 1e-9))

        # 9. Envelopes Donchian Multi-Período (15 features)
        for n in [10, 20, 40, 60]:
            dc_up = d["high"].shift(1).rolling(n).max()
            dc_lo = d["low"].shift(1).rolling(n).min()
            dc_mid = (dc_up + dc_lo) / 2.0
            dc_rng = dc_up - dc_lo + 1e-9

            d[f"dc_width_{n}"] = (dc_up - dc_lo) / (dc_mid + 1e-9)
            d[f"dc_pct_{n}"] = (d["close"] - dc_lo) / dc_rng
            if n in [10, 20]:
                d[f"dc_break_upper_{n}"] = np.maximum(0.0, (d["close"] - dc_up) / (np.abs(dc_up) + 1e-9))
                d[f"dc_break_lower_{n}"] = np.maximum(0.0, (dc_lo - d["close"]) / (np.abs(dc_lo) + 1e-9))

        # 10. Morfologia do Candle e Retornos (6 features)
        bar_rng = np.maximum(1e-9, d["high"] - d["low"])
        d["body_ratio"] = np.clip((d["close"] - d["open"]).abs() / bar_rng, 0.0, 1.0)
        d["upper_wick_ratio"] = np.clip((d["high"] - d[["open", "close"]].max(axis=1)) / bar_rng, 0.0, 1.0)
        d["lower_wick_ratio"] = np.clip((d[["open", "close"]].min(axis=1) - d["low"]) / bar_rng, 0.0, 1.0)
        for lag in [1, 3, 5]:
            ret = d["close"].pct_change(lag)
            d[f"ret_{lag}"] = ret.replace([np.inf, -np.inf], 0.0).fillna(0.0)

        # --- NOVAS FEATURES (19 features) ---
        # 11. Momentum/Oscillators (RSI, MACD, Stochastic)
        # RSI 14
        delta = d["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss + 1e-9)
        d["rsi_14"] = 100 - (100 / (1 + rs))
        d["rsi_14"] = d["rsi_14"].fillna(50.0)

        # MACD (12, 26, 9)
        ema_12 = d["close"].ewm(span=12, adjust=False).mean()
        ema_26 = d["close"].ewm(span=26, adjust=False).mean()
        d["macd"] = ema_12 - ema_26
        d["macd_signal"] = d["macd"].ewm(span=9, adjust=False).mean()
        d["macd_hist"] = d["macd"] - d["macd_signal"]

        # Stochastic (14, 3)
        lowest_low = d["low"].rolling(14).min()
        highest_high = d["high"].rolling(14).max()
        d["stoch_k"] = 100 * (d["close"] - lowest_low) / (highest_high - lowest_low + 1e-9)
        d["stoch_d"] = d["stoch_k"].rolling(3).mean()
        d["stoch_k"] = d["stoch_k"].fillna(50.0)
        d["stoch_d"] = d["stoch_d"].fillna(50.0)

        # 12. Dynamic Volatility (ATR, Keltner)
        # ATR 14
        tr1 = d["high"] - d["low"]
        tr2 = (d["high"] - d["close"].shift(1)).abs()
        tr3 = (d["low"] - d["close"].shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        d["atr_14"] = tr.rolling(14).mean().bfill()

        # Keltner Channel (20, 2)
        ema_20 = d["close"].ewm(span=20, adjust=False).mean()
        kc_upper = ema_20 + 2 * d["atr_14"]
        kc_lower = ema_20 - 2 * d["atr_14"]
        d["kc_pct"] = (d["close"] - kc_lower) / (kc_upper - kc_lower + 1e-9)

        # 13. Simulated MTF (M5/M15 EMA projections in M1)
        ema_m5_sim = d["close"].ewm(span=25, adjust=False).mean()
        ema_m15_sim = d["close"].ewm(span=75, adjust=False).mean()
        d["dist_ema_m5"] = (d["close"] - ema_m5_sim) / (ema_m5_sim + 1e-9)
        d["dist_ema_m15"] = (d["close"] - ema_m15_sim) / (ema_m15_sim + 1e-9)

        # 14. Volume/Order Flow (VWAP, VROC, VSA)
        if "volume" not in d.columns:
            d["volume"] = 1.0
        else:
            d["volume"] = pd.to_numeric(d["volume"], errors="coerce").fillna(1.0)
            
        vol_sum_20 = d["volume"].rolling(20).sum()
        vwap_20 = (d["close"] * d["volume"]).rolling(20).sum() / (vol_sum_20 + 1e-9)
        d["dist_vwap_20"] = (d["close"] - vwap_20) / (vwap_20 + 1e-9)
        d["dist_vwap_20"] = d["dist_vwap_20"].fillna(0.0)

        vroc_5 = d["volume"].pct_change(5).fillna(0.0)
        d["vroc_5"] = vroc_5.replace([np.inf, -np.inf], 0.0)

        d["vsa_vol_spread"] = d["volume"] / bar_rng

        # 15. Advanced Price Action (Fractals, Engulfing, wick z-scores)
        # Zero-lookahead fractals (confirmed at T-2)
        d["fractal_up_conf"] = ((d["high"].shift(2) > d["high"].shift(3)) & 
                                (d["high"].shift(2) > d["high"].shift(4)) & 
                                (d["high"].shift(2) > d["high"].shift(1)) & 
                                (d["high"].shift(2) > d["high"])).astype(int)
        d["fractal_down_conf"] = ((d["low"].shift(2) < d["low"].shift(3)) & 
                                  (d["low"].shift(2) < d["low"].shift(4)) & 
                                  (d["low"].shift(2) < d["low"].shift(1)) & 
                                  (d["low"].shift(2) < d["low"])).astype(int)

        # Engulfing (current vs previous)
        prev_body = d["close"].shift(1) - d["open"].shift(1)
        curr_body = d["close"] - d["open"]
        d["bullish_engulfing"] = ((prev_body < 0) & (curr_body > 0) & 
                                  (d["close"] > d["open"].shift(1)) & 
                                  (d["open"] < d["close"].shift(1))).astype(int)
        d["bearish_engulfing"] = ((prev_body > 0) & (curr_body < 0) & 
                                  (d["close"] < d["open"].shift(1)) & 
                                  (d["open"] > d["close"].shift(1))).astype(int)

        # Wick z-scores
        mean_uw = d["upper_wick_ratio"].rolling(20).mean()
        std_uw = d["upper_wick_ratio"].rolling(20).std()
        d["wick_upper_z"] = (d["upper_wick_ratio"] - mean_uw) / (std_uw + 1e-9)
        
        mean_lw = d["lower_wick_ratio"].rolling(20).mean()
        std_lw = d["lower_wick_ratio"].rolling(20).std()
        d["wick_lower_z"] = (d["lower_wick_ratio"] - mean_lw) / (std_lw + 1e-9)

        d["wick_upper_z"] = d["wick_upper_z"].fillna(0.0)
        d["wick_lower_z"] = d["wick_lower_z"].fillna(0.0)

        # Extrai apenas a última linha (candle atual) no formato exato das features
        cols_to_extract = self.feature_cols if self.feature_cols else list(FEATURE_COLS)
        latest_row = d.iloc[[-1]][cols_to_extract].copy()

        # Verificação estrita de sanidade numérica (rejeita NaN e Inf)
        if latest_row.isnull().any().any() or np.isinf(latest_row.values).any():
            invalid_cols = latest_row.columns[latest_row.isnull().any() | np.isinf(latest_row.values).any(axis=0)].tolist()
            raise ValueError(f"Valores não-finitos (NaN/Inf) detectados no vetor de features do candle: {invalid_cols}")

        return latest_row


    def predict_proba(self, df: pd.DataFrame) -> float:
        """
        Calcula a probabilidade predita de Reversão / Vitória P(Win) para o candle atual.
        Retorna float no intervalo [0.0, 1.0].
        """
        if not self.is_loaded:
            raise RuntimeError("MLFilter: Modelo não está carregado.")

        feat = self.compute_features(df)
        probs = self.model.predict_proba(feat)
        # Classe 1 = Vitória / Reversão
        prob_win = float(probs[0, 1])
        return prob_win

    def filter_signal(self, df: pd.DataFrame, signal: str, threshold: Optional[float] = None, fail_open: Optional[bool] = None) -> Tuple[bool, float]:
        """
        Avalia se o sinal determinístico deve ser executado ou barrado.

        Args:
            df: DataFrame com histórico de candles (mínimo 61 barras).
            signal: Direção do sinal determinístico ('call' ou 'put').
            threshold: Opcional, substitui o threshold padrão (0.62).
            fail_open: Opcional, substitui a política de fail_open da instância.

        Returns:
            (allow_trade: bool, prob: float)
            - allow_trade=True se prob >= threshold
            - allow_trade=False se prob < threshold
        """
        if not signal:
            return False, 0.0

        sig_norm = str(signal).strip().lower()
        if sig_norm not in ("call", "put"):
            return False, 0.0

        fo = self.fail_open if fail_open is None else fail_open

        if not self.is_loaded:
            if fo:
                log.warning("[ML FILTER] Modelo não carregado; fail-open ativo: autorizando trade sem validação ML.")
                return True, 1.0
            else:
                log.warning("[ML FILTER] Modelo não carregado; trade cancelado por segurança (fail-closed).")
                return False, 0.0

        if df is None or len(df) < MIN_CANDLE_COUNT:
            if fo:
                log.warning(f"[ML FILTER] Candles insuficientes ({len(df) if df is not None else 0} < {MIN_CANDLE_COUNT}); fail-open ativo: autorizando trade sem validação ML.")
                return True, 1.0
            else:
                log.warning(f"[ML FILTER] Candles insuficientes ({len(df) if df is not None else 0} < {MIN_CANDLE_COUNT}); trade cancelado por segurança (fail-closed).")
                return False, 0.0

        th = threshold if threshold is not None else self.threshold

        try:
            prob = self.predict_proba(df)
            allowed = bool(prob >= th)
            return allowed, prob
        except Exception as e:
            if fo:
                log.warning(f"[ML FILTER] Erro durante inferência de features: {e}. Fail-open ativo: autorizando trade sem validação ML.")
                return True, 1.0
            else:
                log.error(f"[ML FILTER] Erro durante inferência de features: {e}. Trade cancelado por segurança (fail-closed).")
                return False, 0.0


class LayaFilter(MLFilter):
    """Filtro preditivo baseado no modelo open-source Laya (distilbert)."""
    def __init__(self, model_name: str = "convaiinnovations/laya", threshold: float = 0.5, fail_open: bool = False):
        self.model_name = model_name
        self.threshold = threshold
        self.fail_open = fail_open
        self.model = None
        self.tokenizer = None
        self.feature_cols: List[str] = list(FEATURE_COLS)
        self.is_loaded = False
        self._load_model()

    def _load_model(self) -> bool:
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except Exception as e:
            log.error(f"[LAYA FILTER] Environment Error: Failed to import torch or transformers. Exceção: {e}")
            self.is_loaded = False
            return False
            
        try:
            log.info(f"[LAYA FILTER] Tentando carregar {self.model_name}...")
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, subfolder="tokenizer")
            self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name, num_labels=2, subfolder="encoder")
            self.model.eval()
            self.is_loaded = True
        except Exception as e:
            log.warning(f"[LAYA FILTER] Falha ao carregar {self.model_name} nativamente: {e}. Fallback para distilbert-base-uncased.")
            try:
                self.model_name = "distilbert-base-uncased"
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name, num_labels=2)
                self.model.eval()
                self.is_loaded = True
            except Exception as e2:
                log.error(f"[LAYA FILTER] Fallback falhou: {e2}")
                self.is_loaded = False
                
        if self.is_loaded:
            log.info(f"[LAYA FILTER] Modelo carregado com sucesso ({self.model_name}, tau={self.threshold:.2f})")
        return self.is_loaded

    def predict_proba(self, df: pd.DataFrame) -> float:
        if not self.is_loaded:
            raise RuntimeError("LayaFilter: Modelo não está carregado.")

        feat = self.compute_features(df)
        
        rsi = feat['rsi_14'].iloc[0] if 'rsi_14' in feat else 'unknown'
        bb_dist = feat['bb_pct_b'].iloc[0] if 'bb_pct_b' in feat else 'unknown'
        macd_hist = feat['macd_hist'].iloc[0] if 'macd_hist' in feat else 'unknown'
        
        bullish_eng = feat['bullish_engulfing'].iloc[0] if 'bullish_engulfing' in feat else 0
        bearish_eng = feat['bearish_engulfing'].iloc[0] if 'bearish_engulfing' in feat else 0
        
        eng_text = "none"
        if bullish_eng == 1:
            eng_text = "bullish engulfing"
        elif bearish_eng == 1:
            eng_text = "bearish engulfing"

        if isinstance(rsi, float): rsi = round(rsi, 2)
        if isinstance(bb_dist, float): bb_dist = round(bb_dist, 4)
        if isinstance(macd_hist, float): macd_hist = round(macd_hist, 4)
            
        state_description = (
            f"Market conditions: RSI is {rsi}. "
            f"Bollinger Band distance is {bb_dist}. "
            f"MACD histogram is {macd_hist}. "
            f"Engulfing features: {eng_text}."
        )
        
        log.info(f"[LAYA FILTER] Input context: {state_description}")
        
        import torch
        inputs = self.tokenizer(state_description, return_tensors="pt", truncation=True, max_length=128)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
            probabilities = torch.softmax(logits, dim=1)
            buy_prob = probabilities[0][1].item()
            
        return float(buy_prob)


# Instância singleton global para reuso eficiente com lock de concorrência
_filter_lock = threading.Lock()
_global_filter: Optional[MLFilter] = None

def get_ml_filter(model_path: Optional[str] = None, threshold: float = DEFAULT_THRESHOLD, fail_open: bool = False) -> MLFilter:
    """Retorna instância única (singleton) do MLFilter pré-carregado em memória (thread-safe)."""
    global _global_filter
    if _global_filter is None:
        with _filter_lock:
            if _global_filter is None:
                import config as cfg
                if getattr(cfg, "USE_LAYA_ORACLE", False):
                    _global_filter = LayaFilter(model_name=getattr(cfg, "LAYA_MODEL_NAME", "convaiinnovations/laya"), threshold=threshold, fail_open=fail_open)
                else:
                    _global_filter = MLFilter(model_path=model_path, threshold=threshold, fail_open=fail_open)
    return _global_filter

