"""Diagnose the MHI interpolation color bias."""
import csv
from backtest_mhi_grid import interpolate_m5_to_m1

rows = []
with open("data/BTCUSDT_M5_1y.csv", "r", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        rows.append({"time": float(r["time"]), "open": float(r["open"]),
                      "high": float(r["high"]), "low": float(r["low"]),
                      "close": float(r["close"])})

m1 = interpolate_m5_to_m1(rows[:10])

print("=== M1 candle colors from first 3 M5 candles ===")
for i, c in enumerate(m1[:15]):
    color = "GREEN" if c["close"] > c["open"] else ("RED" if c["close"] < c["open"] else "DOJI")
    ts = int(c["time"])
    mod = (ts // 60) % 5
    block = i // 5
    print(f"  block={block} sub={i%5} mod5={mod} o={c['open']:.6f} c={c['close']:.6f} -> {color}")

# Count overall color distribution in first 10000 M1 candles
m1_big = interpolate_m5_to_m1(rows[:2000])
greens = sum(1 for c in m1_big if c["close"] > c["open"])
reds = sum(1 for c in m1_big if c["close"] < c["open"])
dojis = sum(1 for c in m1_big if c["close"] == c["open"])
total = len(m1_big)
print(f"\nColor distribution (first 10000 M1):")
print(f"  GREEN={greens} ({greens/total:.1%}), RED={reds} ({reds/total:.1%}), DOJI={dojis} ({dojis/total:.1%})")

# Check if the interpolation creates monotonic sub-candles
# (all same direction within a block => MHI always gets same majority)
blocks_same = 0
blocks_mixed = 0
for i in range(0, len(m1_big) - 4, 5):
    block = m1_big[i:i+5]
    colors = []
    for c in block:
        if c["close"] > c["open"]: colors.append("g")
        elif c["close"] < c["open"]: colors.append("r")
        else: colors.append("d")
    if len(set(colors)) == 1:
        blocks_same += 1
    else:
        blocks_mixed += 1
    
print(f"\nBlock color analysis (2000 blocks):")
print(f"  All same color: {blocks_same} ({blocks_same/(blocks_same+blocks_mixed):.1%})")
print(f"  Mixed colors:   {blocks_mixed} ({blocks_mixed/(blocks_same+blocks_mixed):.1%})")

# Check the MHI signal: if sub-candles within a block all have the same
# direction (monotonic interpolation), then the 3-candle minority will
# always predict AGAINST the trend, which is systematically wrong
print("\n=== Critical Issue ===")
print("If interpolation creates monotonic sub-candles (all same color),")
print("MHI minority always bets AGAINST the direction, losing systematically.")
