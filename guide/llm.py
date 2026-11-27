"""3층: 사내 AI(OpenAI 호환 API)로 메뉴 고르기. 챗봇 창에서 규칙으로 못 찾았을 때만 부른다(메인 검색창은 AI를 쓰지 않는다).

- 파이썬 표준 라이브러리(urllib)만 쓴다.
- AI에게는 질문과 '메뉴 지도 목록'을 주고, 그 목록 안에서만 고르게 한다(없는 메뉴를 지어내지 못하게).
- 엄격하게: AI가 sure=true라고 한 경우만 쓴다. 메뉴와 상관없는 질문·애매한 질문은 거절 → 선배에게 여쭤보기 문구.
- AI가 고른 ID는 지도에 실제로 있는지 다시 확인한다. 없으면 버린다.
- 꺼져 있거나, 주소가 틀렸거나, 시간이 초과되면 조용히 None → 화면은 "선배에게 여쭤보기" 문구를 보여 준다.
- 키는 config에 쓰지 않는다. 환경 변수 LLM_API_KEY 또는 저장소 맨 위의 .env 파일에서 읽는다.

연결 시험(실행 PC): python -m guide.llm "연차 쓰려면 어디로 가?"
"""
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request

from guide import loader
from guide.search import menus_by_id
from guide.settings import ROOT, get

SYSTEM_PROMPT = (
    "너는 사내 포털 '메뉴 길잡이'다. 직원의 질문을 읽고, 아래 [메뉴 목록]에서 질문에 맞는 메뉴를 최대 {top_k}개 고른다.\n"
    "엄격한 규칙(어기면 안 된다):\n"
    "1. 너의 일은 '어느 메뉴로 가면 되는지' 고르는 것 하나뿐이다. [메뉴 목록]에 있는 menu_id만 쓴다.\n"
    "2. 목록에 없는 메뉴·주소·규정·절차·날짜·금액·숫자는 절대 지어내지 않는다. 규정 해석이나 조언도 하지 않는다.\n"
    "3. 메뉴 안내와 관계없는 질문(잡담, 주식·뉴스, 개인 고민 상담, 사람 평가, 회사 기밀 등)은 거절한다: menu_ids는 빈 목록, sure는 false.\n"
    "4. 질문과 메뉴가 분명히 맞을 때만 sure를 true로 한다. 조금이라도 애매하면 menu_ids는 빈 목록, sure는 false.\n"
    "5. reply는 한국어 존댓말 한 문장. 왜 이 메뉴인지 짧게. 신청을 대신 해 주겠다는 말은 하지 않는다.\n"
    "6. 사번·이름 같은 개인정보를 묻지 않는다.\n"
    "7. 출력은 JSON 하나만: {{\"menu_ids\": [\"...\"], \"sure\": true, \"reply\": \"...\"}}"
)


def _api_key():
    key = os.environ.get("LLM_API_KEY", "").strip()
    if key:
        return key
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
            line = line.strip()
            if line.startswith("LLM_API_KEY") and "=" in line:
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _menu_lines(data):
    lines = []
    for m in data["menus"][: int(get("LLM_MAX_MENUS", 400))]:
        syn = ", ".join(m["synonyms"][:6]) if isinstance(m["synonyms"], list) else m["synonyms"]
        lines.append(f'{m["menu_id"]} | {m["menu_name"]} | {m["path"]} | {syn} | {m["description"]}')
    return "\n".join(lines)


_last_text = ""  # 마지막 AI 답 원문. 연결 시험(python -m guide.llm)에서만 앞부분을 보여 준다. 기록에는 남기지 않는다


def _content_text(message):
    """message.content가 글자일 수도, 조각 목록일 수도 있다. 생각 과정(reasoning)만 있고 content가 비면 그것도 본다."""
    content = message.get("content")
    if isinstance(content, list):
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
    content = content or ""
    if not content.strip():
        content = message.get("reasoning_content") or message.get("reasoning") or ""
    return content


def _find_json(text):
    """AI 답에서 JSON 하나를 꺼낸다. 생각 과정(<think>…</think>), ```json 코드 블록```, 앞뒤 설명 글을 견딘다."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S | re.I)
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidates = [fence.group(1)] if fence else []
    # menu_ids가 들어 있는 { … } 를 뒤에서부터 찾는다(설명 글 속 중괄호를 피하려고)
    for m in reversed(list(re.finditer(r"\{[^{}]*\}", text, re.S))):
        if "menu_ids" in m.group(0):
            candidates.append(m.group(0))
    greedy = re.search(r"\{.*\}", text, re.S)
    if greedy:
        candidates.append(greedy.group(0))
    for c in candidates:
        try:
            obj = json.loads(c)
            if isinstance(obj, dict):
                return obj
        except ValueError:
            continue
    return None


def _opener():
    handlers = []
    if not get("LLM_USE_SYSTEM_PROXY", True):
        handlers.append(urllib.request.ProxyHandler({}))
    if not get("LLM_SSL_VERIFY", True):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        handlers.append(urllib.request.HTTPSHandler(context=ctx))
    return urllib.request.build_opener(*handlers)


def call(question, data=None):
    """(결과, 오류 문구)를 돌려준다. 결과 = {"menu_ids": [...], "reply": "..."} 또는 None."""
    if not get("LLM_ENABLED", False):
        return None, "LLM_ENABLED가 False입니다(꺼짐)."
    question = (question or "").strip()
    if not question:
        return None, "질문이 비었습니다."
    data = data or loader.load_all()
    top_k = int(get("TOP_K", 3))
    body = {
        "model": get("LLM_MODEL", ""),
        "temperature": 0,
        "max_tokens": int(get("LLM_MAX_TOKENS", 1000)),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT.format(top_k=top_k)},
            {"role": "user", "content": f"[메뉴 목록]\n{_menu_lines(data)}\n\n[질문]\n{question}"},
        ],
    }
    if get("LLM_JSON_MODE", False):
        body["response_format"] = {"type": "json_object"}
    url = str(get("LLM_BASE_URL", "")).rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    key = _api_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    try:
        with _opener().open(req, timeout=float(get("LLM_TIMEOUT", 20))) as res:
            raw = json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        hint = {401: "키가 틀렸거나 없습니다(.env의 LLM_API_KEY)", 403: "권한이 없습니다", 404: "주소가 틀렸습니다(LLM_BASE_URL, …/v1까지인지)"}.get(e.code, "")
        return None, f"사내 AI가 오류 {e.code}를 돌려줬습니다. {hint}".strip()
    except urllib.error.URLError as e:
        return None, f"사내 AI 주소에 연결할 수 없습니다({type(e.reason).__name__}). 주소·프록시(LLM_USE_SYSTEM_PROXY)·인증서(LLM_SSL_VERIFY)를 확인하세요."
    except TimeoutError:
        return None, f"사내 AI가 {get('LLM_TIMEOUT', 20)}초 안에 답하지 않았습니다(LLM_TIMEOUT)."
    except (ValueError, OSError) as e:
        return None, f"사내 AI 응답을 읽지 못했습니다({type(e).__name__})."

    global _last_text
    try:
        choice = raw["choices"][0]
        text = _content_text(choice["message"])
    except (KeyError, IndexError, TypeError, AttributeError):
        return None, "응답 모양이 OpenAI 호환 형식(choices[0].message.content)이 아닙니다."
    _last_text = text
    parsed = _find_json(text)
    if parsed is None:
        if choice.get("finish_reason") == "length":
            return None, f"AI 답이 길이 제한에서 잘렸습니다. config.py의 LLM_MAX_TOKENS(지금 {get('LLM_MAX_TOKENS', 1000)})를 늘려 보세요."
        if not text.strip():
            return None, "AI 답이 비어 있습니다. LLM_MODEL 이름이 맞는지 확인하세요."
        return None, "AI 답에서 JSON을 찾지 못했습니다. config.py에서 LLM_JSON_MODE = True로 바꿔 다시 시험해 보세요."
    if parsed.get("sure") is not True:  # 확실하다고 하지 않으면 답하지 않는다(엄격)
        return {"menu_ids": [], "reply": ""}, None
    known = menus_by_id(data)
    ids = []
    for mid in parsed.get("menu_ids") or []:
        mid = str(mid).strip()
        if mid in known and mid not in ids:  # 지도에 있는 ID만 믿는다
            ids.append(mid)
    reply = str(parsed.get("reply") or "").strip()[:200]
    return {"menu_ids": ids[:top_k], "reply": reply}, None


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or input("질문: ")
    result, err = call(q)
    if err:
        print("❌", err)
        if _last_text:
            print("  (AI 답 앞부분 — 화면에만 보이고 기록되지 않습니다. 회사 정보가 있으면 일반 말로 바꿔 전하세요)")
            print("  " + _last_text.strip().replace("\n", " ")[:300])
        sys.exit(1)
    print("✅ 사내 AI 연결 성공")
    print("  고른 메뉴:", ", ".join(result["menu_ids"]) or "(없음 → 선배에게 여쭤보기 문구)")
    print("  한마디:", result["reply"])
