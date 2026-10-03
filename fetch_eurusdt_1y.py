import requests
import pandas as pd
import time
from datetime import datetime, timezone

SYMBOL = "EURUSDT"
INTERVAL = "1m"
DAYS = 365
LIMIT = 1000

end_time = int(time.time() * 1000)
start_time = end_time - (DAYS * 24 * 60 * 60 * 1000)

all_klines = []
current_start = start_time

print(f"Fetching {DAYS} days of {SYMBOL} M1 data from Binance...")

while current_start < end_time:
    url = f"https://api.binance.com/api/v3/klines?symbol={SYMBOL}&interval={INTERVAL}&limit={LIMIT}&startTime={current_start}&endTime={end_time}"
    try:
        res = requests.get(url)
        data = res.json()
    except Exception as e:
        print("Error fetching:", e)
        time.sleep(2)
        continue

    if not data or type(data) is dict:
        print("Empty or error:", data)
        break

    all_klines.extend(data)
    current_start = data[-1][0] + 1
    
    print(f"Fetched up to {pd.to_datetime(data[-1][0], unit='ms')} - Total: {len(all_klines)}")
    time.sleep(0.5)

df = pd.DataFrame(all_klines, columns=[
    "time", "open", "high", "low", "close", "volume", 
    "close_time", "quote_asset_volume", "number_of_trades",
    "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
])

for col in ["open", "high", "low", "close", "volume"]:
    df[col] = pd.to_numeric(df[col])

df["datetime"] = pd.to_datetime(df["time"], unit="ms", utc=True)
df["date"] = df["datetime"].dt.strftime("%Y-%m-%d")

# Drop unnecessary columns
df = df[["time", "datetime", "date", "open", "high", "low", "close", "volume"]]

df.to_csv(f"data/{SYMBOL}_M1_1y.csv", index=False)
print(f"Saved {len(df)} rows to data/{SYMBOL}_M1_1y.csv")
