"""Estratégias para BTCUSD Binárias (M15 + RSI)."""
import pandas as pd


def rsi_series(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    return 100 - (100 / (1 + gain / loss.replace(0, 1e-9)))


def rsi_m15_signal(df: pd.DataFrame, period: int = 14,
                   overbought: float = 70, oversold: float = 30,
                   require_exit: bool = True) -> str | None:
    """RSI M15 reversão à média.
    - require_exit=True: CALL quando RSI sai de baixo p/ cima do oversold;
      PUT quando sai de cima p/ baixo do overbought (1 sinal por saída).
    - require_exit=False: CALL todo candle com RSI<oversold, PUT com RSI>overbought.
    Usa candle fechado (penúltimo se o último ainda está formando).
    """
    if len(df) < period + 3:
        return None

    rsi = rsi_series(df["close"], period)
    prev_rsi = float(rsi.iloc[-2])
    last_rsi = float(rsi.iloc[-1])

    if require_exit:
        if prev_rsi <= oversold < last_rsi:
            return "call"
        if prev_rsi >= overbought > last_rsi:
            return "put"
        return None
    if last_rsi < oversold:
        return "call"
    if last_rsi > overbought:
        return "put"
    return None

def rsi_momentum_signal(df: pd.DataFrame, period: int = 14,
                        overbought: float = 70, oversold: float = 30,
                        require_exit: bool = True) -> str | None:
    """RSI M15 continuação de tendência.
    - require_exit=True: CALL quando RSI rompe OB p/ cima; PUT quando rompe OS p/ baixo.
    - require_exit=False: CALL todo candle com RSI>OB, PUT com RSI<OS.
    """
    if len(df) < period + 3:
        return None

    rsi = rsi_series(df["close"], period)
    prev_rsi = float(rsi.iloc[-2])
    last_rsi = float(rsi.iloc[-1])

    if require_exit:
        if prev_rsi <= overbought < last_rsi:
            return "call"
        if prev_rsi >= oversold > last_rsi:
            return "put"
        return None
    if last_rsi > overbought:
        return "call"
    if last_rsi < oversold:
        return "put"
    return None

def rsi_momentum_trend_signal(df: pd.DataFrame, period: int = 14,
                              overbought: float = 70, oversold: float = 30,
                              require_exit: bool = True,
                              trend_span: int = 200) -> str | None:
    """Momentum só a favor da tendência: CALL exige close > EMA(trend_span),
    PUT exige close < EMA(trend_span)."""
    if len(df) < period + 3:
        return None

    sig = rsi_momentum_signal(df, period, overbought, oversold, require_exit)
    if not sig:
        return None
    trend = df["close"].ewm(span=trend_span, adjust=False).mean()
    last_close = float(df["close"].iloc[-1])
    last_ema = float(trend.iloc[-1])
    if sig == "call" and last_close <= last_ema:
        return None
    if sig == "put" and last_close >= last_ema:
        return None
    return sig


def rsi_mtf_pullback_signal(df_m15: pd.DataFrame, df_h1: pd.DataFrame,
                              period: int = 14,
                              overbought: float = 70, oversold: float = 30,
                              require_exit: bool = False,
                              htf_ema: int = 50,
                              htf_seconds: int = 3600) -> str | None:
    """Setup do backtest 1y: viés H1 + gatilho pullback RSI no M15.
    Regra idêntica à validada: usa a última barra H1 100% fechada antes da
    abertura do candle M15 de entrada (close_H1 <= from_M15). Sem lookahead."""
    if df_m15 is None or df_h1 is None or len(df_m15) < period + 3 or len(df_h1) < 3:
        return None

    h1_close = df_h1["close"]
    h1_ema = h1_close.ewm(span=htf_ema, adjust=False).mean()
    try:
        entry_from = float(df_m15["from"].iloc[-1])
        h1_from = df_h1["from"].astype(float)
        eligible = df_h1[(h1_from + htf_seconds <= entry_from).to_numpy()]
        if eligible.empty:
            return None
        ref = eligible.index[-1]
        bias_long = float(h1_close.loc[ref]) > float(h1_ema.loc[ref])
        bias_short = float(h1_close.loc[ref]) < float(h1_ema.loc[ref])
    except (KeyError, ValueError, IndexError):
        # fallback conservador sem timestamp: pula as 2 últimas barras H1
        if len(df_h1) < 4:
            return None
        bias_long = float(h1_close.iloc[-3]) > float(h1_ema.iloc[-3])
        bias_short = float(h1_close.iloc[-3]) < float(h1_ema.iloc[-3])

    rsi = rsi_series(df_m15["close"], period)
    prev_rsi = float(rsi.iloc[-2])
    last_rsi = float(rsi.iloc[-1])

    if require_exit:
        if bias_long and prev_rsi <= oversold < last_rsi:
            return "call"
        if bias_short and prev_rsi >= overbought > last_rsi:
            return "put"
        return None
    if bias_long and last_rsi < oversold:
        return "call"
    if bias_short and last_rsi > overbought:
        return "put"
    return None


def donchian_fade_signal(df: pd.DataFrame, n: int = 20) -> str | None:
    """Fade de rompimento Donchian: close acima da máxima dos últimos n
    candles (excluindo o atual) -> PUT; abaixo da mínima -> CALL.
    Regra idêntica à validada (IS+OOS+ano fresco). df.iloc[-1] = candle fechado."""
    if len(df) < n + 2:
        return None
    high = df.get("high", df.get("max"))
    low = df.get("low", df.get("min"))
    if high is None or low is None:
        return None
    hi = float(high.iloc[-n - 1:-1].max())
    lo = float(low.iloc[-n - 1:-1].min())
    close = float(df["close"].iloc[-1])
    if close > hi:
        return "put"
    if close < lo:
        return "call"
    return None


def bollinger_touch_signal(df: pd.DataFrame, period: int = 20,
                           mult: float = 2.0) -> str | None:
    """Toque na banda de Bollinger -> reversão.
    Close abaixo da banda inferior -> CALL; acima da superior -> PUT."""
    if len(df) < period + 2:
        return None
    close_s = df["close"]
    sma = close_s.rolling(period).mean()
    std = close_s.rolling(period).std()
    upper = sma + mult * std
    lower = sma - mult * std
    last_close = float(close_s.iloc[-1])
    last_upper = float(upper.iloc[-1])
    last_lower = float(lower.iloc[-1])
    if pd.isna(last_upper) or pd.isna(last_lower):
        return None
    if last_close > last_upper:
        return "put"
    if last_close < last_lower:
        return "call"
    return None


def multi_mean_reversion_signal(df: pd.DataFrame, donchian_n: int = 20,
                                 bb_period: int = 20, bb_mult: float = 2.0,
                                 rsi_period: int = 14, rsi_ob: float = 70,
                                 rsi_os: float = 30) -> str | None:
    """Combo de 3 indicadores de reversão à média (união).
    Dispara se QUALQUER um dos 3 detectar extremo no mesmo candle:
      1) Donchian Fade (DC20): close fora do canal N
      2) Bollinger Band (BB20, 2σ): close fora da banda
      3) RSI zone (14, 30/70): RSI em zona extrema

    Se mais de um indicador dispara no mesmo candle com direções
    conflitantes (raro), descarta (sem sinal).

    Frequência estimada: ~11-16 sinais/dia/ativo (vs ~7.8 do DC20 sozinho).
    """
    signals = set()

    s1 = donchian_fade_signal(df, n=donchian_n)
    if s1:
        signals.add(s1)

    s2 = bollinger_touch_signal(df, period=bb_period, mult=bb_mult)
    if s2:
        signals.add(s2)

    s3 = rsi_m15_signal(df, period=rsi_period, overbought=rsi_ob,
                        oversold=rsi_os, require_exit=False)
    if s3:
        signals.add(s3)

    if len(signals) == 1:
        return signals.pop()
    # 0 sinais ou conflito (call+put) -> None
    return None


def ema_cross_signal(df: pd.DataFrame, fast: int = 9, slow: int = 21,
                      rsi_period: int = 14, overbought: float = 70,
                      oversold: float = 30) -> str | None:
    """Retorna 'call', 'put' ou None.
    Regra: cruzamento EMA fast/slow + filtro RSI (evita sobrecomprado/sobrevendido contra a entrada).
    df precisa ter coluna 'close'.
    """
    if len(df) < slow + 3:
        return None

    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()

    # RSI simples sem depender de lib externa
    delta = df["close"].diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / rsi_period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / rsi_period, adjust=False).mean()
    rsi = 100 - (100 / (1 + gain / loss.replace(0, 1e-9)))
    last_rsi = float(rsi.iloc[-1])

    prev_diff = float(ema_fast.iloc[-2] - ema_slow.iloc[-2])
    last_diff = float(ema_fast.iloc[-1] - ema_slow.iloc[-1])

    # Cruzou pra cima -> call (se não sobrecomprado)
    if prev_diff <= 0 < last_diff and last_rsi < overbought:
        return "call"
    # Cruzou pra baixo -> put (se não sobrevendido)
    if prev_diff >= 0 > last_diff and last_rsi > oversold:
        return "put"
    return None


def mhi_1_signal(
    df: pd.DataFrame,
    trend_ema: int = 100,
    require_trend: bool = True,
) -> str | None:
    """
    Estratégia Probabilística MHI 1 (Minoria em M1):
    - Analisa as cores das velas 3, 4 e 5 de cada quadrante de 5 minutos (fechamento em :04, :09, :14...).
    - Entra a favor da cor minoritária na Vela 1 do próximo quadrante (:00, :05, :10...).
    - Filtro Anti-Doji: se qualquer uma das 3 velas for Doji (open == close), aborta (None).
    - Filtro de Micro-Tendência: se require_trend=True, CALL exige close > EMA(trend_ema), PUT exige close < EMA(trend_ema).
    """
    if df is None or len(df) < 5:
        return None

    # Identificar timestamp do candle fechado
    last_candle = df.iloc[-1]
    ts = None
    for col in ("from", "at", "open_time", "time", "date", "timestamp"):
        if col in df.columns:
            try:
                v = int(float(last_candle[col]))
                if v > 0:
                    ts = v
                    break
            except (ValueError, TypeError):
                continue

    # Se timestamp disponível, valida se o candle fechado é o 5º do quadrante de 5m (:04, :09, ...)
    if ts is not None:
        minute_mod = (ts // 60) % 5
        if minute_mod != 4:
            return None

    # Analisar cores das últimas 3 velas do quadrante (Velas 3, 4 e 5)
    sample = df.iloc[-3:]
    colors = []
    for _, row in sample.iterrows():
        o = float(row.get("open", 0))
        c = float(row.get("close", 0))
        if c > o:
            colors.append("green")
        elif c < o:
            colors.append("red")
        else:
            return None  # Anti-Doji: indecisão detectada

    greens = colors.count("green")
    reds = colors.count("red")

    if greens > reds:
        signal = "put"
    elif reds > greens:
        signal = "call"
    else:
        return None

    # Filtro de micro-tendência EMA
    if require_trend and len(df) >= trend_ema:
        ema = df["close"].ewm(span=trend_ema, adjust=False).mean()
        last_close = float(df["close"].iloc[-1])
        last_ema = float(ema.iloc[-1])
        if signal == "call" and last_close <= last_ema:
            return None
        if signal == "put" and last_close >= last_ema:
            return None

    return signal


def get_signal(strategy: str, df: pd.DataFrame, cfg, df_htf: pd.DataFrame | None = None) -> str | None:
    if strategy == "donchian_fade":
        return donchian_fade_signal(df, n=cfg.DONCHIAN_N)
    if strategy == "rsi_mtf_pullback":
        return rsi_mtf_pullback_signal(
            df, df_htf, period=cfg.RSI_PERIOD,
            overbought=cfg.RSI_OVERBOUGHT,
            oversold=cfg.RSI_OVERSOLD,
            require_exit=cfg.RSI_REQUIRE_EXIT,
            htf_ema=cfg.HTF_EMA,
            htf_seconds=cfg.HTF_TIMEFRAME,
        )
    if strategy == "rsi_m15":
        return rsi_m15_signal(
            df, period=cfg.RSI_PERIOD,
            overbought=cfg.RSI_OVERBOUGHT,
            oversold=cfg.RSI_OVERSOLD,
            require_exit=cfg.RSI_REQUIRE_EXIT,
        )
    if strategy == "rsi_momentum_trend":
        return rsi_momentum_trend_signal(
            df, period=cfg.RSI_PERIOD,
            overbought=cfg.RSI_OVERBOUGHT,
            oversold=cfg.RSI_OVERSOLD,
            require_exit=cfg.RSI_REQUIRE_EXIT,
            trend_span=cfg.TREND_EMA,
        )
    if strategy == "rsi_momentum":
        return rsi_momentum_signal(
            df, period=cfg.RSI_PERIOD,
            overbought=cfg.RSI_OVERBOUGHT,
            oversold=cfg.RSI_OVERSOLD,
            require_exit=cfg.RSI_REQUIRE_EXIT,
        )
    if strategy == "ema_cross":
        return ema_cross_signal(
            df, fast=cfg.EMA_FAST, slow=cfg.EMA_SLOW,
            rsi_period=cfg.RSI_PERIOD,
            overbought=cfg.RSI_OVERBOUGHT,
            oversold=cfg.RSI_OVERSOLD,
        )
    if strategy == "bollinger_touch":
        return bollinger_touch_signal(
            df, period=getattr(cfg, "BB_PERIOD", 20),
            mult=getattr(cfg, "BB_MULT", 2.0),
        )
    if strategy == "multi_mean_reversion":
        return multi_mean_reversion_signal(
            df, donchian_n=cfg.DONCHIAN_N,
            bb_period=getattr(cfg, "BB_PERIOD", 20),
            bb_mult=getattr(cfg, "BB_MULT", 2.0),
            rsi_period=cfg.RSI_PERIOD,
            rsi_ob=cfg.RSI_OVERBOUGHT,
            rsi_os=cfg.RSI_OVERSOLD,
        )
    if strategy == "mhi_1":
        return mhi_1_signal(
            df,
            trend_ema=getattr(cfg, "MHI_TREND_EMA", 100),
            require_trend=getattr(cfg, "MHI_REQUIRE_TREND", True),
        )
    return None
