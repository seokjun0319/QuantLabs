# -*- coding: utf-8 -*-
"""
QuantLabs - VBS 변동성 돌파 야간 감시
1분마다 현재가 체크, 목표가 돌파 시 슬랙 알림 1회 전송.
종료: Ctrl+C
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.upbit_fetcher import load_btc_daily, update_btc_daily_csv, get_btc_krw_price
from modules.vbs_backtest import get_best_k, get_today_target_and_remaining
from modules.slack_notifier import send_slack_message

INTERVAL_SEC = 60
SENT_TODAY_FILE = ROOT / ".cursor" / "vbs_alert_sent_date.txt"


def get_today_date_str():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")


def already_sent_today() -> bool:
    if not SENT_TODAY_FILE.exists():
        return False
    return SENT_TODAY_FILE.read_text(encoding="utf-8").strip() == get_today_date_str()


def mark_sent_today():
    SENT_TODAY_FILE.parent.mkdir(parents=True, exist_ok=True)
    SENT_TODAY_FILE.write_text(get_today_date_str(), encoding="utf-8")


def run_once():
    df = load_btc_daily()
    if df is None or len(df) < 2:
        update_btc_daily_csv()
        df = load_btc_daily()
    if df is None or len(df) < 2:
        return
    best_k, _ = get_best_k(df, k_min=0.3, k_max=0.7, step=0.05)
    current = get_btc_krw_price()
    target, remaining_pct = get_today_target_and_remaining(df, current or 0, best_k)
    if target is None or current is None:
        return
    if already_sent_today():
        return
    if current >= target:
        msg = (
            f"[🚨 돌파 알림] 지금 비트코인이 목표가 {target:,.0f}원을 돌파했습니다! 매수 검토하세요.\n"
            f"현재가: {current:,.0f}원 / 목표가: {target:,.0f}원 (K={best_k:.2f})"
        )
        if send_slack_message(msg, title="QuantLabs VBS 돌파", color="#ff0000"):
            mark_sent_today()
            print(f"[{time.strftime('%H:%M:%S')}] 돌파 알림 전송 완료.")


def main():
    print("[QuantLabs VBS Monitor] 1분마다 목표가 체크. 종료: Ctrl+C")
    while True:
        try:
            run_once()
            time.sleep(INTERVAL_SEC)
        except KeyboardInterrupt:
            print("\n중지.")
            break
        except Exception as e:
            print(f"오류: {e}")
            time.sleep(INTERVAL_SEC)


if __name__ == "__main__":
    main()
