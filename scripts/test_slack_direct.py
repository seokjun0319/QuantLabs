"""
QuantLabs 슬랙 통신 직접 테스트 (일회성)
- 대장님 슬랙에 "딩동" 메시지 전송.
- 성공 시 .env 에 SLACK_WEBHOOK_URL 설정 후 동일 방식으로 완료 보고/09시 리포트 사용.
"""
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("requests 미설치. pip install requests 후 재실행.")
    sys.exit(1)

# .env 의 SLACK_WEBHOOK_URL 사용 (민감정보 절대 하드코딩 금지)
import os
WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
MESSAGE = "대장님, 노예가 직접 보고드립니다. 통신 성공!"


def main():
    if not WEBHOOK_URL:
        print(".env 에 SLACK_WEBHOOK_URL 을 설정한 뒤 다시 실행하세요.")
        return 1
    payload = {
        "text": MESSAGE,
        "attachments": [{"color": "#36a64f", "title": "QuantLabs 슬랙 통신 테스트"}],
    }
    try:
        r = requests.post(WEBHOOK_URL, json=payload, timeout=10)
        if r.status_code == 200:
            print("[OK] 슬랙 전송 성공. 대장님 채널에서 메시지를 확인하세요.")
            return 0
        print(f"[FAIL] HTTP {r.status_code}: {r.text}")
        return 1
    except Exception as e:
        print(f"[ERROR] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
