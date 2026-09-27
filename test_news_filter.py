import logging
from datetime import datetime, timezone
from news_filter import NewsFilter

logging.basicConfig(level=logging.INFO)

print("Testing NewsFilter normal operation:")
nf = NewsFilter(cache_dir="data_test")
print("Events loaded:", len(nf.events))

print("Testing is_news_time with an empty event list (simulating timeout):")
nf.events = []
print("is_news_time:", nf.is_news_time(datetime.now(timezone.utc)))
