"""CSV 지식베이스 읽기.

DATA_DIR 폴더의 CSV 4개(menus, situations, synonyms, eval_questions)를 읽어 리스트(한 줄 = dict 하나)로 돌려준다.
- 인코딩: utf-8-sig(엑셀 "CSV UTF-8") 먼저, 실패하면 cp949(엑셀 기본 CSV)
- `|`로 나뉜 칸은 리스트로 바꾼다
실행: python -m guide.loader
"""
import csv
from pathlib import Path

from guide.settings import ROOT, cfg

# 파일 이름: (꼭 있어야 하는 열, `|`로 나눌 열)
FILES = {
    "menus": (
        ["menu_id", "menu_name", "path", "synonyms", "description", "owner_dept", "contact", "last_checked"],
        ["synonyms"],
    ),
    "situations": (
        ["situation_id", "situation_name", "trigger_words", "step_no", "step_title", "menu_id", "site", "owner_dept", "tip"],
        ["trigger_words"],
    ),
    "synonyms": (["word", "standard", "note"], []),
    "eval_questions": (["q_id", "q_type", "question", "answer_ids", "note"], ["answer_ids"]),
}


class DataError(Exception):
    """데이터 파일 문제를 한국어로 알려 주는 오류."""


def data_dir():
    path = Path(cfg.DATA_DIR)
    return path if path.is_absolute() else ROOT / path


def read_rows(path):
    """CSV를 dict 리스트로 읽는다. 인코딩을 두 가지로 시도한다."""
    for enc in ("utf-8-sig", "cp949"):
        try:
            with open(path, encoding=enc, newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                return (reader.fieldnames or []), rows
        except UnicodeDecodeError:
            continue
    raise DataError(f"{path.name}: 글자를 읽을 수 없습니다. 엑셀에서 'CSV UTF-8(쉼표로 분리)'로 다시 저장해 주세요.")


def split_cell(value):
    return [v.strip() for v in (value or "").split("|") if v.strip()]


def load_file(name):
    required, list_cols = FILES[name]
    path = data_dir() / f"{name}.csv"
    if not path.exists():
        raise DataError(f"데이터 파일이 없습니다: {path} (config의 DATA_DIR = '{cfg.DATA_DIR}')")
    header, rows = read_rows(path)
    header = [h.strip() for h in header if h]
    missing = [c for c in required if c not in header]
    if missing:
        raise DataError(f"{name}.csv: 열 이름이 없습니다 → {', '.join(missing)} (첫 줄 열 이름을 샘플과 똑같이 맞춰 주세요)")
    clean = []
    for row in rows:
        row = {(k or "").strip(): (v or "").strip() for k, v in row.items() if k}
        if not any(row.values()):
            continue  # 빈 줄 건너뛰기
        for col in list_cols:
            row[col] = split_cell(row.get(col))
        clean.append(row)
    return clean


_cache = {}


def load_all(reload=False):
    """모든 파일을 한 번 읽어 기억해 둔다. reload=True면 다시 읽는다."""
    if reload or not _cache:
        _cache.clear()
        for name in FILES:
            _cache[name] = load_file(name)
    return _cache


if __name__ == "__main__":
    data = load_all()
    short = {"eval_questions": "eval"}
    print(f"데이터 폴더: {data_dir()}  (설정 파일: {cfg.SOURCE_FILE})")
    print(" / ".join(f"{short.get(k, k)} {len(v)}" for k, v in data.items()))
