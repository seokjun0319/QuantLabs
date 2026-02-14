# -*- coding: utf-8 -*-
"""매 시간 data/btc_daily.csv 업데이트 (cron/스케줄러에서 호출)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.upbit_fetcher import update_btc_daily_csv

if __name__ == "__main__":
    ok = update_btc_daily_csv()
    sys.exit(0 if ok else 1)
