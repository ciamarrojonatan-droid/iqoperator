import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta
import requests

log = logging.getLogger("iqrobot")

class NewsFilter:
    def __init__(self, cache_dir="data"):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        self.cache_file = os.path.join(self.cache_dir, "ff_calendar_cache.json")
        self.events = []
        self._load_cache()

    def _load_cache(self):
        # Cache file valid for the current UTC day
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("date") == today_str:
                        self.events = data.get("events", [])
                        return
            except Exception as e:
                log.warning(f"Error reading news cache: {e}")
        
        self._fetch_news(today_str)

    def _fetch_news(self, today_str):
        log.info("Fetching ForexFactory calendar...")
        try:
            resp = requests.get('https://nfs.faireconomy.media/ff_calendar_thisweek.json', timeout=10)
            if resp.status_code == 200:
                raw_events = resp.json()
                self.events = []
                for ev in raw_events:
                    try:
                        # parse datetime, example: '2026-09-27T19:50:00-04:00'
                        dt = datetime.fromisoformat(ev['date']).astimezone(timezone.utc)
                        self.events.append({
                            "title": ev.get("title", ""),
                            "country": ev.get("country", ""),
                            "impact": ev.get("impact", ""),
                            "timestamp": dt.timestamp()
                        })
                    except Exception:
                        pass
                
                with open(self.cache_file, "w", encoding="utf-8") as f:
                    json.dump({"date": today_str, "events": self.events}, f)
            else:
                log.warning(f"ForexFactory HTTP {resp.status_code}")
        except Exception as e:
            log.warning(f"Failed to fetch ForexFactory calendar: {e}")

    def is_news_time(self, current_utc_time: datetime, margin_minutes=30) -> bool:
        if not self.events:
            return False
            
        current_ts = current_utc_time.timestamp()
        margin_sec = margin_minutes * 60
        
        for ev in self.events:
            if ev.get("country") in ["USD", "EUR"] and ev.get("impact") == "High":
                ev_ts = ev.get("timestamp", 0)
                if abs(current_ts - ev_ts) <= margin_sec:
                    return True
        return False
