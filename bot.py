"""RobÃ´ IQOption DEMO - BinÃ¡rias multi-ativo OTC | donchian_fade M15 + Kelly 2%.

- Opera todos os cfg.ASSETS em ciclo sequencial (1 scan ~= todos os ativos).
- Resultado de trade NÃƒO bloqueia o loop: posiÃ§Ãµes ficam em self.pending e sÃ£o
  conciliadas a cada ciclo (_reconcile_pending) via get_betinfo pontual.
- Trava global: no mÃ¡ximo cfg.MAX_CONCURRENT posiÃ§Ãµes pendentes simultÃ¢neas
  (manual via cockpit bypassa a trava, com log explÃ­cito).
- Log de trades com coluna asset; arquivo legado sem a coluna Ã© preservado
  como *_legacy.csv e um novo Ã© iniciado.
"""
import csv
import json
import logging
import os
import threading
import time
from collections import deque
from datetime import datetime, timezone, timedelta
import pandas as pd
from iqoptionapi.stable_api import IQ_Option

import config as cfg
from strategies import get_signal, rsi_series
from kelly import kelly_fraction_stake, empirical_winrate
from hf_sync import sync_file, download_file
from homeostasis import HomeostasisManager
from ml_filter import MLFilter
from news_filter import NewsFilter


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(cfg.LOG_FILE, encoding="utf-8"),
              logging.StreamHandler()],
)
log = logging.getLogger("iqrobot")

TRADE_HEADER = ["time", "asset", "signal", "info", "payout", "winrate",
                "kelly", "stake", "profit", "balance"]


class Bot:
    def __init__(self):
        self.api = IQ_Option(cfg.EMAIL, cfg.PASSWORD)
        # Serializa reconnects: threads abandonadas (timeout) chamam connect() por
        # conta prÃ³pria dentro da lib; sem lock elas trocam self.api no meio do
        # voo e geram 'NoneType is_ssl' / corridas no websocket.
        self._api_lock = threading.Lock()
        self._last_connect_ts = 0.0
        self.is_healing = False
        self._healing_started_ts = 0.0
        self.homeostasis = HomeostasisManager(self)
        self.homeostasis.patch_api(self.api)
        _orig_connect = self.api.connect

        def _locked_connect(*a, **k):
            # Serra autenticaÃ§Ã£o: intervalo mÃ­nimo entre handshakes (a lib e as
            # threads zumbis chamam connect() em loop durante outages; sem freio,
            # o martelo de logins toma throttle e derruba a conta).
            with self._api_lock:
                wait = 15.0 - (time.time() - self._last_connect_ts)
                if wait > 0:
                    self.homeostasis.sleep_with_heartbeat(wait)
                try:
                    return _orig_connect(*a, **k)
                finally:
                    self._last_connect_ts = time.time()

        self.api.connect = _locked_connect  # type: ignore[method-assign]
        self.assets = list(cfg.ASSETS)
        self.profit = 0.0
        self.asset_profit = {a: 0.0 for a in self.assets}
        self.history: dict[str, deque] = {a: deque(maxlen=cfg.KELLY_LOOKBACK) for a in self.assets}
        self.buys_attempted = 0
        self.buys_rejected = 0
        self.last_signal: dict[str, str | None] = {}
        self.last_payout: dict[str, float] = {}
        self.last_candle_key: dict[str, str] = {}
        self.last_check: dict[str, str] = {}
        self.pending: list[dict] = []
        self.martingale_step = 0
        self.current_amount = cfg.AMOUNT
        self._detail_cache: tuple[float, object] = (0.0, None)
        self._last_balance: float | None = None
        self._balance_ts = 0.0
        self._last_progress = time.time()
        self._candle_fail: dict[str, list] = {}  # asset -> [falhas_seg, pula_atÃ©]
        self._asset_cursor = 0
        self._empty_scans = 0
        self._quiet_until = 0.0
        self._consecutive_global_fails = 0
        self._hard_reconnect_count = 0
        self._trade_log_init()
        self._load_pending()
        model_path = "models/xgb_filter_m5.pkl" if cfg.TIMEFRAME == 300 else cfg.ML_MODEL_PATH
        self.ml_filter = MLFilter(model_path, cfg.ML_THRESHOLD, fail_open=cfg.ML_FAIL_OPEN) if cfg.USE_ML_FILTER else None
        self.news_filter = NewsFilter()


    # ---------- chamadas com timeout ----------
    def _call_timeout(self, fn, timeout: float, label: str):
        """Roda fn() com prazo; estourou -> (False, 'TIMEOUT...'). Nunca trava o loop."""
        import queue
        q: queue.Queue = queue.Queue()

        def _w():
            try:
                q.put((True, fn()))
            except Exception as e:  # noqa: BLE001
                q.put((False, f"{type(e).__name__}: {e}"))

        was_healing = getattr(self, "is_healing", False)
        t = threading.Thread(target=_w, daemon=True)
        t.start()
        t.join(timeout)
        if t.is_alive():
            # Se a chamada disparou homeostase de cura, aguarda a cura concluir com heartbeat.
            # health_ping tem timeout estrito de integridade e nunca aguarda cura.
            # Chamadas iniciadas quando a cura jÃ¡ estava ativa tambÃ©m nÃ£o aguardam recursivamente.
            if not was_healing and getattr(self, "is_healing", False) and label != "health_ping":
                log.info(f"{label}: chamada ativou estado de cura â€” aguardando conclusÃ£o...")
                wait_start = time.time()
                while t.is_alive() and getattr(self, "is_healing", False) and (time.time() - wait_start < 600.0):
                    self._touch_progress()
                    t.join(1.0)
                if t.is_alive():
                    t.join(2.0)
        if t.is_alive():
            return False, f"TIMEOUT apÃ³s {timeout:.0f}s em {label}"
        try:
            return q.get(timeout=0.5)
        except Exception:
            return False, f"sem resposta em {label}"

    def _safe_balance(self, timeout: float = 20) -> float:
        if self._last_balance is not None and time.time() - self._balance_ts < cfg.BALANCE_TTL:
            return self._last_balance

        def _fetch():
            bal = self.api.get_balance()
            if bal is None or not isinstance(bal, (int, float)):
                raise ValueError(f"get_balance retornou valor invÃ¡lido: {bal}")
            return float(bal)

        ok, res = self._call_timeout(_fetch, timeout, "get_balance")
        if ok and isinstance(res, (int, float)):
            self._last_balance = float(res)
            self._balance_ts = time.time()
            return self._last_balance
        log.warning(f"get_balance falhou ({res}); usando Ãºltimo conhecido.")
        return self._last_balance or 0.0

    def _touch_progress(self):
        self._last_progress = time.time()

    def _start_watchdog(self):
        def _w():
            while True:
                time.sleep(30)
                if getattr(self, "is_healing", False):
                    healing_started = getattr(self, "_healing_started_ts", 0.0)
                    if healing_started <= 0.0:
                        self._healing_started_ts = time.time()
                        healing_started = self._healing_started_ts
                    if (time.time() - healing_started) > 600.0:
                        log.error(f"WATCHDOG: processo travado em estado de cura hÃ¡ {time.time() - healing_started:.0f}s â€” reiniciando processo.")
                        os._exit(1)
                    log.info("WATCHDOG: Sistema em estado de cura autonÃ´mica â€” mantendo processo ativo.")
                    self._touch_progress()
                    continue
                idle = time.time() - self._last_progress
                if idle > cfg.WATCHDOG_TIMEOUT:
                    log.error(f"WATCHDOG: sem progresso hÃ¡ {idle:.0f}s â€” reiniciando processo.")
                    os._exit(1)
        threading.Thread(target=_w, daemon=True).start()

    # ---------- pendÃªncias em disco ----------
    def _save_pending(self):
        try:
            os.makedirs(os.path.dirname(cfg.PENDING_FILE) or ".", exist_ok=True)
            with open(cfg.PENDING_FILE, "w", encoding="utf-8") as f:
                json.dump(self.pending, f)
        except Exception as e:
            log.warning(f"save_pending: {e}")

    def _load_pending(self):
        try:
            if not os.path.exists(cfg.PENDING_FILE):
                return
            with open(cfg.PENDING_FILE, encoding="utf-8") as f:
                orders = json.load(f)
            now = time.time()
            kept = [o for o in orders if isinstance(o, dict) and o.get("deadline", 0) > now]
            dropped = len(orders) - len(kept)
            if dropped:
                log.warning(f"Descartando {dropped} pendÃªncia(s) expirada(s) do restart.")
            self.pending = kept
            if kept:
                log.info(f"Recuperadas {len(kept)} pendÃªncia(s) do disco.")
        except Exception as e:
            log.warning(f"load_pending: {e}")

    # ---------- log de trades ----------
    def _trade_log_init(self):
        from hf_sync import download_file
        if not os.path.exists(cfg.TRADE_LOG):
            download_file(cfg.TRADE_LOG)
            
        if not os.path.exists(cfg.TRADE_LOG):
            os.makedirs(os.path.dirname(cfg.TRADE_LOG) or ".", exist_ok=True)
            with open(cfg.TRADE_LOG, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(TRADE_HEADER)
            return
        try:
            with open(cfg.TRADE_LOG, encoding="utf-8") as f:
                lines = f.readlines()
            if not lines:
                return
            header = lines[0].strip().split(",")
            if header != TRADE_HEADER:
                legacy = cfg.TRADE_LOG.replace(".csv", "_legacy.csv")
                os.rename(cfg.TRADE_LOG, legacy)
                log.info(f"Trade log legado preservado em {legacy}; iniciando novo com coluna asset.")
                with open(cfg.TRADE_LOG, "w", newline="", encoding="utf-8") as f:
                    csv.writer(f).writerow(TRADE_HEADER)
            else:
                tz_br = timezone(timedelta(hours=-3))
                today_str = datetime.now(tz_br).strftime("%Y-%m-%d")
                for row in lines[1:]:
                    if not row.strip(): continue
                    cols = row.strip().split(",")
                    if len(cols) < 9: continue
                    tstamp, asset, signal, info, payout, p, kfull, stake, profit = cols[:9]
                    
                    try:
                        prof_f = float(profit)
                        won = prof_f > 0
                        if asset in self.history:
                            self.history[asset].append(won)
                        
                        # UTC date is close enough
                        if tstamp.startswith(today_str) or tstamp[:10] == today_str:
                            if asset in self.asset_profit:
                                self.asset_profit[asset] += prof_f
                    except ValueError:
                        pass
                log.info(f"Log restaurado: {sum(len(h) for h in self.history.values())} trades em memoria.")
        except Exception as e:
            log.warning(f"trade_log_init: {e}")
    def _trade_log(self, row: list):
        with open(cfg.TRADE_LOG, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)
        # sem disco no Railway: espelha no dataset HF (se HF_TOKEN + HF_DATASET_REPO setados)
        sync_file(cfg.TRADE_LOG)

    # ---------- conexÃ£o ----------
    def connect(self) -> bool:
        for attempt in range(1, 6):
            self._touch_progress()
            try:
                def _do_connect():
                    ok, reason = self.api.connect()
                    if not ok:
                        return False, reason
                    self.homeostasis.patch_api(self.api)
                    self.api.change_balance(cfg.BALANCE_TYPE)
                    bal = self.api.get_balance()
                    return True, bal

                ok, res = self._call_timeout(_do_connect, 20.0, f"connect_api_{attempt}")
                
                if ok:
                    try:
                        ok2, data = res
                    except (TypeError, ValueError):
                        ok2, data = False, str(res)
                        
                    if ok2:
                        bal = data
                        log.info(f"Conectado | Conta: {cfg.BALANCE_TYPE} | Saldo: {bal}")
                        try:
                            if hasattr(self.api, "update_ACTIVES_OPCODE"):
                                ok3, _ = self._call_timeout(self.api.update_ACTIVES_OPCODE, 10.0, "update_ACTIVES_OPCODE")
                                if not ok3:
                                    log.warning(f"update_ACTIVES_OPCODE timeout/erro (tent. {attempt})")
                        except Exception as e:
                            log.warning(f"update_ACTIVES_OPCODE exceÃ§Ã£o (tent. {attempt}): {e}")
                        return True
                    else:
                        log.warning(f"Connect falhou (tent. {attempt}): {data}")
                else:
                    log.warning(f"Connect bloqueado/timeout (tent. {attempt}): {res}")
                    # Se o socket travou a ponto de dar timeout, a API original estÃ¡ corrompida (zombie).
                    # ForÃ§amos a recriaÃ§Ã£o da instÃ¢ncia para a prÃ³xima tentativa do loop.
                    try:
                        if hasattr(self, "api") and hasattr(self.api, "api") and hasattr(self.api.api, "close"):
                            self.api.api.close()
                    except Exception:
                        pass
                    from iqoptionapi.stable_api import IQ_Option
                    self.api = IQ_Option(cfg.IQ_USER, cfg.IQ_PASS)

            except Exception as e:
                log.warning(f"Connect exceÃ§Ã£o (tent. {attempt}): {e}")
            self.homeostasis.sleep_with_heartbeat(min(5 * attempt, 30))
        return False

    def verify_connection(self) -> bool:
        """Ping real de conexÃ£o para validar se o websocket e a sessÃ£o estÃ£o operantes."""
        try:
            if not self.api.check_connect():
                return False
            ok, res = self._call_timeout(
                lambda: self.api.get_balance(), 10, "health_ping")
            return bool(ok and res is not None and isinstance(res, (int, float)))
        except Exception:
            return False

    def ensure_connected(self) -> bool:
        if getattr(self, "is_healing", False):
            return self.homeostasis.heal(reason="ensure_connected aguardando cura em andamento")
        if self.verify_connection():
            self._touch_progress()
            return True
        log.warning("ConexÃ£o perdida, acionando homeostase de reconexÃ£o...")
        return self.homeostasis.heal(reason="ensure_connected verify_connection falhou")

    # Fix 3: reconexÃ£o destrutiva â€” recria a instÃ¢ncia da API do zero
    def _hard_reconnect(self) -> bool:
        """DestrÃ³i a API atual e cria uma nova instÃ¢ncia limpa."""
        self._hard_reconnect_count += 1
        log.warning(f"HARD RECONNECT #{self._hard_reconnect_count}: recriando instÃ¢ncia da API")
        try:
            if hasattr(self.api, "api"):
                if hasattr(self.api.api, "websocket") and hasattr(self.api.api.websocket, "close"):
                    self.api.api.websocket.close()
                if hasattr(self.api.api, "websocket_thread") and hasattr(self.api.api.websocket_thread, "join"):
                    self.api.api.websocket_thread.join(timeout=2.0)
            elif hasattr(self.api, "close"):
                self.api.close()
        except Exception:
            pass
        self.api = IQ_Option(cfg.EMAIL, cfg.PASSWORD)
        _orig_connect = self.api.connect

        def _locked_connect(*a, **k):
            with self._api_lock:
                wait = 15.0 - (time.time() - self._last_connect_ts)
                if wait > 0:
                    self.homeostasis.sleep_with_heartbeat(wait)
                try:
                    return _orig_connect(*a, **k)
                finally:
                    self._last_connect_ts = time.time()

        self.api.connect = _locked_connect  # type: ignore[method-assign]
        self.homeostasis.patch_api(self.api)
        return self.connect()

    # ---------- dados ----------
    def candles_df(self, asset: str, timeframe: int, count: int,
                   timeout: float = 30) -> pd.DataFrame | None:
        # A lib entra em `while True + reconnect` se a conexÃ£o cair no meio do
        # get_candles â€” sem timeout, 1 ativo congela o scan inteiro (e o heartbeat).
        # Roda com prazo: estourou, pula o ativo neste ciclo.
        self._touch_progress()
        ok, res = self._call_timeout(
            lambda: self.api.get_candles(asset, timeframe, count, time.time(), timeout=timeout),
            timeout + 2.0, f"get_candles {asset}")
        self._touch_progress()
        if not ok:
            self._note_candle_fail(asset, str(res))
            if "need reconnect" in str(res).lower() or "timeout" in str(res).lower():
                self.homeostasis.heal(reason=f"candles_df {asset}: {res}")
            return None
        candles = res
        if not candles:
            self._note_candle_fail(asset, "vazio")
            return None
        self._candle_fail[asset] = [0, 0.0]
        df = pd.DataFrame(candles)
        df = df.rename(columns={"max": "high", "min": "low"})
        for c in ("high", "low", "close", "open"):
            if c not in df.columns:
                df[c] = df.get("close", 0)
        return df

    def _fetch_detail(self):
        """get_binary_option_detail com cache de 120s (a chamada Ã© lenta/instÃ¡vel)."""
        self._touch_progress()
        ts, cached = self._detail_cache
        if cached is not None and time.time() - ts < 120:
            return cached
        ok, detail = self._call_timeout(self.api.get_binary_option_detail, 30, "get_all_init")
        self._touch_progress()
        if not ok:
            log.warning(f"detail fallback: {detail}")
            return cached  # usa Ãºltimo conhecido (pode ser None)
        self._detail_cache = (time.time(), detail)
        return detail

    def get_payout(self, asset: str, detail=None) -> float:
        try:
            if detail is None:
                detail = self.api.get_binary_option_detail()
            v = detail.get(asset) if isinstance(detail, dict) else None
            if isinstance(v, dict):
                # estrutura real: {"binary": {"option": {"profit": {"commission": X}}}, ...}
                for k in ("binary", "turbo"):
                    sub = v.get(k)
                    if isinstance(sub, dict):
                        try:
                            commission = float(sub["option"]["profit"]["commission"])
                            return round((100.0 - commission) / 100.0, 4)
                        except (KeyError, TypeError, ValueError):
                            pass
                for k in ("profit", "payout", "turbo", "binary"):
                    if k in v:
                        num = v[k]
                        if isinstance(num, dict):
                            num = next(iter(num.values()), None)
                        if isinstance(num, (int, float)):
                            return float(num) / 100 if num > 1 else float(num)
            elif isinstance(v, (int, float)):
                return float(v) / 100 if v > 1 else float(v)
        except Exception as e:
            log.warning(f"payout fallback {asset}: {e}")
        return cfg.KELLY_PAYOUT_DEFAULT

    def calc_stake(self, asset: str, payout: float) -> tuple[float, float, float]:
        balance = self._safe_balance()
        p = empirical_winrate(list(self.history[asset]), cfg.KELLY_PRIOR,
                              prior_weight=cfg.KELLY_PRIOR_WEIGHT)
        if cfg.USE_KELLY:
            stake, kfull = kelly_fraction_stake(
                balance, payout, p, fraction=cfg.KELLY_FRACTION,
                max_risk=cfg.KELLY_MAX_RISK, min_amount=cfg.KELLY_MIN)
            return stake, p, kfull
        return round(self.current_amount, 2), p, 0.0

    # ---------- execuÃ§Ã£o nÃ£o-bloqueante ----------
    def _fire_buy(self, asset: str, action: str, stake: float):
        """Dispara o buy e retorna order dict (sem aguardar resultado)."""
        self.buys_attempted += 1
        balance_before = self._safe_balance()
        ok, res = self._call_timeout(
            lambda: self.api.buy(stake, asset, action, cfg.EXPIRATION),
            30, f"buy {asset}")
        if not ok:
            self.buys_rejected += 1
            log.error(f"Buy TIMEOUT ({self.buys_rejected}/{self.buys_attempted}): {res} (ativo={asset})")
            return None
        ok2, order_id = res
        if not ok2:
            self.buys_rejected += 1
            log.error(f"Buy rejeitado ({self.buys_rejected}/{self.buys_attempted}): {order_id} (ativo={asset})")
            return None
        log.info(f"TRADE {action.upper()} {asset} M{cfg.EXPIRATION} stake={stake} id={order_id}")
        return {"order_id": order_id, "asset": asset, "action": action,
                "stake": stake, "balance_before": balance_before,
                "deadline": time.time() + cfg.EXPIRATION * 60 + 180,
                "signal": None, "info": None, "payout": None, "p": None, "kfull": None}

    def _poll_pending(self, order: dict) -> float | None:
        """Uma consulta assÃ­ncrona de resultado; None = ainda pendente/desconhecido."""
        self._touch_progress()
        order_id = order["order_id"]
        try:
            async_order = self.api.get_async_order(order_id)
            if async_order and async_order.get("option-closed"):
                closed_data = async_order["option-closed"]
                msg = closed_data.get("msg", {})
                profit_amount = float(msg.get("profit_amount", 0.0))
                amount = float(msg.get("amount", 0.0))
                return float(profit_amount - amount)
        except Exception as e:
            log.warning(f"_poll_pending id={order_id} falhou ao ler dicionÃ¡rio assÃ­ncrono: {e}")
            return None
        return None

    def _settle(self, order: dict, profit: float, estimated: bool = False):
        tag = "RESULT_TIMEOUT(est)" if estimated else ("WIN" if profit > 0 else "LOSS")
        self.update_result(order["asset"], order.get("signal") or order["action"],
                           order.get("info") or "AUTO", order.get("payout") or 0,
                           order.get("p") or 0, order.get("kfull") or 0,
                           order["stake"], round(profit, 2))
        log.info(f"{tag} {order['asset']} {profit:+.2f} id={order['order_id']}")

    def _reconcile_pending(self):
        for order in list(self.pending):
            self._touch_progress()
            profit = self._poll_pending(order)
            if profit is not None:
                self.pending.remove(order)
                self._save_pending()
                self._settle(order, profit)
                continue
            if time.time() > order["deadline"]:
                self.pending.remove(order)
                self._save_pending()
                balance_now = self._safe_balance()
                est = round(balance_now - order["balance_before"], 2)
                log.warning(f"RESULT_TIMEOUT id={order['order_id']} â€” sem betinfo; profit estimado via saldo: {est:+.2f}")
                self._settle(order, est, estimated=True)

    # ---------- resultado ----------
    def update_result(self, asset: str, signal: str, info: object, payout: float,
                      p: float, kfull: float, stake: float, profit: float):
        self.profit += profit
        self.asset_profit[asset] = self.asset_profit.get(asset, 0.0) + profit
        won = profit > 0
        self.history[asset].append(won)
        balance = self._safe_balance()
        tag = "WIN" if won else "LOSS"
        wr = empirical_winrate(list(self.history[asset]), cfg.KELLY_PRIOR,
                               prior_weight=cfg.KELLY_PRIOR_WEIGHT)
        log.info(f"{tag} {asset} {profit:+.2f} | SessÃ£o {self.profit:+.2f} | saldo {balance} | wr {wr:.2f}")
        self._trade_log([datetime.now().isoformat(timespec="seconds"), asset, signal,
                         info, round(payout, 4), round(p, 4),
                         kfull, stake, round(profit, 2), balance])
        self._write_status()

    def _note_candle_fail(self, asset: str, reason):
        fails, _ = self._candle_fail.get(asset, [0, 0.0])
        fails += 1
        if fails >= cfg.CANDLE_FAIL_LIMIT:
            until = time.time() + cfg.CANDLE_COOLDOWN
            self._candle_fail[asset] = [fails, until]
            log.warning(f"{asset}: {fails} falhas de candles ({reason}) â€” em cooldown {cfg.CANDLE_COOLDOWN}s.")
        else:
            self._candle_fail[asset] = [fails, 0.0]
            log.warning(f"get_candles {asset}: {reason} â€” pulando ciclo ({fails}/{cfg.CANDLE_FAIL_LIMIT}).")

    def _in_cooldown(self, asset: str) -> bool:
        fails, until = self._candle_fail.get(asset, [0, 0.0])
        if until and time.time() < until:
            return True
        if until and time.time() >= until:
            self._candle_fail[asset] = [0, 0.0]
        return False

    def _next_subset(self) -> list[str]:
        """Round-robin: N ativos por ciclo (corta a taxa de requests sem perder cobertura)."""
        n = max(1, min(cfg.ASSETS_PER_CYCLE, len(self.assets)))
        subset = [self.assets[(self._asset_cursor + i) % len(self.assets)] for i in range(n)]
        self._asset_cursor = (self._asset_cursor + n) % len(self.assets)
        return subset

    def _candle_key(self, df) -> str:
        """Chave robusta do Ãºltimo candle (vÃ¡rias versÃµes da API usam 'from'/'at'/etc)."""
        last = df.iloc[-1]
        for col in ("from", "at", "open_time", "time", "date", "timestamp"):
            if col in df.columns:
                try:
                    v = int(float(last[col]))
                    if v > 0:
                        return f"{col}:{v}"
                except (TypeError, ValueError):
                    continue
        # fallback: usa o close (avalia todo loop, sem dedup por tempo)
        try:
            return f"noclock:{float(last['close'])}"
        except (TypeError, ValueError, KeyError):
            return f"row:{len(df)}"

    def _write_status(self):
        try:
            self._touch_progress()
            os.makedirs(os.path.dirname(cfg.BOT_STATUS) or ".", exist_ok=True)
            per_asset = []
            for a in self.assets:
                wr = empirical_winrate(list(self.history[a]), cfg.KELLY_PRIOR,
                                       prior_weight=cfg.KELLY_PRIOR_WEIGHT)
                per_asset.append({
                    "asset": a,
                    "profit_session": round(self.asset_profit.get(a, 0.0), 2),
                    "trades": len(self.history[a]),
                    "winrate": round(wr, 4),
                    "last_signal": self.last_signal.get(a),
                    "last_payout": self.last_payout.get(a),
                    "last_check": self.last_check.get(a),
                })
            ml_tag = f"ON (tau={cfg.ML_THRESHOLD})" if (self.ml_filter and self.ml_filter.is_loaded) else "OFF"
            
            balance_now = self._safe_balance() if hasattr(self, 'api') else 0.0
            start_balance = self._get_daily_base(balance_now)
            
            if cfg.COMPOUND_META_DAILY > 0:
                win_target = start_balance * (cfg.COMPOUND_META_DAILY / 100.0)
                is_compound = True
                display_profit = balance_now - start_balance
            else:
                win_target = cfg.STOP_WIN
                is_compound = False
                display_profit = self.profit
                
            if cfg.COMPOUND_LOSS_DAILY > 0:
                loss_target = start_balance * (cfg.COMPOUND_LOSS_DAILY / 100.0)
            else:
                loss_target = cfg.STOP_LOSS
                
            with open(cfg.BOT_STATUS, "w", encoding="utf-8") as f:
                json.dump({
                    "last_tick": datetime.now(timezone.utc).isoformat(),
                    "asset": f"multi:{len(self.assets)}",
                    "assets": per_asset,
                    "balance": self._safe_balance() if hasattr(self, 'api') else None,
                    "balance_type": cfg.BALANCE_TYPE,
                    "strategy": cfg.STRATEGY,
                    "ml_filter_status": ml_tag,
                    "profit_session": round(display_profit, 2),
                    "win_target": round(win_target, 2),
                    "loss_target": round(loss_target, 2),
                    "is_compound": is_compound,
                    "trades": sum(len(h) for h in self.history.values()),
                    "buys_attempted": self.buys_attempted,
                    "buys_rejected": self.buys_rejected,
                    "pending": len(self.pending),
                    "max_concurrent": cfg.MAX_CONCURRENT,
                }, f)
        except Exception:
            pass

    def _check_manual(self) -> dict | None:
        try:
            if not os.path.exists(cfg.MANUAL_SIGNAL):
                return None
            with open(cfg.MANUAL_SIGNAL, encoding="utf-8") as f:
                data = json.load(f)
            ts = data.get("ts", 0)
            if time.time() - ts > 60:
                os.remove(cfg.MANUAL_SIGNAL)
                return None
            sig = data.get("signal")
            if sig not in ("call", "put"):
                os.remove(cfg.MANUAL_SIGNAL)
                return None
            os.remove(cfg.MANUAL_SIGNAL)
            asset = str(data.get("asset") or self.assets[0]).upper()
            if asset not in self.assets:
                log.warning(f"MANUAL ignorado: ativo {asset} fora da lista {self.assets}")
                return None
            stake = data.get("stake")
            try:
                stake = float(stake) if stake is not None else None
            except (TypeError, ValueError):
                stake = None
            log.info(f"MANUAL {sig.upper()} {asset} solicitado via cockpit")
            return {"signal": sig, "asset": asset, "stake": stake}
        except Exception as e:
            log.warning(f"manual check falhou: {e}")
            return None

    def _manual_stake(self, asset: str, payout: float, want: float | None) -> tuple[float, float, float]:
        if want is not None and want > 0:
            balance = self._safe_balance()
            cap = max(balance * 0.05, cfg.KELLY_MIN)
            if want <= cap:
                p = empirical_winrate(list(self.history[asset]), cfg.KELLY_PRIOR,
                                      prior_weight=cfg.KELLY_PRIOR_WEIGHT)
                return round(want, 2), p, 0.0
            log.warning(f"MANUAL stake {want} acima do teto {cap:.2f}; usando Kelly.")
        return self.calc_stake(asset, payout)

    def _get_daily_base(self, current_balance: float) -> float:
        """Carrega ou cria o snapshot diÃ¡rio do saldo (GMT-3)"""
        tz_br = timezone(timedelta(hours=-3))
        today_str = datetime.now(tz_br).strftime("%Y-%m-%d")
        
        data = {}
        if os.path.exists(cfg.DAILY_META_FILE):
            try:
                with open(cfg.DAILY_META_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass

        if data.get("date") == today_str:
            return float(data.get("start_balance", current_balance))
        else:
            # Virou o dia, salva a nova base de juros compostos
            data = {
                "date": today_str,
                "start_balance": current_balance
            }
            os.makedirs(os.path.dirname(cfg.DAILY_META_FILE) or ".", exist_ok=True)
            with open(cfg.DAILY_META_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f)
            log.info(f"[JUROS COMPOSTOS] Novo dia iniciado ({today_str}). Base atualizada para {current_balance:.2f}")
            # Zera o profit da sessÃ£o para nÃ£o acumular de dias anteriores
            self.profit = 0.0
            for a in self.assets:
                self.asset_profit[a] = 0.0
            return current_balance

    def stop(self) -> bool:
        if not hasattr(self, 'api') or not self.api:
            return False
            
        current_balance = self._safe_balance()
        start_balance = self._get_daily_base(current_balance)
        
        if cfg.COMPOUND_META_DAILY > 0:
            win_target = start_balance * (cfg.COMPOUND_META_DAILY / 100.0)
            daily_profit = current_balance - start_balance
        else:
            win_target = cfg.STOP_WIN
            daily_profit = self.profit
            
        if cfg.COMPOUND_LOSS_DAILY > 0:
            loss_target = start_balance * (cfg.COMPOUND_LOSS_DAILY / 100.0)
            loss_profit = current_balance - start_balance
        else:
            loss_target = cfg.STOP_LOSS
            loss_profit = self.profit

        if loss_profit <= -loss_target:
            log.error(f"Stop loss atingido: profit={loss_profit:.2f} <= limite=-{loss_target:.2f}")
            return True
        if daily_profit >= win_target:
            log.info(f"Stop win atingido: profit={daily_profit:.2f} >= meta={win_target:.2f}")
            return True
        return False

    def run(self):
        if not cfg.EMAIL or not cfg.PASSWORD:
            log.error("Configure IQ_EMAIL e IQ_PASSWORD no .env")
            return
        if cfg.BALANCE_TYPE == "REAL" and os.getenv("CONFIRM_REAL") != "YES":
            log.error("Conta REAL sem CONFIRM_REAL=YES â€” abortando por seguranÃ§a. Use PRACTICE.")
            return
        if not self.connect():
            return
        self._start_watchdog()

        ml_tag = f"ON(tau={cfg.ML_THRESHOLD})" if (self.ml_filter and self.ml_filter.is_loaded) else "OFF"
        log.info(f"START multi:{len(self.assets)} {','.join(self.assets)} | {cfg.STRATEGY} "
                 f"RSI({cfg.RSI_PERIOD}) {cfg.RSI_OVERSOLD}/{cfg.RSI_OVERBOUGHT} "
                 f"exit={int(cfg.RSI_REQUIRE_EXIT)} H1_EMA={cfg.HTF_EMA} | Kelly "
                 f"{cfg.KELLY_FRACTION}x teto {cfg.KELLY_MAX_RISK*100:.0f}% | max_concurrent={cfg.MAX_CONCURRENT} | ML_Filter={ml_tag}")
        errors = 0

        try:
            while True:
                try:
                    self._touch_progress()
                    if self.stop():
                        break
                    if not self.ensure_connected():
                        log.error("HOMEOSTASE: ConexÃ£o nÃ£o restabelecida apÃ³s ciclo de cura â€” reiniciando processo.")
                        os._exit(1)
                    self._write_status()
                    if time.time() < self._quiet_until:
                        # disjuntor global: silÃªncio total p/ resetar o throttle
                        left = self._quiet_until - time.time()
                        log.info(f"Disjuntor ativo: {left:.0f}s restantes de silÃªncio.")
                        self.homeostasis.sleep_with_heartbeat(min(15.0, max(1.0, left)))
                        self._touch_progress()
                        continue
                    detail = self._fetch_detail()
                    if detail is None:
                        log.info("Sem detail de payout, aguardando.")
                        self.homeostasis.sleep_with_heartbeat(60.0)
                        self._touch_progress()
                        continue
                    self._reconcile_pending()

                    # sinal manual tem prioridade (botao cockpit)
                    manual = self._check_manual()
                    if manual:
                        asset = manual["asset"]
                        payout = self.get_payout(asset, detail)
                        if payout < cfg.PAYOUT_MIN:
                            log.info(f"MANUAL {asset} ignorado: payout {payout:.2f} < mÃ­nimo.")
                        else:
                            stake, p, kfull = self._manual_stake(asset, payout, manual["stake"])
                            order = self._fire_buy(asset, manual["signal"], stake)
                            if order:
                                order.update({"signal": manual["signal"], "info": "MANUAL",
                                              "payout": payout, "p": p, "kfull": kfull})
                                self.pending.append(order)
                                self._save_pending()
                                if len(self.pending) > cfg.MAX_CONCURRENT:
                                    log.warning(f"MANUAL bypass cap ({len(self.pending)}/{cfg.MAX_CONCURRENT} pendentes).")
                        time.sleep(5)
                        continue

                    subset = self._next_subset()
                    got = 0
                    current_utc = datetime.now(timezone.utc)
                    is_toxic = current_utc.hour in cfg.BLOCKED_HOURS_UTC
                    is_news = self.news_filter.is_news_time(current_utc)
                    
                    for i, asset in enumerate(subset):
                        self._touch_progress()
                        if i:
                            time.sleep(cfg.ASSET_DELAY)
                        if self._in_cooldown(asset):
                            continue
                        if is_toxic:
                            if i == 0: log.info(f"Toxic Hour ({current_utc.hour} UTC) - skipping scan.")
                            continue
                        if is_news:
                            if i == 0: log.info(f"High Impact News Time - skipping scan.")
                            continue
                        payout = self.get_payout(asset, detail)
                        if payout < cfg.PAYOUT_MIN:
                            continue
                        df = self.candles_df(asset, cfg.TIMEFRAME, cfg.CANDLE_COUNT)
                        if df is None or df.empty:
                            log.warning(f"Sem candles ({asset} M{cfg.EXPIRATION}) â€” aguardando.")
                            continue
                        got += 1
                        candle_key = self._candle_key(df)
                        if candle_key == self.last_candle_key.get(asset):
                            continue
                        self.last_candle_key[asset] = candle_key
                        if candle_key.startswith("noclock:"):
                            log.warning(f"{asset}: coluna de tempo ausente nos candles â€” avaliando sem dedup por candle.")

                        df_h1 = None
                        if cfg.STRATEGY == "rsi_mtf_pullback":
                            df_h1 = self.candles_df(asset, cfg.HTF_TIMEFRAME, cfg.HTF_COUNT)
                            if df_h1 is None or df_h1.empty:
                                continue

                        signal = get_signal(cfg.STRATEGY, df, cfg, df_h1)
                        self.last_signal[asset] = signal
                        close_px = float(df["close"].iloc[-1])
                        if cfg.STRATEGY == "donchian_fade":
                            info: object = f"DC{cfg.DONCHIAN_N}"
                            n = cfg.DONCHIAN_N
                            hi = float(df["high"].iloc[-n - 1:-1].max())
                            lo = float(df["low"].iloc[-n - 1:-1].min())
                            detail_s = f"close={close_px:.2f} hi20={hi:.2f} lo20={lo:.2f}"
                        elif cfg.STRATEGY == "bollinger_touch":
                            info = f"BB{cfg.BB_PERIOD}"
                            detail_s = f"close={close_px:.2f} BB({cfg.BB_PERIOD},{cfg.BB_MULT})"
                        elif cfg.STRATEGY == "multi_mean_reversion":
                            info = "MULTI"
                            rsi_val = round(float(rsi_series(df["close"], cfg.RSI_PERIOD).iloc[-1]), 1)
                            detail_s = f"close={close_px:.2f} RSI={rsi_val} MULTI"
                        else:
                            info = round(float(rsi_series(df["close"], cfg.RSI_PERIOD).iloc[-1]), 1)
                            detail_s = f"close={close_px:.2f} RSI={info}"
                        self.last_payout[asset] = payout
                        self.last_check[asset] = f"{detail_s} signal={signal} payout={payout:.2f}"
                        log.info(f"[CHECK] {asset} {candle_key} {detail_s} -> {signal} (payout {payout:.2f})")
                        self._write_status()
                        if not signal:
                            continue
                        if len(self.pending) >= cfg.MAX_CONCURRENT:
                            log.info(f"SINAL {signal.upper()} {asset} ignorado: cap {cfg.MAX_CONCURRENT} pendentes atingido.")
                            continue

                        # Filtro Preditivo ML (XGBoost tau=0.62)
                        if self.ml_filter:
                            allowed, prob = self.ml_filter.filter_signal(df, signal, threshold=cfg.ML_THRESHOLD)
                            if not allowed:
                                log.info(f"[ML FILTER] False Breakout detectado, trade cancelado ({asset} {signal.upper()}, prob={prob:.4f} < {cfg.ML_THRESHOLD})")
                                continue
                            log.info(f"[ML FILTER] Trade aprovado ({asset} {signal.upper()}, prob={prob:.4f} >= {cfg.ML_THRESHOLD})")

                        stake, p, kfull = self.calc_stake(asset, payout)

                        log.info(f"SINAL {signal.upper()} {asset} {info} payout={payout:.2f} "
                                 f"p={p:.2f} kelly={kfull:.3f} stake={stake:.2f}")
                        order = self._fire_buy(asset, signal, stake)
                        if order:
                            order.update({"signal": signal, "info": info,
                                          "payout": payout, "p": p, "kfull": kfull})
                            self.pending.append(order)
                            self._save_pending()
                    if got == 0 and not (is_toxic or is_news):
                        self._empty_scans += 1
                        self._consecutive_global_fails += 1
                        if self._consecutive_global_fails >= cfg.MAX_GLOBAL_ERRORS:
                            log.warning(f"OUTAGE GLOBAL: {self._consecutive_global_fails} ciclos "
                                        f"sem dados de nenhum ativo â€” acionando homeostase.")
                            if not self.homeostasis.heal(reason="outage global de ativos"):
                                log.error("Homeostase nÃ£o conseguiu recuperar conexÃ£o no outage global â€” forÃ§ando restart.")
                                os._exit(1)
                        if self._empty_scans >= 3:
                            self._empty_scans = 0
                            self._quiet_until = time.time() + cfg.GLOBAL_COOLDOWN
                            log.warning(f"Disjuntor global: 3 scans sem candles â€” silÃªncio de {cfg.GLOBAL_COOLDOWN}s p/ resetar o throttle.")
                    elif got > 0 or is_toxic or is_news:
                        self._empty_scans = 0
                        self._consecutive_global_fails = 0
                        self._hard_reconnect_count = 0  # conexÃ£o saudÃ¡vel, reseta
                    self._touch_progress()
                    errors = 0
                    time.sleep(cfg.SCAN_SLEEP)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    errors += 1
                    log.error(f"Erro no loop ({errors}): {e}")
                    self.homeostasis.sleep_with_heartbeat(min(60.0 * errors, 300.0))
                    self._touch_progress()
        except KeyboardInterrupt:
            log.info("Interrompido pelo usuÃ¡rio.")
        finally:
            try:
                log.info(f"FIM SessÃ£o {self.profit:.2f} | Saldo {self._safe_balance()}")
            except Exception:
                log.info(f"FIM SessÃ£o {self.profit:.2f}")

