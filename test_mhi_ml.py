"""
Simula o impacto do Filtro ML sobre os sinais do MHI.
Roda a estratégia nos dados reais M1 para extrair os sinais,
e passa cada sinal pelo ml_filter.py (modelo XGBoost).
"""
import sys
import pandas as pd
from ml_filter import MLFilter

def main():
    print("Carregando ML Filter...")
    ml = MLFilter(threshold=0.62)
    if not ml.is_loaded:
        print("Falha ao carregar modelo ML!")
        return

    csv_path = "data/BTCUSDT_M1_60d.csv"
    print(f"Carregando {csv_path}...")
    df = pd.read_csv(csv_path)

    # Configuração Top 1 (EMA 100, Require Trend)
    ema_period = 100
    df["ema"] = df["close"].ewm(span=ema_period, adjust=False).mean()
    
    closes = df["close"].values
    opens = df["open"].values
    times = df["time"].values
    emas = df["ema"].values

    signals = []
    # Começa no N mínimo para o ML filter (61)
    for i in range(65, len(df) - 1):
        minute_mod = (int(times[i]) // 60) % 5
        if minute_mod != 4:
            continue
            
        colors = []
        valid = True
        for k in range(i - 2, i + 1):
            if closes[k] > opens[k]: colors.append("green")
            elif closes[k] < opens[k]: colors.append("red")
            else:
                valid = False
                break
        if not valid: continue
        
        greens = colors.count("green")
        reds = colors.count("red")
        
        if greens > reds: sig = "put"
        elif reds > greens: sig = "call"
        else: continue
            
        # Filtro de Tendência MHI
        if sig == "call" and closes[i] <= emas[i]: continue
        if sig == "put" and closes[i] >= emas[i]: continue

        # Resolucao MHI
        nxt = closes[i+1]
        if nxt == closes[i]: continue
        won = (sig == "call" and nxt > closes[i]) or (sig == "put" and nxt < closes[i])
        
        signals.append({
            "idx": i,
            "sig": sig,
            "won": won,
            "ts": times[i]
        })

    print(f"MHI 1 Pura: {len(signals)} sinais válidos.")
    w_mhi = sum(1 for s in signals if s["won"])
    l_mhi = len(signals) - w_mhi
    print(f"Winrate MHI Pura: {w_mhi/len(signals):.2%} (W: {w_mhi}, L: {l_mhi})")
    print(f"Lucro Bruto Pura (Payout 87%, $10 fixo): ${(w_mhi * 8.7) - (l_mhi * 10):.2f}")

    print("\nAplicando Filtro ML (Threshold 0.62)...")
    ml_passed = []
    
    # Avaliar o ML para cada sinal
    done = 0
    for s in signals:
        # Prepara o df até o momento do sinal
        hist = df.iloc[s["idx"] - 70 : s["idx"] + 1].copy()
        try:
            allow, prob = ml.filter_signal(hist, s["sig"])
            if allow:
                s["prob"] = prob
                ml_passed.append(s)
        except Exception as e:
            pass # IGNORA ERROS (ex. inf/nan)
        done += 1
        if done % 1000 == 0:
            print(f" Processado {done}/{len(signals)} sinais...")

    print(f"\nSinais Aprovados pelo ML: {len(ml_passed)} / {len(signals)} (Bloqueou {1 - len(ml_passed)/len(signals):.2%})")
    if not ml_passed: return
    
    w_ml = sum(1 for s in ml_passed if s["won"])
    l_ml = len(ml_passed) - w_ml
    wr_ml = w_ml / len(ml_passed)
    print(f"Winrate com Filtro ML: {wr_ml:.2%} (W: {w_ml}, L: {l_ml})")
    print(f"Lucro Bruto c/ ML (Payout 87%, $10 fixo): ${(w_ml * 8.7) - (l_ml * 10):.2f}")

if __name__ == "__main__":
    main()
