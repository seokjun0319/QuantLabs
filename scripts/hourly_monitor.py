# -*- coding: utf-8 -*-
"""
QuantLabs 1시간 주기 통합 감시관
- 비트코인: 현재가, VBS 돌파 타점과의 거리, 추천 K값
- 엔비디아(NVDA): 실시간 시세, 20/50일 이격도
- PM급 인사이트 1줄 + 한글 UTF-8 이모지 슬랙 보고
- 야간(한국 22~07시)에는 NVDA 변동폭 최우선 배치
"""
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.upbit_fetcher import load_btc_daily, update_btc_daily_csv, get_btc_krw_price
from modules.vbs_backtest import get_best_k, get_today_target_and_remaining
from modules.nvda_fetcher import (
    get_nvda_ma_distance,
    get_nvda_rsi,
)
from modules.nvda_engine import (
    build_indicator_df,
    load_golden_params,
    get_current_buy_score,
    valuation_vs_volatility,
)
from modules.slack_notifier import send_slack_message


def _is_us_market_hours_kst() -> bool:
    """한국 시간 기준 미장(미국 주식) 매매 시간대: 22:00~07:00 KST 근사."""
    from datetime import timezone, timedelta
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst).time()
    return now.hour >= 22 or now.hour < 7


def _btc_insight(remaining_pct: float, current: float, target: float) -> str:
    if remaining_pct <= 0:
        return "🚨 변동성 돌파 완료. 매수 검토 구간."
    if remaining_pct < 1:
        return "📈 돌파 직전, 힘 응축 중."
    if remaining_pct < 3:
        return "📊 목표가 근접. 관망 권장."
    return "⏳ 목표가까지 여유. 대기."


def _nvda_insight(dist20: float, dist50: float, rsi: float) -> str:
    if rsi is not None and rsi >= 70:
        return "📉 RSI 과매수 구간으로 보임. 조정 가능성."
    if rsi is not None and rsi <= 30:
        return "📈 RSI 과매도 구간. 반등 관찰."
    if dist20 is not None and dist20 > 5:
        return "📈 단기 이격 확대. 추세 강함."
    if dist20 is not None and dist20 < -3:
        return "📉 20일선 이탈. 관망."
    return "📊 이격도 중립. 추세 확인 중."


def run_once():
    lines = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    nvda_first = _is_us_market_hours_kst()

    # ----- NVDA -----
    nvda_price, ma20, ma50, dist20, dist50 = get_nvda_ma_distance()
    nvda_rsi = get_nvda_rsi(14)
    tech_score = 50
    valuation_txt = "중립"
    try:
        df_nvda = build_indicator_df(365)
        if df_nvda is not None and len(df_nvda) > 0:
            params, _ = load_golden_params()
            tech_score = int(get_current_buy_score(df_nvda, **{k: v for k, v in params.items() if k in ["w_ma", "w_rsi", "w_atr", "rsi_ob", "rsi_rel", "atr_k"]}))
            valuation_txt = valuation_vs_volatility(df_nvda)
    except Exception:
        pass
    nvda_block = [
        "【📈 엔비디아 NVDA】",
        f"현재가: ${nvda_price:,.2f}" if nvda_price else "현재가: —",
        f"기술적 점수(Alpha-V1): {tech_score}점",
        f"20일선 이격도: {dist20:+.2f}%" if dist20 is not None else "20일 이격: —",
        f"50일선 이격도: {dist50:+.2f}%" if dist50 is not None else "50일 이격: —",
        f"RSI(14): {nvda_rsi:.1f}" if nvda_rsi is not None else "RSI: —",
        f"💰 인사이트: 현재 최적화된 모형에 따른 기술적 점수는 {tech_score}점이며, {valuation_txt}.",
        _nvda_insight(dist20 or 0, dist50 or 0, nvda_rsi or 50),
        "",
    ]
    btc_block = [
        "【₿ 비트코인 BTC/KRW】",
    ]

    df = load_btc_daily()
    if df is None or len(df) < 2:
        update_btc_daily_csv()
        df = load_btc_daily()
    if df is not None and len(df) >= 2:
        best_k, _ = get_best_k(df, 0.3, 0.7, 0.05)
        current_btc = get_btc_krw_price()
        target, remaining_pct = get_today_target_and_remaining(df, current_btc or 0, best_k)
        btc_block.append(f"현재가: {current_btc:,.0f}원" if current_btc else "현재가: —")
        btc_block.append(f"추천 K값: {best_k:.2f}")
        if target is not None:
            btc_block.append(f"오늘 목표가: {target:,.0f}원")
            if remaining_pct is not None:
                btc_block.append(f"돌파까지: {remaining_pct:.2f}%")
                btc_block.append(_btc_insight(remaining_pct, current_btc or 0, target))
    else:
        btc_block.append("일봉 데이터 없음.")
    btc_block.append("")

    if nvda_first:
        lines.extend(nvda_block)
        lines.extend(btc_block)
    else:
        lines.extend(btc_block)
        lines.extend(nvda_block)

    lines.insert(0, f"🕐 QuantLabs 1시간 감시 리포트 ({now})")
    lines.insert(1, "")
    body = "\n".join(lines)
    send_slack_message(body, title="QuantLabs 통합 감시", color="#2196F3")


if __name__ == "__main__":
    import time
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="1회만 실행 후 종료")
    args = parser.parse_args()
    if args.once:
        run_once()
    else:
        print("[QuantLabs] 1시간 주기 통합 감시. 종료: Ctrl+C")
        while True:
            try:
                run_once()
                time.sleep(3600)
            except KeyboardInterrupt:
                print("\n중지.")
                break
            except Exception as e:
                print(f"오류: {e}")
                time.sleep(3600)
