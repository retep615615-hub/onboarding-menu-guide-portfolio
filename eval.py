"""정답셋 채점: 기존 메뉴 검색(흉내) vs 길잡이.

- 기존 검색 흉내: 질문을 띄어쓰기로 나눈 단어(2글자 이상) 중 하나라도 메뉴 이름에 들어 있으면 그 메뉴를 찾은 것으로 본다.
  범위 밖 질문(길잡이가 모르는 것)은 안내를 못 하므로 항상 실패.
- 길잡이: router.answer 결과. unknown(선배에게 여쭤보기 제안) → UNKNOWN, 그 밖에는 메뉴 상위 결과 + 상황 단계의 메뉴들.
- 성공: 정답 ID 중 하나라도 결과에 있으면.
실행: python eval.py
주의: 실제 포털 검색창과 똑같지 않다. 실제 성능은 실제 포털 검색으로 직접 잰 값과 함께 본다.
"""
import time

from guide import loader
from guide.router import answer
from guide.search import norm
from guide.settings import get

ORDER = ["일상어", "메뉴이름", "범위밖"]


def baseline(question, menus):
    words = [norm(w) for w in question.split()]
    words = [w for w in words if len(w) >= 2]
    return {m["menu_id"] for m in menus if any(w in norm(m["menu_name"]) for w in words)}


def guide_ids(result):
    if result["type"] == "unknown":
        return {"UNKNOWN"}
    ids = {m["menu_id"] for m in result["menus"]}
    for s in result["situations"]:
        ids.update(st["menu"]["menu_id"] for st in s["steps"] if st["menu"])
    return ids


def main():
    data = loader.load_all()
    stats, fails = {}, []
    for row in data["eval_questions"]:
        q, kind, ans = row["question"], row["q_type"], set(row["answer_ids"])
        t0 = time.perf_counter()
        g = guide_ids(answer(q, data=data))
        ms = (time.perf_counter() - t0) * 1000
        b = set() if kind == "범위밖" else baseline(q, data["menus"])
        g_ok, b_ok = bool(ans & g), bool(ans & b)
        s = stats.setdefault(kind, {"n": 0, "g": 0, "b": 0, "ms": 0.0})
        s["n"] += 1
        s["g"] += g_ok
        s["b"] += b_ok
        s["ms"] += ms
        if not g_ok:
            fails.append(f'  {row["q_id"]} "{q}" → 정답 {"|".join(sorted(ans))}, 길잡이 {"|".join(sorted(g)) or "없음"}')

    print(f"데이터: {loader.data_dir()}")
    print(f"사내 AI: {'켬 (규칙으로 못 찾은 질문만 AI가 도움)' if get('LLM_ENABLED', False) else '끔 (규칙만)'}")
    print(f'{"질문 종류":<8} {"개수":>4}  {"기존 검색(흉내)":>14}  {"길잡이":>8}  {"길잡이 평균 응답":>14}')
    total = {"n": 0, "g": 0, "b": 0}
    for kind in ORDER + [k for k in stats if k not in ORDER]:
        if kind not in stats:
            continue
        s = stats[kind]
        for k in total:
            total[k] += s[k]
        print(f'{kind:<8} {s["n"]:>4}  {s["b"]:>9}/{s["n"]:<4}  {s["g"]:>4}/{s["n"]:<3}  {s["ms"] / s["n"]:>11.1f} ms')
    print(f'{"합계":<8} {total["n"]:>4}  {total["b"]:>9}/{total["n"]:<4}  {total["g"]:>4}/{total["n"]:<3}')
    print("\n길잡이가 틀린 질문:" if fails else "\n길잡이가 틀린 질문: 없음")
    for line in fails:
        print(line)


if __name__ == "__main__":
    main()
