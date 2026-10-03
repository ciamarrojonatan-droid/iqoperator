import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from train_xgb_v2 import compute_all_features
import pickle
import json

def generate_mhi_dataset(csv_path="data/BTCUSDT_M1_60d.csv"):
    print(f"Carregando dados brutos M1 de {csv_path}...")
    df = pd.read_csv(csv_path)
    
    # Adicionando features técnicas
    print("Calculando features técnicas (XGBoost)...")
    df = compute_all_features(df)
    
    closes = df["close"].values
    opens = df["open"].values
    times = df["time"].values
    
    # Extrair sinais MHI
    signals = []
    print("Extraindo sinais MHI Puros...")
    for i in range(65, len(df) - 1):
        minute_mod = (int(times[i]) // 60) % 5
        if minute_mod != 4:  # MHI atua no 5o minuto de cada bloco M5
            continue
            
        colors = []
        valid = True
        for k in range(i - 2, i + 1):
            if closes[k] > opens[k]: colors.append("green")
            elif closes[k] < opens[k]: colors.append("red")
            else:
                valid = False
                break
        if not valid: continue
        
        greens = colors.count("green")
        reds = colors.count("red")
        
        if greens > reds: sig = "put"
        elif reds > greens: sig = "call"
        else: continue
            
        nxt = closes[i+1]
        if nxt == closes[i]: continue
        won = (sig == "call" and nxt > closes[i]) or (sig == "put" and nxt < closes[i])
        
        # Guardar features no momento 'i' (quando a decisão é tomada) + Label (won)
        row_features = df.iloc[i].copy()
        row_features["target"] = 1 if won else 0
        row_features["signal_dir"] = 1 if sig == "call" else 0
        signals.append(row_features)

    sdf = pd.DataFrame(signals)
    print(f"Total de sinais MHI gerados: {len(sdf)}")
    w_mhi = sdf["target"].sum()
    print(f"Winrate MHI Pura (Baseline): {w_mhi/len(sdf):.2%} (W: {w_mhi}, L: {len(sdf)-w_mhi})")
    
    return sdf

def train_xgb(sdf):
    print("\nPreparando dados para o modelo XGBoost...")
    # Filtrar features (remover open, high, low, close brutos, ts)
    drop_cols = ["open", "high", "low", "close", "time", "target", "from", "date", "datetime", "next_candle_dir", "y", "candle_dir"]
    feature_cols = [c for c in sdf.columns if c not in drop_cols]
    
    X = sdf[feature_cols]
    y = sdf["target"]
    
    # Separando 70% treino, 30% teste OOS
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, shuffle=False)
    
    print(f"Treinando em {len(X_train)} sinais, validando em {len(X_test)}...")
    clf = XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        n_jobs=-1,
        random_state=42
    )
    
    clf.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
    
    # Simulando o Threshold
    probs = clf.predict_proba(X_test)[:, 1]
    
    thresholds = [0.5, 0.52, 0.54, 0.55, 0.58, 0.60]
    print("\n=== Resultado OOS (Filtro ML) ===")
    for t in thresholds:
        passed = probs >= t
        total_passed = passed.sum()
        if total_passed > 0:
            wins = y_test[passed].sum()
            wr = wins / total_passed
            print(f"Threshold >= {t:.2f} | Trades: {total_passed}/{len(X_test)} ({total_passed/len(X_test):.1%}) | Win Rate: {wr:.2%} (W: {wins}, L: {total_passed-wins})")
        else:
            print(f"Threshold >= {t:.2f} | 0 trades aprovados.")

    # Save the model
    import os
    os.makedirs("models", exist_ok=True)
    model_path = "models/xgb_filter_v2.json"
    clf.save_model(model_path)
    print(f"\nModelo salvo em {model_path}!")

if __name__ == "__main__":
    sdf = generate_mhi_dataset()
    train_xgb(sdf)
