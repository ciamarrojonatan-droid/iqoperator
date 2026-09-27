import os
import pandas as pd
import numpy as np
from ml_filter import MLFilter
from backtest_portfolio import evaluate_bollinger_touch, compute_all_features

assets = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "EURGBP"]
toxic_hours = [5, 8, 12, 21, 23]
threshold = 0.55
model_path = "models/xgb_filter_m5.pkl"

def main():
    ml = MLFilter(model_path, threshold=threshold)
    if not ml.is_loaded:
        print(f"[ERRO] Modelo ML não carregado de {model_path}.")
        return

    results = []

    for asset in assets:
        csv_path = f"data/{asset}_M5_iq.csv"
        if not os.path.exists(csv_path):
            print(f"[Aviso] {csv_path} não encontrado. Pulando...")
            continue
        
        print(f"Analisando {asset}...")
        df = pd.read_csv(csv_path)
        
        # Ensure datetime is correct
        if "datetime" not in df.columns:
            df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True)
            
        signals = evaluate_bollinger_touch(df)
        if not signals:
            results.append({"Asset": asset, "Trades": 0, "Wins": 0, "Losses": 0, "WinRate": 0.0, "NetProfit": 0.0})
            continue
            
        feat = compute_all_features(df, ml.feature_cols)
        probs = ml.model.predict_proba(feat)[:, 1]
        
        valid_trades = []
        wins = 0
        losses = 0
        
        for s in signals:
            idx = s["idx"]
            hour = df.iloc[idx]["datetime"].hour
            if hour in toxic_hours:
                continue
                
            prob = probs[idx]
            if np.isnan(prob) or prob < threshold:
                continue
                
            valid_trades.append(s)
            if s["won"]:
                wins += 1
            else:
                losses += 1
                
        total = wins + losses
        wr = wins / total if total > 0 else 0.0
        # assuming typical binary payout config where win=$8.7 and loss=-$10 on $10 stake
        profit = wins * 8.7 - losses * 10.0
        
        results.append({
            "Asset": asset,
            "Trades": total,
            "Wins": wins,
            "Losses": losses,
            "WinRate": wr,
            "NetProfit": profit
        })

    # Save to CSV
    out_csv = "data/assets_performance_m5.csv"
    res_df = pd.DataFrame(results)
    res_df.to_csv(out_csv, index=False)
    print(f"\n[OK] Resultados salvos em {out_csv}\n")

    # Markdown Summary
    md = "### Synaptic Hypervisor: Grid Search Analysis\n"
    md += "| Asset | Trades | W/L | Win Rate | Net Profit |\n"
    md += "|---|---|---|---|---|\n"
    for r in results:
        w_l = f"{r.get('Wins', 0)}/{r.get('Losses', 0)}"
        md += f"| {r['Asset']} | {r['Trades']} | {w_l} | {r['WinRate']:.2%} | ${r['NetProfit']:.2f} |\n"
    
    print(md)

if __name__ == "__main__":
    main()
