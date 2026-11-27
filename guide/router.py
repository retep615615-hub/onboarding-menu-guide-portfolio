"""판단 순서.

- 메인 큰 검색창(mode="main"): **규칙만**(상황 대시보드 → 메뉴). AI는 쓰지 않는다.
  못 찾으면 type="to_chat" → 화면이 오른쪽 아래 챗봇 창을 열어 같은 질문을 넘긴다.
- 챗봇 창(mode="chat", 명령 창·채점은 None과 같음): 규칙 → (못 찾으면) 사내 AI(엄격: 확실할 때만) → 모름.
  모름이면 type="unknown" + "이 질문은 제가 아직 잘 몰라요…" 문구.

answer(question, mode) 는 화면이 그대로 그릴 수 있는 dict를 돌려준다.
  type: "answer" | "to_chat" | "unknown",  source: "rule" | "ai"
  situations: 맞는 상황 대시보드(단계 + 메뉴 링크),  menus: 메뉴 검색 상위 결과
실행: python -m guide.router "손님 와"       (챗봇 창처럼)
      python -m guide.router --main "손님 와" (메인 검색창처럼)
"""
import sys

from guide import llm, loader
from guide.search import expand, menu_url, menus_by_id, norm, search
from guide.settings import get


def _has_any(q, words):
    return any(len(norm(w)) >= 2 and norm(w) in q for w in words)


def menu_card(menu, score=None):
    card = {
        "menu_id": menu["menu_id"],
        "menu_name": menu["menu_name"],
        "path": menu["path"],
        "description": menu["description"],
        "owner_dept": menu["owner_dept"],
        "contact": menu["contact"],
        "url": menu_url(menu["menu_id"]),
    }
    if score is not None:
        card["score"] = score
    return card


def all_situations(data=None, q=None):
    """상황 대시보드 전부(q가 있으면 trigger_words가 맞는 것만). 화면 메인 카드에 쓴다."""
    data = data or loader.load_all()
    by_id = menus_by_id(data)
    groups = {}
    for row in data["situations"]:
        groups.setdefault(row["situation_id"], []).append(row)
    found = []
    for sid, rows in groups.items():
        if q is not None:
            triggers = set()
            for r in rows:
                triggers.update(r["trigger_words"])
            if not _has_any(q, triggers):
                continue
        steps = []
        for r in rows:
            menu = by_id.get(r["menu_id"])
            steps.append({
                "step_no": int(r["step_no"]) if r["step_no"].isdigit() else 0,
                "title": r["step_title"],
                "site": r["site"] or "전체",
                "owner_dept": r["owner_dept"],
                "tip": r["tip"],
                "menu": menu_card(menu) if menu else None,
            })
        steps.sort(key=lambda s: s["step_no"])
        found.append({"situation_id": sid, "name": rows[0]["situation_name"], "steps": steps})
    return found


def match_situations(q, data=None):
    return all_situations(data, q)


def answer(question, mode=None, data=None):
    data = data or loader.load_all()
    question = (question or "").strip()
    result = {
        "question": question,
        "mode": mode,
        "type": "answer",
        "source": "rule",
        "message": "",
        "situations": [],
        "menus": [],
    }
    if not question:
        return result

    q = expand(question, data)
    if q:
        # ① 상황 대시보드  ② 메뉴
        result["situations"] = match_situations(q, data)
        result["menus"] = [menu_card(r["menu"], r["score"]) for r in search(question, data)]

    if result["situations"] or result["menus"]:
        result["message"] = "이렇게 찾았어요. 링크는 직접 눌러서 열어 주세요."
        return result

    # 메인 큰 검색창은 AI로 추론하지 않는다 → 챗봇 창으로 넘긴다
    if mode == "main":
        result["type"] = "to_chat"
        result["message"] = "챗봇에게 물어볼게요."
        return result

    # ③ 챗봇 창: 규칙으로 못 찾았을 때만 사내 AI(확실할 때만 답한다)
    ai, err = llm.call(question, data)
    if ai and ai["menu_ids"]:
        by_id = menus_by_id(data)
        result["source"] = "ai"
        result["menus"] = [dict(menu_card(by_id[i]), ai=True) for i in ai["menu_ids"]]
        result["message"] = ai["reply"] or "사내 AI가 메뉴 지도에서 골랐어요. 맞는지 확인하고 눌러 주세요."
        return result
    if err and get("LLM_ENABLED", False):
        result["llm_error"] = err

    # ④ 모름 → 답을 지어내지 않고 선배와 직접 이야기하도록 정중하게 권한다
    result["type"] = "unknown"
    result["message"] = get("UNKNOWN_MESSAGE", "이 질문은 제가 아직 잘 몰라요. 부서 선배님께 편하게 여쭤보는 건 어떨까요?")
    return result


if __name__ == "__main__":
    args = sys.argv[1:]
    mode = "chat"
    if args and args[0] == "--main":
        mode, args = "main", args[1:]
    question = " ".join(args) or input("질문: ")
    r = answer(question, mode)
    print(f'[{r["type"]}] {r["message"]}')
    for s in r["situations"]:
        print(f'  대시보드 "{s["name"]}" 단계 {len(s["steps"])}개:')
        for st in s["steps"]:
            print(f'    {st["step_no"]}. {st["title"]} [{st["site"]}] {st["owner_dept"]}')
    for m in r["menus"]:
        print(f'  메뉴 {m["menu_id"]} {m["menu_name"]}' + (" (🤖 사내 AI)" if m.get("ai") else f' (점수 {m["score"]})'))
    if r.get("llm_error"):
        print("  사내 AI:", r["llm_error"])
