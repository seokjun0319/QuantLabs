# -*- coding: utf-8 -*-
"""
QuantLabs 09시 전체 요약 리포트 발송
스케줄러(예: 09:00)에서 실행하면 대장님 슬랙으로 요약 전송.
"""
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.upbit_fetcher import load_btc_daily, get_btc_krw_price
from modules.vbs_backtest import get_best_k, get_today_target_and_remaining
from modules.slack_notifier import send_daily_report_09am


def build_report() -> str:
    lines = [
        f"📅 QuantLabs 일일 리포트 ({datetime.now().strftime('%Y-%m-%d %H:%M')})",
        "",
        "【VBS 변동성 돌파】",
    ]
    df = load_btc_daily()
    if df is not None and len(df) >= 2:
        best_k, _ = get_best_k(df, 0.3, 0.7, 0.05)
        current = get_btc_krw_price()
        target, remaining = get_today_target_and_remaining(df, current or 0, best_k)
        lines.append(f"- 추천 K값: {best_k:.2f}")
        lines.append(f"- BTC/KRW 현재가: {current:,.0f}원" if current else "- 현재가: 조회 실패")
        if target is not None:
            lines.append(f"- 오늘 목표가: {target:,.0f}원")
            if remaining is not None:
                lines.append(f"- 돌파까지 남은 %: {remaining:.2f}%" if remaining > 0 else "- 상태: 돌파 완료")
    else:
        lines.append("- 일봉 데이터 없음. update_btc_daily_csv 실행 후 재시도.")
    lines.extend(["", "QuantLabs — Data-Driven Wealth"])
    return "\n".join(lines)


if __name__ == "__main__":
    report = build_report()
    ok = send_daily_report_09am(report)
    print("09시 리포트 전송:", "성공" if ok else "실패")
    sys.exit(0 if ok else 1)
