"""1층: 메뉴 지도 검색 (LLM 없음).

규칙:
1. 정리: 소문자, 띄어쓰기와 ?!.,~· 제거
2. 펼치기: 동의어 사전의 word가 있으면 standard를 질문 뒤에 덧붙임
3. 점수: 메뉴 이름 전체 +3 / 메뉴 동의어(2글자 이상) 하나당 +2 / 메뉴 이름 단어(2글자 이상, STOPWORDS 제외) 하나당 +1
4. MIN_SCORE 이상, 점수 높은 순 → menu_id 순, 최대 TOP_K개
실행: python -m guide.search "법카 어디서 신청해"
"""
import re
import sys

from guide import loader
from guide.settings import get

_CLEAN = re.compile(r"[\s?!.,~·]")


def norm(text):
    """띄어쓰기·문장부호를 없애고 소문자로. '차 쓰고' == '차쓰고'"""
    return _CLEAN.sub("", (text or "").lower())


def expand(question, data=None):
    """질문을 정리하고 동의어 사전으로 펼친다."""
    data = data or loader.load_all()
    q = norm(question)
    extra = []
    for row in data["synonyms"]:
        word = norm(row["word"])
        if len(word) >= 2 and word in q:
            extra.append(norm(row["standard"]))
    return q + "".join(extra)


def menu_url(menu_id):
    return get("MENU_URL_TEMPLATE", "{menu_id}").format(menu_id=menu_id)


def score_menu(menu, q, stopwords):
    score = 0
    if norm(menu["menu_name"]) in q:
        score += 3
    for word in menu["synonyms"]:
        w = norm(word)
        if len(w) >= 2 and w in q:
            score += 2
    for word in re.split(r"[\s·]+", menu["menu_name"]):
        w = norm(word)
        if len(w) >= 2 and w not in stopwords and w in q:
            score += 1
    return score


def search(question, data=None):
    """질문 → 상위 메뉴 [{menu, score, url}]"""
    data = data or loader.load_all()
    q = expand(question, data)
    if not q:
        return []
    stopwords = {norm(s) for s in get("STOPWORDS", [])}
    min_score = get("MIN_SCORE", 2)
    found = []
    for menu in data["menus"]:
        s = score_menu(menu, q, stopwords)
        if s >= min_score:
            found.append({"menu": menu, "score": s, "url": menu_url(menu["menu_id"])})
    found.sort(key=lambda r: (-r["score"], r["menu"]["menu_id"]))
    return found[: get("TOP_K", 3)]


def menus_by_id(data=None):
    data = data or loader.load_all()
    return {m["menu_id"]: m for m in data["menus"]}


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or input("질문: ")
    results = search(question)
    if not results:
        print("찾은 메뉴 없음")
    for r in results:
        m = r["menu"]
        print(f'{m["menu_id"]}  {m["menu_name"]}  (점수 {r["score"]})  {m["path"]}  → {r["url"]}')
