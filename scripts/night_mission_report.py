# -*- coding: utf-8 -*-
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.slack_notifier import send_completion_report
lines = [
    "야간 특명 완료: 1시간 통합 감시 + 엔비디아 분석",
    "hourly_monitor.py (BTC+VBS, NVDA 이격도, 인사이트, 한글 이모지 슬랙)",
    "미장 직투 탭 NVDA 섹션 (5일 거래량, RSI, 지지/저항)",
    "1분 지시서 감시 + 1시간 시장 감시 병행 실행 안내 반영",
]
ok = send_completion_report(lines)
sys.exit(0 if ok else 1)
