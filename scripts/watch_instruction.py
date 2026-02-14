"""
QuantLabs 지시서 감시 스크립트 (5분마다 체크)
- quantlabs_instruction.md를 5분마다 읽음.
- 마지막 [Cursor 완료 보고] 이후에 젬민이(PM)가 신규 지시를 추가했으면
  .cursor/quantlabs_pending_check.txt 를 생성해 Cursor가 다음 세션에서 자동 처리하도록 함.
- 대장님이 "멈춰" 할 때까지 무한 반복. (Ctrl+C로 종료)

실행: 프로젝트 루트에서
  py -m scripts.watch_instruction
  또는
  python scripts/watch_instruction.py
"""
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTRUCTION_FILE = ROOT / "quantlabs_instruction.md"
TRIGGER_FILE = ROOT / ".cursor" / "quantlabs_pending_check.txt"
INTERVAL_SEC = 60  # 1분


def get_last_report_line(content: str) -> int:
    """마지막 '[Cursor 완료 보고' 가 나오는 줄 번호 (1-based). 없으면 0."""
    last_line = 0
    for i, line in enumerate(content.splitlines(), start=1):
        if "[Cursor 완료 보고" in line:
            last_line = i
    return last_line


def get_instruction_section(content: str) -> tuple[int, str]:
    """'신규/수정 지시' 섹션 시작 줄 번호와 그 다음 --- 전까지 내용. (1-based line, body)."""
    lines = content.splitlines()
    start = 0
    for i, line in enumerate(lines, start=1):
        if "신규/수정 지시" in line and "PM" in line:
            start = i
            break
    if start == 0:
        return 0, ""
    body_lines = []
    for i in range(start, len(lines)):
        if i < len(lines) and lines[i].strip().startswith("---"):
            break
        body_lines.append(lines[i])
    return start, "\n".join(body_lines).strip()


def has_new_instruction(content: str) -> bool:
    """마지막 완료 보고 이후에 실제 지시 내용이 있으면 True."""
    last_report = get_last_report_line(content)
    inst_line, inst_body = get_instruction_section(content)
    if last_report == 0 or inst_line == 0:
        return False
    # 지시 섹션이 완료 보고보다 위에 있으면 이미 처리된 것
    if inst_line < last_report:
        return False
    # 플레이스홀더만 있으면 무시
    placeholder = "(새 기획이나 수정 요청이 생기면 이 섹션에 추가"
    if inst_body.strip() == "" or (placeholder in inst_body and len(inst_body.strip()) < 150):
        return False
    # 실제 지시 문장이 있는지 (bullet 또는 일반 문장)
    lines = [l.strip() for l in inst_body.splitlines() if l.strip() and not l.strip().startswith("---")]
    for line in lines:
        if "Cursor" in line and "완료 보고" in line:
            continue
        if len(line) > 3 and placeholder not in line:
            return True
    return False


def main():
    ROOT.joinpath(".cursor").mkdir(parents=True, exist_ok=True)
    print(f"[QuantLabs Watcher] 1분마다 {INSTRUCTION_FILE.name} 체크. 종료: Ctrl+C")
    while True:
        try:
            if not INSTRUCTION_FILE.exists():
                time.sleep(INTERVAL_SEC)
                continue
            text = INSTRUCTION_FILE.read_text(encoding="utf-8")
            if has_new_instruction(text):
                TRIGGER_FILE.write_text(f"pending\n{time.strftime('%Y-%m-%d %H:%M:%S')}", encoding="utf-8")
                print(f"[{time.strftime('%H:%M:%S')}] 신규 지시 감지 → Cursor 트리거 생성. (Cursor 열면 자동 처리)")
            time.sleep(INTERVAL_SEC)
        except KeyboardInterrupt:
            print("\n[QuantLabs Watcher] 대장님 명령으로 중지.")
            break
        except Exception as e:
            print(f"[QuantLabs Watcher] 오류: {e}")
            time.sleep(INTERVAL_SEC)


if __name__ == "__main__":
    main()
