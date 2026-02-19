# -*- coding: utf-8 -*-
"""
결과를 슬랙 웹훅으로 전송. UTF-8, ensure_ascii=False.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ENCODING = "utf-8"


def _ensure_env():
    """실행 시 .env 로드 (슬랙 테스트 등)."""
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except Exception:
        pass


def send_result_to_slack(message: str, title: str = "QuantLabs 자율 최적화") -> bool:
    """슬랙 웹훅으로 메시지 전송. 한글 깨짐 방지."""
    url = os.environ.get("SLACK_WEBHOOK_URL") or os.environ.get("SLACK_WEBHOOK", "")
    if not url:
        return False
    try:
        import requests
        payload = {"text": message, "attachments": [{"title": title, "color": "#36a64f"}]}
        body = json.dumps(payload, ensure_ascii=False)
        r = requests.post(url, data=body.encode(ENCODING), headers={"Content-Type": "application/json; charset=utf-8"}, timeout=10)
        return r.status_code == 200
    except Exception:
        return False


if __name__ == "__main__":
    _ensure_env()
    if getattr(sys.stdout, "reconfigure", None):
        try:
            sys.stdout.reconfigure(encoding=ENCODING)
        except Exception:
            pass
    msg = sys.argv[1] if len(sys.argv) > 1 else "테스트"
    ok = send_result_to_slack(msg)
    print("OK" if ok else "FAIL")
    sys.exit(0 if ok else 1)
