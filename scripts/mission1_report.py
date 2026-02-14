# -*- coding: utf-8 -*-
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.slack_notifier import send_completion_report
lines = [
    "미션 1호 비트코인 무한동력 시스템 완료",
    "Upbit 파이프라인 + VBS 백테스트 + 게이지 + monitor_vbs + 09시 리포트 준비",
]
ok = send_completion_report(lines)
sys.exit(0 if ok else 1)
