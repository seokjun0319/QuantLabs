# -*- coding: utf-8 -*-
"""
완료 보고를 슬랙으로 전송 (Cursor 완료 시 호출).
파일을 열거나 쓸 때는 무조건 encoding='utf-8' 명시. 슬랙 전송은 json.dumps(..., ensure_ascii=False) 사용.
"""
import sys
from pathlib import Path

# 파일 I/O 시 반드시 사용할 인코딩 (한글 깨짐 방지)
FILE_ENCODING = "utf-8"

# 입출력 인코딩 UTF-8 강제
def _force_utf8():
    for name in ("stdout", "stderr", "stdin"):
        stream = getattr(sys, name, None)
        if stream is not None and getattr(stream, "reconfigure", None):
            try:
                if stream.encoding and stream.encoding.lower() != "utf-8":
                    stream.reconfigure(encoding="utf-8")
            except Exception:
                pass
_force_utf8()

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.slack_notifier import send_completion_report

if __name__ == "__main__":
    lines = sys.argv[1:] if len(sys.argv) > 1 else ["- 완료"]
    # 인자 한글 깨짐 방지: bytes로 들어온 경우 UTF-8 디코딩
    decoded = []
    for s in lines:
        if isinstance(s, bytes):
            decoded.append(s.decode("utf-8", errors="replace"))
        else:
            decoded.append(s)
    ok = send_completion_report(decoded)
    print("Slack 전송:", "성공" if ok else "실패")
    sys.exit(0 if ok else 1)
