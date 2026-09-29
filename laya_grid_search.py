import os
import sys
import pandas as pd
import subprocess
import logging
import csv
import yfinance as yf
from strategies import get_signal
from ml_filter import LayaFilter
from kelly import kelly_fraction_stake

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger("iqrobot.ml_filter").setLevel(logging.ERROR)

ASSETS = ["EURUSD", "GBPUSD", "BTCUSD", "ETHUSD", "XAUUSD", "XAGUSD", "SP500"]
STRATEGIES = ["bollinger_touch", "rsi_m15"]
INTERVAL = 300 # M5
CANDLE_COUNT = 10000 # About 1 month of M5 (24 * 12 * 30 = 8640)
PAYOUT = 0.85

def ensure_data(asset):
    os.makedirs("data", exist_ok=True)
    filename = f"data/{asset}_M5_iq.csv"
    if not os.path.exists(filename):
        logger.info(f"Downloading M5 data for {asset}...")
        try:
            subprocess.run([
                sys.executable, "fetch_iq.py", 
                "--asset", asset, 
                "--interval", str(INTERVAL), 
                "--n", str(CANDLE_COUNT), 
                "--out", filename
            ], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to fetch data for {asset}: {e}")
            logger.info(f"Attempting fallback yfinance fetch for {asset}...")
            mapping = {
                "EURUSD": "EURUSD=X",
                "GBPUSD": "GBPUSD=X",
                "BTCUSD": "BTC-USD",
                "ETHUSD": "ETH-USD",
                "XAUUSD": "GC=F",
                "XAGUSD": "SI=F",
                "SP500": "^GSPC"
            }
            yf_symbol = mapping.get(asset)
            if not yf_symbol:
                logger.error(f"No yfinance mapping for {asset}")
                return filename
            
            try:
                df = yf.download(yf_symbol, period="60d", interval="5m", progress=False, auto_adjust=False)
                if df.empty:
                    logger.error(f"yfinance returned empty for {yf_symbol}")
                    return filename
                    
                df = df.dropna()
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df = df.reset_index()
                
                with open(filename, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(["time", "open", "high", "low", "close"])
                    for _, r in df.iterrows():
                        col_time = "Datetime" if "Datetime" in r else "Date"
                        ts = int(r[col_time].timestamp() * 1000)
                        w.writerow([ts, r["Open"], r["High"], r["Low"], r["Close"]])
                logger.info(f"Fallback fetch successful for {asset}")
            except Exception as e2:
                logger.error(f"Fallback fetch failed for {asset}: {e2}")
    return filename

class MockCfg:
    DONCHIAN_N = 20
    RSI_PERIOD = 14
    RSI_OVERBOUGHT = 70
    RSI_OVERSOLD = 30
    RSI_REQUIRE_EXIT = False
    BB_PERIOD = 20
    BB_MULT = 2.0
    HTF_EMA = 50
    HTF_TIMEFRAME = 3600
    TREND_EMA = 200

def run_grid_search():
    cfg = MockCfg()
    logger.info("Initializing LayaFilter...")
    # Initialize Laya filter as implicitly required
    laya = LayaFilter(threshold=0.5, fail_open=False)

    results = []

    for asset in ASSETS:
        csv_file = ensure_data(asset)
        if not os.path.exists(csv_file):
            logger.warning(f"Skipping {asset} due to missing data.")
            continue
        
        try:
            df_all = pd.read_csv(csv_file)
        except Exception as e:
            logger.error(f"Error reading {csv_file}: {e}")
            continue

        if len(df_all) < 200:
            logger.warning(f"Not enough data for {asset} ({len(df_all)} rows). Skipping.")
            continue
            
        for strategy in STRATEGIES:
            logger.info(f"Backtesting {asset} - {strategy}...")
            
            wins = 0
            losses = 0
            ties = 0
            total_profit = 0.0
            
            # Start from candle index 150 to allow window calculations
            # We use a window of 150 candles for the base strategy and the Laya filter
            for i in range(150, len(df_all) - 1):
                window = df_all.iloc[i-150:i+1].copy()
                
                signal = get_signal(strategy, window, cfg)
                
                if signal in ("call", "put"):
                    # Validate with LayaFilter
                    allow, prob = laya.filter_signal(window, signal)
                    
                    if allow:
                        # Proceed with simulated trade on the next candle
                        next_candle = df_all.iloc[i+1]
                        op = next_candle['open']
                        cl = next_candle['close']
                        
                        if signal == "call":
                            if cl > op:
                                wins += 1
                                total_profit += PAYOUT
                            elif cl < op:
                                losses += 1
                                total_profit -= 1.0
                            else:
                                ties += 1
                        else: # put
                            if cl < op:
                                wins += 1
                                total_profit += PAYOUT
                            elif cl > op:
                                losses += 1
                                total_profit -= 1.0
                            else:
                                ties += 1
                                
            total_trades = wins + losses
            winrate = wins / total_trades if total_trades > 0 else 0.0
            
            # Calculate Kelly Criterion using existing kelly_fraction_stake
            _, kelly_val = kelly_fraction_stake(100.0, PAYOUT, winrate)
            
            logger.info(f"Result -> {asset} | {strategy} | Trades: {total_trades} | WR: {winrate:.2f} | Profit: {total_profit:.2f} | Kelly: {kelly_val:.2f}")
            
            results.append({
                "Asset": asset,
                "Strategy": strategy,
                "Trades": total_trades,
                "Winrate": round(winrate, 4),
                "Total Profit": round(total_profit, 2),
                "Kelly": round(kelly_val, 4)
            })

    # Save to data/laya_grid_results.csv
    os.makedirs("data", exist_ok=True)
    df_res = pd.DataFrame(results)
    if not df_res.empty:
        df_res.to_csv("data/laya_grid_results.csv", index=False)
        logger.info("Grid search completed successfully. Results saved to data/laya_grid_results.csv")
    else:
        logger.info("No results to save.")

if __name__ == "__main__":
    run_grid_search()
