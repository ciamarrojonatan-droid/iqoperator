"""Fetch BTCUSDT 1m candles from Binance (free, no auth needed).
Resilient: retries on timeout, saves partial results on failure."""
import csv
import os
import sys
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
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt < retries - 1:
                wait = (attempt + 1) * 5
                print(f"    retry {attempt+1}/{retries} in {wait}s...", flush=True)
                time.sleep(wait)
            else:
                raise

def save_csv(klines, out):
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time", "open", "high", "low", "close"])
        for k in klines:
            ts = int(k[0]) // 1000
            w.writerow([ts, k[1], k[2], k[3], k[4]])

def fetch_all(symbol="BTCUSDT", days=62, out="data/BTCUSDT_M1_90d.csv"):
    target = days * 24 * 60
    all_klines = []
    end_ms = None
    batch = 0

    try:
        while len(all_klines) < target:
            batch += 1
            kl = get_klines(symbol=symbol, interval="1m", limit=1000, end_time=end_ms)
            if not kl:
                break
            all_klines = kl + all_klines
            end_ms = kl[0][0] - 1
            if batch % 10 == 0:
                print(f"  batch {batch}: total={len(all_klines)}/{target}", flush=True)
            time.sleep(0.4)
    except Exception as e:
        print(f"\n[WARN] Stopped at {len(all_klines)} candles: {e}")
    finally:
        if all_klines:
            save_csv(all_klines, out)
            print(f"\n[OK] {len(all_klines)} candles M1 -> {out}")
        else:
            print("[ERRO] Nenhum candle baixado.")
    return len(all_klines)

if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 62
    out = sys.argv[2] if len(sys.argv) > 2 else "data/BTCUSDT_M1_90d.csv"
    fetch_all(days=days, out=out)
