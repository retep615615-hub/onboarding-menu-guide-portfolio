"""질의응답 기록(익명). 이 챗봇을 쓰는 이유: 신입·인턴이 무엇을 가장 궁금해하는지 알고, 답이 틀린 곳을 고치기 위해.

- LOG_ENABLED=True일 때만 LOG_PATH(CSV)에 한 줄씩 붙인다.
- 남기는 것: 시각, 화면(main/chat), 일(질문/클릭), 질문, 답 종류, 찾은 방법(규칙/AI), 보여 준 메뉴 ID, 상황 대시보드, AI 한마디, AI 오류, 응답 시간.
- 남기지 않는 것: 사번, 이름, IP, 컴퓨터 이름, 세션·쿠키. 같은 사람의 질문을 이어 붙일 방법을 만들지 않는다.
- 질문에 실수로 들어간 개인정보처럼 보이는 것(긴 숫자, 전화번호, 메일 주소)은 저장 전에 가린다.
- LOG_KEEP_DAYS가 지난 줄은 길잡이를 켤 때 지운다.
"""
import csv
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path

from guide.settings import ROOT, get

FIELDS = ["time", "screen", "event", "question", "answer_type", "source",
          "menu_ids", "situations", "ai_reply", "llm_error", "ms"]
_LOCK = threading.Lock()

_MASKS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[메일]"),
    (re.compile(r"01[016789][-\s.]?\d{3,4}[-\s.]?\d{4}"), "[전화]"),
    (re.compile(r"\d{2,4}-\d{3,4}-\d{4}"), "[전화]"),
    (re.compile(r"\d{6,}"), "[숫자]"),  # 사번·주민번호 앞자리 같은 긴 숫자
]


def enabled():
    return bool(get("LOG_ENABLED", False))


def path():
    p = Path(get("LOG_PATH", "logs/questions.csv"))
    return p if p.is_absolute() else ROOT / p


def mask(text):
    text = (text or "").replace("\n", " ").strip()[:300]
    for pattern, repl in _MASKS:
        text = pattern.sub(repl, text)
    return text


def _append(row):
    if not enabled():
        return
    p = path()
    with _LOCK:
        p.parent.mkdir(parents=True, exist_ok=True)
        new = not p.exists() or p.stat().st_size == 0
        with p.open("a", encoding="utf-8-sig" if new else "utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            if new:
                w.writeheader()
            w.writerow({k: row.get(k, "") for k in FIELDS})


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log_answer(screen, result, ms):
    """질문 한 번 = 한 줄. result는 router.answer()가 돌려준 dict."""
    if not enabled() or not result.get("question"):
        return
    _append({
        "time": _now(),
        "screen": screen or "",
        "event": "질문",
        "question": mask(result["question"]),
        "answer_type": result.get("type", ""),
        "source": result.get("source", ""),
        "menu_ids": "|".join(m["menu_id"] for m in result.get("menus", [])),
        "situations": "|".join(s["name"] for s in result.get("situations", [])),
        "ai_reply": mask(result.get("message", "")) if result.get("source") == "ai" else "",
        "llm_error": result.get("llm_error", ""),
        "ms": int(ms),
    })


def log_click(screen, menu_id):
    """사람이 [열기]를 누른 메뉴 ID. 어떤 질문 뒤였는지는 잇지 않는다."""
    menu_id = re.sub(r"[^\w-]", "", menu_id or "")[:40]
    if not enabled() or not menu_id:
        return
    _append({"time": _now(), "screen": screen or "", "event": "클릭", "menu_ids": menu_id})


def prune():
    """보관 기간이 지난 줄을 지운다. 지운 줄 수를 돌려준다."""
    days = int(get("LOG_KEEP_DAYS", 0) or 0)
    p = path()
    if days <= 0 or not p.exists():
        return 0
    limit = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    with _LOCK:
        with p.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        keep = [r for r in rows if (r.get("time") or "") >= limit]
        if len(keep) == len(rows):
            return 0
        with p.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            for r in keep:
                w.writerow({k: r.get(k, "") for k in FIELDS})
    return len(rows) - len(keep)
