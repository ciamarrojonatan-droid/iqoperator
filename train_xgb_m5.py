import os
import time
import pickle
import numpy as np
import pandas as pd
from xgboost import XGBClassifier
from hyperopt import fmin, tpe, hp, Trials, STATUS_OK
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import shap
import matplotlib.pyplot as plt
import ml_filter

# Re-use compute_all_features from train_xgb_v2 if possible, but to be robust we'll just import it or redefine it.
from train_xgb_v2 import compute_all_features

def main():
    print("[TRAIN M5] Loading dataset...")
    df = pd.read_csv("data/BTCUSDT_M5_3y.csv")
    
    print("[TRAIN M5] Computing features...")
    # This also computes 'y' as next-candle reversal in train_xgb_v2, but we will overwrite it with Bollinger Touch logic.
    df_feat = compute_all_features(df)
    
    # Compute Bollinger Touch signal logic
    # period = 20, mult = 2.0
    bb_sma = df_feat["close"].rolling(20).mean()
    bb_std = df_feat["close"].rolling(20).std()
    bb_upper = bb_sma + 2.0 * bb_std
    bb_lower = bb_sma - 2.0 * bb_std
    
    # Signal occurs if close > upper (put) or close < lower (call)
    # We only care about rows where a signal was generated.
    is_call = df_feat["close"] < bb_lower
    is_put = df_feat["close"] > bb_upper
    
    # Next candle direction
    next_close = df_feat["close"].shift(-1)
    next_open = df_feat["open"].shift(-1)
    
    # Win condition
    # Call win: next_close > next_open
    # Put win: next_close < next_open
    call_win = is_call & (next_close > next_open)
    put_win = is_put & (next_close < next_open)
    
    df_feat["is_signal"] = is_call | is_put
    df_feat["y"] = (call_win | put_win).astype(int)
    
    # Filter only rows with signals
    df_signals = df_feat[df_feat["is_signal"] == True].copy()
    df_signals = df_signals.dropna()
    
    features = list(ml_filter.FEATURE_COLS)
    
    # Ensure all features exist
    missing = [f for f in features if f not in df_signals.columns]
    if missing:
        print(f"[ERROR] Missing features: {missing}")
        return
        
    X = df_signals[features]
    y = df_signals["y"]
    
    print(f"[TRAIN M5] Signals extracted: {len(X)}. Win rate: {y.mean():.2%}")
    
    if len(X) < 100:
        print("[TRAIN M5] Not enough signals for ML.")
        return
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
    
    def objective(space):
        clf = XGBClassifier(
            n_estimators=int(space['n_estimators']),
            max_depth=int(space['max_depth']),
            learning_rate=space['learning_rate'],
            gamma=space['gamma'],
            min_child_weight=int(space['min_child_weight']),
            subsample=space['subsample'],
            colsample_bytree=space['colsample_bytree'],
            use_label_encoder=False,
            eval_metric="logloss",
            random_state=42
        )
        clf.fit(X_train, y_train)
        pred = clf.predict(X_test)
        acc = accuracy_score(y_test, pred)
        return {'loss': -acc, 'status': STATUS_OK, 'model': clf}

    space = {
        'max_depth': hp.quniform("max_depth", 3, 9, 1),
        'learning_rate': hp.uniform("learning_rate", 0.01, 0.2),
        'gamma': hp.uniform("gamma", 0.0, 0.5),
        'min_child_weight': hp.quniform("min_child_weight", 1, 10, 1),
        'subsample': hp.uniform("subsample", 0.6, 1.0),
        'colsample_bytree': hp.uniform("colsample_bytree", 0.6, 1.0),
        'n_estimators': hp.quniform("n_estimators", 50, 300, 10)
    }

    print("[TRAIN M5] Running Hyperopt...")
    trials = Trials()
    best = fmin(fn=objective, space=space, algo=tpe.suggest, max_evals=20, trials=trials)
    
    best_model = trials.best_trial['result']['model']
    best_acc = -trials.best_trial['result']['loss']
    print(f"[TRAIN M5] Best Accuracy: {best_acc:.4f}")
    
    # Save model
    os.makedirs("models", exist_ok=True)
    model_path = "models/xgb_filter_m5.pkl"
    
    meta = {
        "accuracy": best_acc,
        "win_rate_base": float(y.mean()),
        "threshold": 0.62,
        "n_samples": len(X),
        "timestamp": time.time()
    }
    
    with open(model_path, "wb") as f:
        pickle.dump({
            "model": best_model,
            "feature_cols": features,
            "threshold": 0.62,
            "meta": meta
        }, f)
        
    print(f"[TRAIN M5] Model saved to {model_path}")
    
    # Plot SHAP values
    try:
        print("[TRAIN M5] Computing SHAP values...")
        explainer = shap.TreeExplainer(best_model)
        shap_values = explainer.shap_values(X_test)
        plt.figure(figsize=(10, 6))
        shap.summary_plot(shap_values, X_test, show=False)
        plt.savefig("models/shap_m5.png", bbox_inches='tight')
        plt.close()
        print("[TRAIN M5] SHAP summary saved to models/shap_m5.png")
    except Exception as e:
        print(f"[TRAIN M5] Failed to plot SHAP: {e}")

if __name__ == "__main__":
    main()
