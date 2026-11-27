"""데이터 검사기: 실제 데이터를 넣은 뒤 실행 전에 돌린다.

실행: python check_data.py            (설정의 DATA_DIR 폴더 검사)
      python check_data.py 폴더경로   (다른 폴더 검사)
문제마다 "파일명 몇째 줄: 무엇이 문제"를 한 줄씩 보여 준다. (줄 번호 = 엑셀의 행 번호)
"""
import sys
from datetime import date, datetime
from pathlib import Path

from guide import loader
from guide.settings import get

STALE_DAYS = 90
SPECIAL_ANSWERS = {"UNKNOWN"}


def parse_date(text):
    """엑셀이 바꿔 저장한 날짜 모양(2026/11/24, 2026.11.24)도 받아 준다."""
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y. %m. %d"):
        try:
            return datetime.strptime(text.strip().rstrip("."), fmt).date()
        except ValueError:
            continue
    return None


def check(folder):
    problems = []
    rows = {}

    def add(fname, line, msg):
        problems.append(f"{fname}.csv {line}째 줄: {msg}" if line else f"{fname}.csv: {msg}")

    # 1) 파일과 열 이름
    for name, (required, _) in loader.FILES.items():
        path = folder / f"{name}.csv"
        if not path.exists():
            add(name, None, "파일이 없습니다")
            continue
        try:
            header, data = loader.read_rows(path)
        except loader.DataError as e:
            problems.append(str(e))
            continue
        header = [h.strip() for h in header if h]
        missing = [c for c in required if c not in header]
        if missing:
            add(name, 1, "열 이름이 없습니다 → " + ", ".join(missing))
            continue
        rows[name] = [{(k or "").strip(): (v or "").strip() for k, v in r.items() if k} for r in data]

    def each(name):
        for i, r in enumerate(rows.get(name, [])):
            if any(r.values()):
                yield i + 2, r  # 1째 줄은 열 이름

    # 2) 메뉴 지도
    ids = {}
    today = date.today()
    for line, r in each("menus"):
        mid = r["menu_id"]
        if not mid:
            add("menus", line, "menu_id가 비어 있습니다")
        elif "E+" in mid.upper() or mid.endswith(".0"):
            add("menus", line, f"menu_id '{mid}'를 엑셀이 숫자로 바꿨습니다. menu_id 열을 '텍스트' 형식으로 바꾸고 원래 ID를 다시 넣어 주세요")
        elif mid in ids:
            add("menus", line, f"menu_id '{mid}'가 {ids[mid]}째 줄과 겹칩니다")
        else:
            ids[mid] = line
        if not r["menu_name"]:
            add("menus", line, "menu_name이 비어 있습니다")
        for w in loader.split_cell(r["synonyms"]):
            if len(w.replace(" ", "")) < 2:
                add("menus", line, f"동의어 '{w}'는 한 글자라 너무 많이 걸립니다")
        if r["last_checked"]:
            checked = parse_date(r["last_checked"])
            if checked is None:
                add("menus", line, f"last_checked '{r['last_checked']}'는 날짜 형식이 아닙니다(예: 2026-11-24)")
            elif (today - checked).days > STALE_DAYS:
                add("menus", line, f"링크를 확인한 지 {STALE_DAYS}일이 넘었습니다({r['last_checked']})")

    def check_ref(name, line, mid):
        if mid and ids and mid not in ids:
            add(name, line, f"menu_id '{mid}'가 menus.csv에 없습니다")

    # 3) 상황 체크리스트
    for line, r in each("situations"):
        check_ref("situations", line, r["menu_id"])
        if not r["step_no"].isdigit():
            add("situations", line, f"step_no '{r['step_no']}'는 숫자여야 합니다")
        for w in loader.split_cell(r["trigger_words"]):
            if len(w.replace(" ", "")) < 2:
                add("situations", line, f"trigger_words '{w}'는 한 글자입니다")

    # 5) 동의어 사전
    for line, r in each("synonyms"):
        if len(r["word"].replace(" ", "")) < 2 or not r["standard"]:
            add("synonyms", line, "word는 두 글자 이상, standard는 비울 수 없습니다")

    # 6) 정답셋
    for line, r in each("eval_questions"):
        if not r["question"]:
            add("eval_questions", line, "question이 비어 있습니다")
        for mid in loader.split_cell(r["answer_ids"]):
            if mid not in SPECIAL_ANSWERS:
                check_ref("eval_questions", line, mid)

    # 7) 설정
    if "{menu_id}" not in get("MENU_URL_TEMPLATE", ""):
        problems.append("config: MENU_URL_TEMPLATE에 {menu_id} 자리가 없습니다")

    return problems


def main():
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else loader.data_dir()
    print(f"검사 폴더: {folder}")
    problems = check(folder)
    if problems:
        print(f"문제 {len(problems)}개:")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print("문제 없음")


if __name__ == "__main__":
    main()
