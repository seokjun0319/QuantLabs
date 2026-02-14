"""
QuantLabs - Slack 알림 모듈
에러 발생 시 대장님 슬랙으로 무조건 전송. 멈추면 죽음이다.
한글 깨짐 방지: 모든 JSON 직렬화는 ensure_ascii=False 필수. 요청 본문 UTF-8.
"""
import json
import os

# 슬랙 전송 시 한글이 유니코드 이스케이프 되지 않도록 고정
JSON_DUMPS_KWARGS = {"ensure_ascii": False}
SLACK_HEADERS = {"Content-Type": "application/json; charset=utf-8"}
import traceback
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")


def send_slack_message(
    text: str,
    title: Optional[str] = None,
    color: Optional[str] = None,
) -> bool:
    """
    Slack Webhook으로 메시지 전송.
    Returns: 전송 성공 여부
    """
    if not SLACK_WEBHOOK_URL:
        return False
    try:
        payload = {
            "text": text,
            "attachments": []
        }
        if title or color:
            att = {"title": title or "QuantLabs", "color": color or "#36a64f"}
            payload["attachments"].append(att)
        # 한글이 절대로 깨지지 않도록 ensure_ascii=False 필수
        body = json.dumps(payload, ensure_ascii=False)
        resp = requests.post(
            SLACK_WEBHOOK_URL,
            data=body.encode("utf-8"),
            headers=SLACK_HEADERS,
            timeout=10,
        )
        return resp.status_code == 200
    except Exception:
        # Slack 실패 시 로그만 남기고 앱은 멈추지 않음
        traceback.print_exc()
        return False


def send_error_to_slack(
    error: Exception,
    context: Optional[str] = None,
) -> bool:
    """
    예외를 슬랙으로 전송. try-except에서 호출.
    """
    tb = traceback.format_exc()
    title = "QuantLabs 에러"
    body = f"*Context:* {context or 'N/A'}\n*Error:* `{type(error).__name__}: {str(error)}`\n```\n{tb}\n```"
    return send_slack_message(body, title=title, color="#ff0000")


def send_completion_report(summary_lines: list[str]) -> bool:
    """
    완료 보고를 대장님 슬랙으로 전송.
    summary_lines: 변경 사항 요약 리스트 (예: ["- 비트코인 탭 수정", "- API 연동 추가"])
    """
    from datetime import datetime
    header = f"[Cursor 완료 보고: {datetime.now().strftime('%Y-%m-%d %H:%M')}]"
    body = header + "\n" + "\n".join(summary_lines)
    return send_slack_message(body, title="QuantLabs 완료 보고", color="#36a64f")


def send_daily_report_09am(content: str) -> bool:
    """
    09시 리포트를 대장님 슬랙으로 전송.
    content: 리포트 본문.
    """
    return send_slack_message(content, title="QuantLabs 09시 리포트", color="#2196F3")
