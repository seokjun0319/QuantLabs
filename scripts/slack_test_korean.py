# -*- coding: utf-8 -*-
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.slack_notifier import send_completion_report
ok = send_completion_report(["자동화 테스트 중", "슬랙 한글 리포트 전송 확인"])
sys.exit(0 if ok else 1)
