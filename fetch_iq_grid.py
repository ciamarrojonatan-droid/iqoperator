import argparse
import csv
import os
import time
from dotenv import load_dotenv

def main():
    load_dotenv()
    email = os.getenv("IQ_EMAIL")
    pwd = os.getenv("IQ_PASSWORD")
    if not email or not pwd:
        print("[ERRO] IQ_EMAIL/PASSWORD não definidos no .env")
        return

    from iqoptionapi.stable_api import IQ_Option
    api = IQ_Option(email, pwd)
    ok, reason = api.connect()
    if not ok:
        print(f"[ERRO] connect falhou: {reason}")
        return
    api.change_balance("PRACTICE")

    assets = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "EURGBP"]
    n_candles = 20000
    interval = 300

    os.makedirs("data", exist_ok=True)

    for asset in assets:
        out_path = f"data/{asset}_M5_iq.csv"
        print(f"Baixando {asset}...")
        try:
            all_candles = []
            end_time = time.time()
            while len(all_candles) < n_candles:
                fetch_count = min(1000, n_candles - len(all_candles))
                candles = api.get_candles(asset, interval, fetch_count, end_time)
                if not candles:
                    break
                all_candles = candles + all_candles
                end_time = candles[0]["from"] - 1
                time.sleep(0.5)
            
            if not all_candles:
                print(f"[ERRO] Sem candles para {asset}")
                continue
            
            with open(out_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["time", "open", "high", "low", "close"])
                for c in all_candles:
                    w.writerow([c.get("from", ""), c.get("open", ""), c.get("max", ""), c.get("min", ""), c.get("close", "")])
            print(f"[OK] {len(all_candles)} candles de {asset} salvos em {out_path}")
        except Exception as e:
            print(f"[ERRO] Falha em {asset}: {e}")

if __name__ == "__main__":
    main()
