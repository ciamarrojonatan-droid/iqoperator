"""Config central do robô - lê do .env"""
import os
from dotenv import load_dotenv

load_dotenv()

def _get_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default

def _get_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default

EMAIL = os.getenv("IQ_EMAIL", "")
PASSWORD = os.getenv("IQ_PASSWORD", "")
BALANCE_TYPE = os.getenv("IQ_BALANCE_TYPE", "PRACTICE").upper()  # PRACTICE | REAL

ASSET = os.getenv("IQ_ASSET", "BTCUSD")
# Multi-ativo: IQ_ASSETS="EURUSD-OTC,GBPUSD-OTC,..." (fallback: [IQ_ASSET])
def _get_list(key: str, fallback: list) -> list:
    raw = os.getenv(key, "")
    if raw.strip():
        return [a.strip().upper() for a in raw.split(",") if a.strip()]
    return fallback

DEFAULT_ASSETS = ["EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC", "AUDUSD-OTC", "EURGBP-OTC", "USDCAD-OTC"]
ASSETS = _get_list("IQ_ASSETS", _get_list("IQ_ASSET", DEFAULT_ASSETS))
# Sanidade: nomes de ativo válidos (ex.: "EURUSD-OTC"); ignora entradas quebradas
# (ex. lista colada na variável singular) em vez de travar o loop em reconnect.
import re as _re
_ASSET_RE = _re.compile(r"^[A-Z0-9\-]+$")
_BAD = [a for a in ASSETS if not _ASSET_RE.match(a)]
if _BAD:
    import logging as _logging
    _logging.getLogger("iqrobot").warning(f"Ignorando ativos inválidos: {_BAD}")
    ASSETS = [a for a in ASSETS if _ASSET_RE.match(a)]
if not ASSETS:
    ASSETS = list(DEFAULT_ASSETS)
# Trava global de exposição: no máximo N posições pendentes simultâneas
MAX_CONCURRENT = _get_int("IQ_MAX_CONCURRENT", 3)
# Pendências em disco (sobrevivem a restart) e watchdog anti-deadlock
PENDING_FILE = os.getenv("PENDING_FILE", "data/pending.json")
WATCHDOG_TIMEOUT = _get_int("WATCHDOG_TIMEOUT", 120)
# Outage global: após N ciclos consecutivos sem dados de nenhum ativo, restart forçado
MAX_GLOBAL_ERRORS = _get_int("MAX_GLOBAL_ERRORS", 10)
# Ritmo do scan multi-ativo (estratégia M15: scan agressivo só gera rate-limit)
SCAN_SLEEP = _get_int("IQ_SCAN_SLEEP", 45)
ASSET_DELAY = _get_float("IQ_ASSET_DELAY", 2.0)
# Backoff: após N falhas seguidas de candles, pula o ativo por M segundos
CANDLE_FAIL_LIMIT = _get_int("CANDLE_FAIL_LIMIT", 3)
CANDLE_COOLDOWN = _get_int("CANDLE_COOLDOWN", 300)
# Ritmo sustentável: N ativos por ciclo + disjuntor global após scans vazios
ASSETS_PER_CYCLE = _get_int("IQ_ASSETS_PER_CYCLE", 2)
GLOBAL_COOLDOWN = _get_int("IQ_GLOBAL_COOLDOWN", 300)
BALANCE_TTL = _get_int("IQ_BALANCE_TTL", 30)
TIMEFRAME = _get_int("IQ_TIMEFRAME", 900)  # segundos: 900 = M15
EXPIRATION = _get_int("IQ_EXPIRATION", 15)  # minutos p/ binária (igual ao M15)
AMOUNT = _get_float("IQ_AMOUNT", 2.0)
PAYOUT_MIN = _get_float("IQ_PAYOUT_MIN", 0.70)
CANDLE_COUNT = _get_int("IQ_CANDLE_COUNT", 120)

# Kelly fracionário (substitui valor fixo quando USE_KELLY=1)
# Breakeven p/ payout 0.80 = 1/1.8 = 0.5556. Prior 0.58 = edge pequeno e conservador.
USE_KELLY = os.getenv("USE_KELLY", "1") == "1"
KELLY_PRIOR = _get_float("KELLY_PRIOR", 0.58)  # winrate inicial estimado
KELLY_FRACTION = _get_float("KELLY_FRACTION", 0.25)  # 0.25 = quarter-kelly (conservador)
KELLY_MAX_RISK = _get_float("KELLY_MAX_RISK", 0.02)  # teto 2% da banca
KELLY_MIN = _get_float("KELLY_MIN", 1.0)
KELLY_LOOKBACK = _get_int("KELLY_LOOKBACK", 50)
KELLY_PRIOR_WEIGHT = _get_float("KELLY_PRIOR_WEIGHT", 20.0)  # peso bayesiano do prior
KELLY_PAYOUT_DEFAULT = _get_float("KELLY_PAYOUT_DEFAULT", 0.87)

STOP_WIN = _get_float("IQ_STOP_WIN", 50.0)
STOP_LOSS = _get_float("IQ_STOP_LOSS", 30.0)

# Metas de Juros Compostos (% do saldo inicial do dia)
COMPOUND_META_DAILY = _get_float("COMPOUND_META_DAILY", 0.0)
COMPOUND_LOSS_DAILY = _get_float("COMPOUND_LOSS_DAILY", 0.0)

# Caminho para armazenar o snapshot do saldo diário
DAILY_META_FILE = os.getenv("DAILY_META_FILE", "data/daily_meta.json")
MAX_MARTINGALE = _get_int("IQ_MAX_MARTINGALE", 2)
MARTINGALE_MULTIPLIER = _get_float("IQ_MARTINGALE_MULTIPLIER", 2.0)

STRATEGY = os.getenv("STRATEGY", "donchian_fade")
DONCHIAN_N = _get_int("DONCHIAN_N", 20)
TREND_EMA = _get_int("TREND_EMA", 200)
# Higher timeframe p/ setup MTF (H1 = 3600s). HTF_EMA = viés (50 = validado no backtest 1y)
HTF_TIMEFRAME = _get_int("HTF_TIMEFRAME", 3600)
HTF_COUNT = _get_int("HTF_COUNT", 100)
HTF_EMA = _get_int("HTF_EMA", 50)
# RSI_REQUIRE_EXIT=0 (zona) = modo validado; 1 = só saída da zona
RSI_REQUIRE_EXIT = os.getenv("RSI_REQUIRE_EXIT", "0") == "1"
LOG_FILE = os.getenv("LOG_FILE", "data/bot.log")
TRADE_LOG = os.getenv("TRADE_LOG", "data/trades_live.csv")
MANUAL_SIGNAL = os.getenv("MANUAL_SIGNAL", "data/manual_signal.json")
BOT_STATUS = os.getenv("BOT_STATUS", "data/bot_status.json")
EMA_FAST = _get_int("EMA_FAST", 9)
EMA_SLOW = _get_int("EMA_SLOW", 21)
RSI_PERIOD = _get_int("RSI_PERIOD", 14)
RSI_OVERBOUGHT = _get_float("RSI_OVERBOUGHT", 70)
RSI_OVERSOLD = _get_float("RSI_OVERSOLD", 30)
BB_PERIOD = _get_int("BB_PERIOD", 20)
BB_MULT = _get_float("BB_MULT", 2.0)
MHI_TREND_EMA = _get_int("IQ_MHI_TREND_EMA", 100)
MHI_REQUIRE_TREND = os.getenv("IQ_MHI_REQUIRE_TREND", "1") == "1"

# Filtro Preditivo ML (XGBoost tau=0.62 ou Laya)
USE_ML_FILTER = os.getenv("USE_ML_FILTER", "1") == "1"
USE_LAYA_ORACLE = os.getenv("USE_LAYA_ORACLE", "0") == "1"
LAYA_MODEL_NAME = os.getenv("LAYA_MODEL_NAME", "convaiinnovations/laya")
ML_MODEL_PATH = os.getenv("ML_MODEL_PATH", "models/xgb_filter_v2.pkl")
ML_THRESHOLD = _get_float("ML_THRESHOLD", 0.62)
ML_FAIL_OPEN = os.getenv("ML_FAIL_OPEN", "0") == "1"

# Toxic hours: hours in UTC where trading is blocked
BLOCKED_HOURS_UTC = [int(h) for h in _get_list("BLOCKED_HOURS_UTC", ["5", "8", "12", "21", "23"])]

