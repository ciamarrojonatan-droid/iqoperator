import os
import numpy as np
import pandas as pd
from xgboost import XGBClassifier
from train_xgb_v2 import compute_all_features
from strategies import mhi_1_signal
import logging

log = logging.getLogger("mhi_router")

class MHIMLRouter:
    def __init__(self, model_path="models/xgb_filter_v2.json", threshold=0.58):
        self.threshold = threshold
        self.clf = XGBClassifier()
        self.is_loaded = False
        if os.path.exists(model_path):
            try:
                self.clf.load_model(model_path)
                self.is_loaded = True
                log.info(f"[MHIMLRouter] Model loaded from {model_path}. Threshold={self.threshold}")
            except Exception as e:
                log.error(f"[MHIMLRouter] Error loading model: {e}")
        else:
            log.warning(f"[MHIMLRouter] Model not found at {model_path}")

        self.drop_cols = ["open", "high", "low", "close", "time", "target", "from", "date", "datetime", "next_candle_dir", "y", "candle_dir"]

    def generate_signals(self, df: pd.DataFrame, payout: float = 0.8) -> pd.Series:
        # Default empty signals
        sig_series = pd.Series(["NO_TRADE"] * len(df), index=df.index)
        if df is None or len(df) < 5:
            return sig_series

        # Execute pure MHI logic
        raw_signal = mhi_1_signal(df, trend_ema=100, require_trend=False)
        if not raw_signal:
            return sig_series
        
        signal_dir = 1 if raw_signal.lower() == "call" else 0

        # Compute features
        try:
            df_feat = compute_all_features(df)
            row_feat = df_feat.iloc[[-1]].copy()
            row_feat["signal_dir"] = signal_dir
            
            # Drop excluded columns
            for c in self.drop_cols:
                if c in row_feat.columns:
                    row_feat = row_feat.drop(columns=[c])
            
            # Predict
            if self.is_loaded:
                prob = self.clf.predict_proba(row_feat)[0, 1]
                if prob >= self.threshold:
                    sig_series.iloc[-1] = raw_signal.upper()
                    self.last_regime = f"ML_PASS({prob:.2f})"
                else:
                    self.last_regime = f"ML_BLOCKED({prob:.2f})"
            else:
                self.last_regime = "NO_MODEL"
        except Exception as e:
            log.error(f"[MHIMLRouter] Inference error: {e}")
            self.last_regime = f"ERR({e})"

        return sig_series
