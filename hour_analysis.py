"""Analisa a performance por hora do dia no M5 com ML threshold = 0.55"""
import pandas as pd
import numpy as np
import warnings
from backtest_portfolio import bollinger_touch_signals
from ml_filter import MLFilter
from xgboost import XGBClassifier

warnings.filterwarnings("ignore")

def main():
    print("Loading ML...")
    ml = MLFilter(threshold=0.55)
    
    df_m5 = pd.read_csv("data/BTCUSDT_M5_60d.csv")
    df_m5.rename(columns={"time": "timestamp"}, inplace=True)
    df_m5["datetime"] = pd.to_datetime(df_m5["timestamp"], unit="s", utc=True)
    
    print("Calculating signals...")
    sigs = bollinger_touch_signals(df_m5)
    
    print("Computing ML features...")
    features = ml.compute_features(df_m5)
    
    # Predict all
    if "datetime" in features.columns:
        features = features.drop(columns=["datetime"])
    
    X = features[ml.feature_cols].copy()
    for col in X.columns:
        X[col] = pd.to_numeric(X[col], errors='coerce').fillna(0)
        
    probs = ml.model.predict_proba(X)[:, 1]
    
    results = []
    for s in sigs:
        idx = s["idx"]
        prob = probs[idx]
        if prob >= 0.55:
            hour = df_m5.iloc[idx]["datetime"].hour
            results.append({
                "hour": hour,
                "won": s["won"],
                "prob": prob
            })
            
    res_df = pd.DataFrame(results)
    print("\n--- PERFORMANCE POR HORA DO DIA (M5 / Threshold 0.55) ---")
    
    summary = []
    for hour in range(24):
        h_df = res_df[res_df["hour"] == hour]
        trades = len(h_df)
        if trades > 0:
            wins = h_df["won"].sum()
            wr = wins / trades
            summary.append({"Hora": hour, "Trades": trades, "Winrate": wr})
            
    summary_df = pd.DataFrame(summary).sort_values("Hora")
    print(summary_df.to_string(index=False, formatters={'Winrate': '{:.2%}'.format}))
    
    # Simula remover as piores horas
    bad_hours = summary_df[summary_df["Winrate"] < 0.50]["Hora"].tolist()
    filtered = res_df[~res_df["hour"].isin(bad_hours)]
    
    f_trades = len(filtered)
    f_wins = filtered["won"].sum()
    f_wr = f_wins / f_trades if f_trades > 0 else 0
    
    print(f"\nSe cortarmos as horas tóxicas {bad_hours}:")
    print(f"Trades: {f_trades} (Ainda {(f_trades/60):.2f} por dia)")
    print(f"Winrate sobe para: {f_wr:.2%}")

if __name__ == "__main__":
    main()
