import os
import pandas as pd
import numpy as np
import xgboost as xgb
from train_xgb_v2 import compute_all_features
import matplotlib.pyplot as plt

print("Loading 1 year EURUSDT M1 Data...")
df = pd.read_csv("data/EURUSDT_M1_1y.csv")
df["datetime"] = pd.to_datetime(df["datetime"])

# Sort just in case
df = df.sort_values("time").reset_index(drop=True)

print(f"Data loaded: {len(df)} rows.")

# 1. Compute Features FIRST (because it drops NAs and resets index)
print("Computing 86 features...")
df_feat = compute_all_features(df)

# 2. Pure MHI Logic to extract base signals
print("Extracting pure MHI base signals from feature dataframe...")
closes = df_feat["close"].values
opens = df_feat["open"].values
mhi_signals = [] # list of (index, signal_direction, won)
for i in range(5, len(df_feat)-1):
    colors = []
    for k in range(i - 2, i + 1):
        if closes[k] > opens[k]: colors.append("green")
        elif closes[k] < opens[k]: colors.append("red")
        else: colors.append("doji")
        
    if "doji" in colors: continue
    
    greens = colors.count("green")
    reds = colors.count("red")
    
    if greens > reds: sig = "put"
    elif reds > greens: sig = "call"
    else: continue
        
    nxt = closes[i+1]
    if nxt == closes[i]: continue
    won = (sig == "call" and nxt > closes[i]) or (sig == "put" and nxt < closes[i])
    
    mhi_signals.append((i, 1 if sig == "call" else 0, int(won)))

print(f"Found {len(mhi_signals)} total MHI signals.")
if len(mhi_signals) == 0:
    print("No signals found.")
    exit()

# Evaluate pure MHI
wins = sum(s[2] for s in mhi_signals)
total = len(mhi_signals)
print(f"--- PURE MHI (No Filter) ---")
print(f"Win Rate: {wins/total*100:.2f}% ({wins}W / {total-wins}L)")

# Build ML dataset
X_rows = []
y_rows = []
for idx, sig_dir, won in mhi_signals:
    row = df_feat.iloc[idx].copy()
    row["signal_dir"] = sig_dir
    X_rows.append(row)
    y_rows.append(won)

X_df = pd.DataFrame(X_rows)
y = np.array(y_rows)

drop_cols = ["open", "high", "low", "close", "time", "target", "from", "date", "datetime", "next_candle_dir", "y", "candle_dir"]
for c in drop_cols:
    if c in X_df.columns:
        X_df = X_df.drop(columns=[c])

print(f"Dataset ready. X shape: {X_df.shape}")

# 3. Test existing BTCUSDT model
print("\n--- Testing Existing BTCUSDT Model on EURUSD ---")
clf_btc = xgb.XGBClassifier()
if os.path.exists("models/xgb_filter_v2.json"):
    clf_btc.load_model("models/xgb_filter_v2.json")
    expected_features = clf_btc.get_booster().feature_names
    X_exact = X_df[expected_features]
    probs_btc = clf_btc.predict_proba(X_exact)[:, 1]
    
    thresholds = [0.55, 0.58, 0.60, 0.65]
    for t in thresholds:
        takes = probs_btc >= t
        if takes.sum() == 0:
            continue
        w = y[takes].sum()
        tot = takes.sum()
        wr = w / tot
        print(f"Threshold >= {t:.2f} | WR: {wr*100:.2f}% | Trades: {tot} ({w}W / {tot-w}L)")
else:
    print("models/xgb_filter_v2.json not found.")

# 4. Train a NEW EURUSD specific model
print("\n--- Training NEW EURUSD Model (Train/Test Split) ---")
split_idx = int(len(X_df) * 0.7)
X_train, y_train = X_df.iloc[:split_idx], y[:split_idx]
X_test, y_test = X_df.iloc[split_idx:], y[split_idx:]

clf_eur = xgb.XGBClassifier(
    n_estimators=300,
    max_depth=4,
    learning_rate=0.03,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=42,
    eval_metric='logloss'
)

clf_eur.fit(
    X_train, y_train,
    eval_set=[(X_test, y_test)],
    verbose=False
)

probs_eur = clf_eur.predict_proba(X_test)[:, 1]

print("--- NEW EURUSD Model Out-Of-Sample Performance ---")
for t in [0.52, 0.54, 0.55, 0.58, 0.60, 0.62]:
    takes = probs_eur >= t
    if takes.sum() == 0:
        continue
    w = y_test[takes].sum()
    tot = takes.sum()
    wr = w / tot
    print(f"Threshold >= {t:.2f} | WR: {wr*100:.2f}% | Trades: {tot} ({w}W / {tot-w}L)")

clf_eur.save_model("models/xgb_filter_eurusd_1y.json")
print("\nSaved new EURUSD model to models/xgb_filter_eurusd_1y.json")
