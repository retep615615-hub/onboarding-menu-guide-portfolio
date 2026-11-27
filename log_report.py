"""질의응답 기록 요약(관리자용). 기록 파일을 열지 않고도 무엇을 고칠지 보이게 한다.

실행: python log_report.py            → 전체 기간
      python log_report.py 7          → 최근 7일
보여 주는 것
  1) 한눈에: 질문 수, 규칙으로 찾음 / 사내 AI가 도움 / 못 찾음 비율, 평균 응답 시간
  2) 고칠 것: 못 찾은 질문(→ 동의어·메뉴 추가 후보), 사내 AI가 답한 질문(→ 맞는지 확인 후 규칙으로 옮기기), AI 오류
  3) 많이 묻는 것: 메뉴·상황·누른 메뉴. 개인이 드러나지 않게 LOG_MIN_GROUP(기본 5)번 이상인 것만
"""
import csv
import sys
from collections import Counter
from datetime import datetime, timedelta

from guide import loader, qlog
from guide.search import menus_by_id
from guide.settings import get


def main():
    p = qlog.path()
    if not p.exists():
        print(f"기록 파일이 아직 없습니다: {p}")
        print("LOG_ENABLED = True 인지, 길잡이에서 질문을 해 봤는지 확인하세요.")
        return
    with p.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        since = (datetime.now() - timedelta(days=int(sys.argv[1]))).strftime("%Y-%m-%d %H:%M:%S")
        rows = [r for r in rows if r["time"] >= since]
    asks = [r for r in rows if r["event"] == "질문"]
    clicks = [r for r in rows if r["event"] == "클릭"]
    if not asks:
        print("이 기간에 질문 기록이 없습니다.")
        return

    try:
        names = {k: v["menu_name"] for k, v in menus_by_id(loader.load_all()).items()}
    except loader.DataError:
        names = {}
    k = int(get("LOG_MIN_GROUP", 5))
    n = len(asks)
    rule = [r for r in asks if r["answer_type"] == "answer" and r["source"] != "ai"]
    ai = [r for r in asks if r["source"] == "ai"]
    unknown = [r for r in asks if r["answer_type"] == "unknown"]
    to_chat = [r for r in asks if r["answer_type"] == "to_chat"]
    errors = [r for r in asks if r["llm_error"]]

    def pct(x):
        return f"{len(x)}건 ({len(x) * 100 / n:.0f}%)"

    def avg_ms(x):
        ms = [int(r["ms"]) for r in x if r["ms"].isdigit()]
        return f"{sum(ms) / len(ms) / 1000:.2f}초" if ms else "-"

    print(f"기록: {p}")
    print(f"기간: {asks[0]['time'][:10]} ~ {asks[-1]['time'][:10]} · 질문 {n}건 (메인 {sum(r['screen'] == 'main' for r in asks)} / 챗봇 창 {sum(r['screen'] == 'chat' for r in asks)}) · 클릭 {len(clicks)}건")
    print("\n[1] 한눈에")
    print(f"  규칙으로 찾음   {pct(rule)}  평균 {avg_ms(rule)}")
    print(f"  사내 AI가 도움  {pct(ai)}  평균 {avg_ms(ai)}")
    print(f"  메인→챗봇 넘김  {pct(to_chat)}  → 메인 검색창(규칙)이 못 찾아 챗봇 창으로 넘긴 질문")
    print(f"  못 찾음        {pct(unknown)}  → 챗봇이 답을 거절하고 선배에게 여쭤보기 문구가 나간 질문")

    print("\n[2] 고칠 것")
    print("  ▶ 못 찾은 질문 (많은 순) → 이 말을 synonyms.csv나 메뉴 동의어에 더하거나, 빠진 메뉴를 지도에 넣는다")
    for q, c in Counter(r["question"] for r in unknown).most_common(20):
        print(f"    {c}회  {q}")
    if not unknown:
        print("    없음")
    print("  ▶ 사내 AI가 답한 질문 → AI가 고른 메뉴가 맞으면 그 말을 동의어로 더해 규칙으로 옮긴다(더 빠르고 늘 같은 답)")
    for (q, ids), c in Counter((r["question"], r["menu_ids"]) for r in ai).most_common(20):
        shown = ", ".join(f"{i} {names.get(i, '')}".strip() for i in ids.split("|") if i)
        print(f"    {c}회  {q}  →  {shown}")
    if not ai:
        print("    없음")
    print(f"  ▶ 사내 AI 오류 {len(errors)}건")
    for e, c in Counter(r["llm_error"] for r in errors).most_common(5):
        print(f"    {c}회  {e}")

    print(f"\n[3] 많이 묻는 것 ({k}번 이상만 — 개인이 드러나지 않게)")
    menu_c = Counter(i for r in asks for i in r["menu_ids"].split("|") if i)
    sit_c = Counter(s for r in asks for s in r["situations"].split("|") if s)
    click_c = Counter(r["menu_ids"] for r in clicks if r["menu_ids"])
    for title, counter in (("보여 준 메뉴", menu_c), ("상황 대시보드", sit_c), ("[열기]를 누른 메뉴", click_c)):
        items = [(x, c) for x, c in counter.most_common(10) if c >= k]
        print(f"  ▶ {title}")
        for x, c in items:
            print(f"    {c}회  {x} {names.get(x, '')}".rstrip())
        if not items:
            print(f"    아직 {k}번 넘은 것이 없음")


if __name__ == "__main__":
    main()
