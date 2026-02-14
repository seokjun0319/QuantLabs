# -*- coding: utf-8 -*-
"""
QuantLabs - Upbit BTC/KRW 데이터 파이프라인
30일 일봉 수집 → data/btc_daily.csv 저장, 매 시간 업데이트.
"""
from pathlib import Path
from typing import Optional

import pandas as pd

from .slack_notifier import send_error_to_slack

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
BTC_DAILY_CSV = DATA_DIR / "btc_daily.csv"


def get_btc_krw_price() -> Optional[float]:
    """Upbit BTC/KRW 현재가 (원)."""
    try:
        import pyupbit
        return float(pyupbit.get_current_price("KRW-BTC") or 0) or None
    except Exception as e:
        send_error_to_slack(e, context="get_btc_krw_price")
        return None


def fetch_btc_krw_daily(count: int = 30) -> Optional[pd.DataFrame]:
    """Upbit API(pyupbit)로 BTC/KRW 최근 count일 일봉 조회."""
    try:
        import pyupbit
    except ImportError:
        send_error_to_slack(ImportError("pyupbit 미설치"), context="fetch_btc_krw_daily")
        return None
    try:
        df = pyupbit.get_ohlcv("KRW-BTC", interval="day", count=count)
        if df is None or df.empty:
            return None
        df.index.name = "date"
        df = df.rename(columns={"open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"})
        return df[["open", "high", "low", "close", "volume"]].sort_index()
    except Exception as e:
        send_error_to_slack(e, context="pyupbit get_ohlcv KRW-BTC")
        return None


def save_btc_daily(df: pd.DataFrame) -> bool:
    """일봉 데이터를 data/btc_daily.csv에 저장."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        df.to_csv(BTC_DAILY_CSV, encoding="utf-8")
        return True
    except Exception as e:
        send_error_to_slack(e, context="save_btc_daily")
        return False


def load_btc_daily() -> Optional[pd.DataFrame]:
    """data/btc_daily.csv 로드. 없으면 None."""
    if not BTC_DAILY_CSV.exists():
        return None
    try:
        df = pd.read_csv(BTC_DAILY_CSV, index_col=0, parse_dates=True)
        return df
    except Exception as e:
        send_error_to_slack(e, context="load_btc_daily")
        return None


def update_btc_daily_csv() -> bool:
    """30일 일봉 조회 후 data/btc_daily.csv 갱신. 매 시간 호출용."""
    df = fetch_btc_krw_daily(30)
    if df is None or df.empty:
        return False
    return save_btc_daily(df)
