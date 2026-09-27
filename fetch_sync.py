import csv
import os
import time
import requests

BASE = "https://api.binance.com"

def get_klines(symbol="BTCUSDT", interval="1m", limit=1000, end_time=None, retries=3):
    url = f"{BASE}/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    if end_time:
        url += f"&endTime={end_time}"
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt < retries - 1:
                time.sleep((attempt + 1) * 2)
            else:
                raise

def save_csv(klines, out):
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time", "open", "high", "low", "close", "volume"])
        for k in klines:
            ts = int(k[0]) // 1000
            w.writerow([ts, k[1], k[2], k[3], k[4], k[5]])

def fetch_all(symbol="BTCUSDT", days=60, interval="1m", out="data/BTCUSDT_M1_60d.csv"):
    if interval == "1m":
        target = days * 24 * 60
    elif interval == "5m":
        target = days * 24 * 12
    elif interval == "15m":
        target = days * 24 * 4
    
    all_klines = []
    end_ms = None
    
    print(f"Fetching {target} candles for {interval}...")
    try:
        while len(all_klines) < target:
            kl = get_klines(symbol=symbol, interval=interval, limit=1000, end_time=end_ms)
            if not kl:
                break
            all_klines = kl + all_klines
            end_ms = kl[0][0] - 1
            time.sleep(0.2)
    except Exception as e:
        print(f"[WARN] Stopped: {e}")
    
    all_klines = all_klines[-target:]
    if all_klines:
        save_csv(all_klines, out)
        print(f"[OK] Saved {len(all_klines)} candles to {out}")

if __name__ == "__main__":
    fetch_all(interval="1m", out="data/BTCUSDT_M1_60d.csv")
    fetch_all(interval="5m", out="data/BTCUSDT_M5_60d.csv")
    fetch_all(interval="15m", out="data/BTCUSDT_M15_60d.csv")
