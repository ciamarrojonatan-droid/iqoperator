"""Baixa candles M5 reais de BTCUSDT via API pública Binance (sem chave)."""
import argparse
import csv
import json
import os
import urllib.request
import time
import datetime

BASE = "https://data-api.binance.vision"

def get_klines(symbol="BTCUSDT", interval="5m", limit=1000, end_time=None):
    url = f"{BASE}/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    if end_time:
        url += f"&endTime={end_time}"
    req = urllib.request.Request(url, headers={"User-Agent": "iqrobot/1.0"})
    
    # Retry loop
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            time.sleep(2)
            print(f"Retry on error: {e}")
    return []

def main():
    symbol = "BTCUSDT"
    interval = "5m"
    out = "data/BTCUSDT_M5_3y.csv"
    
    # 3 years of M5 candles: 3 * 365 * 24 * 12 = 315,360
    n = 315360
    
    pages = []
    end_time = None
    
    print(f"Fetching {n} M5 candles for {symbol}...")
    
    while sum(len(p) for p in pages) < n:
        limit = min(1000, n - sum(len(p) for p in pages))
        kl = get_klines(symbol=symbol, interval=interval, limit=limit, end_time=end_time)
        if not kl:
            break
        pages.append(kl)
        end_time = kl[0][0] - 1
        print(f"Fetched {sum(len(p) for p in pages)}/{n} candles. Last timestamp: {datetime.datetime.fromtimestamp(kl[0][0]/1000)}")
        if len(kl) < 1000:
            break

    klines = [k for p in reversed(pages) for k in p][-n:]
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time", "open", "high", "low", "close"])
        for k in klines:
            w.writerow([k[0], k[1], k[2], k[3], k[4]])
            
    if klines:
        t0 = datetime.datetime.fromtimestamp(klines[0][0] / 1000).strftime("%Y-%m-%d")
        t1 = datetime.datetime.fromtimestamp(klines[-1][0] / 1000).strftime("%Y-%m-%d")
        print(f"[OK] {len(klines)} candles {interval} {t0} -> {t1} em {out}")
    else:
        print("No candles fetched.")

if __name__ == "__main__":
    main()
