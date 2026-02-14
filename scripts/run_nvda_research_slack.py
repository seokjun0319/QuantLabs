# -*- coding: utf-8 -*-
"""
NVDA 백테스팅 최적화 연구 — 첫 보고부터 슬랙으로 실시간 전송.
10회마다 중간 보고, 완료 시 종합 리포트.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.slack_notifier import send_slack_message
from modules.nvda_engine import build_indicator_df, optimize_golden_params_with_slack


def main():
    # 1) 첫 보고: 연구 시작
    send_slack_message(
        "🔬 NVDA Alpha-V1 최적화 연구를 지금 시작합니다.\n"
        "10회마다 최고 수익률·파라미터 상황을 보고드립니다.",
        title="QuantLabs 연구 시작",
        color="#2196F3",
    )
    # 2) 데이터 로드
    df = build_indicator_df(365)
    if df is None or len(df) < 60:
        send_slack_message("⚠️ NVDA 1년 데이터 로드 실패. 연구 중단.", title="QuantLabs", color="#ff0000")
        return 1
    # 3) 최적화 (10회마다 슬랙 보고, 완료 시 종합 리포트 자동 전송)
    optimize_golden_params_with_slack(
        df,
        target_return=0.30,
        target_mdd=0.15,
        max_iter=50,
        report_interval=10,
    )
    send_slack_message(
        "대장님, NVDA 최적화 모형 연구를 완료했습니다. 이제부터 실시간 감시에 들어갑니다.",
        title="QuantLabs NVDA 완료",
        color="#76b900",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
