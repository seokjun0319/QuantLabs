# -*- coding: utf-8 -*-
"""NVDA 최적화 모형 완료 슬랙 보고."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.slack_notifier import send_slack_message
msg = "대장님, NVDA 최적화 모형 개발을 완료했습니다. 이제부터 실시간 감시에 들어갑니다."
ok = send_slack_message(msg, title="QuantLabs NVDA Alpha-V1 완료", color="#76b900")
sys.exit(0 if ok else 1)
