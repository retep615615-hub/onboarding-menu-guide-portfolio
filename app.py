"""HR 메뉴 길잡이 실행 파일 (파이썬 표준 라이브러리만). 메인 = 상황 대시보드 + 규칙 검색창, 오른쪽 아래 = AI 챗봇 창.

실행: python app.py  → 브라우저에서 http://127.0.0.1:8000
끄기: 명령 창에서 Ctrl + C
데이터(CSV)를 고쳤으면 껐다가 다시 켠다.
"""
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from guide import loader, qlog
from guide.router import all_situations, answer
from guide.settings import ROOT, cfg, get

INDEX = ROOT / "static" / "index.html"


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, body, content_type):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, status=200):
        self._send(status, json.dumps(obj, ensure_ascii=False), "application/json; charset=utf-8")

    def do_GET(self):
        url = urlparse(self.path)
        params = parse_qs(url.query)
        try:
            if url.path in ("/", "/index.html"):
                self._send(200, INDEX.read_bytes(), "text/html; charset=utf-8")
            elif url.path == "/api/ask":
                q = params.get("q", [""])[0]
                mode = params.get("mode", [None])[0]
                t0 = time.perf_counter()
                result = answer(q, mode)
                qlog.log_answer("main" if mode == "main" else "chat", result, (time.perf_counter() - t0) * 1000)
                self._json(result)
            elif url.path == "/api/click":
                qlog.log_click(params.get("screen", [""])[0], params.get("menu_id", [""])[0])
                self._json({"ok": True})
            elif url.path == "/api/dashboards":
                self._json({"situations": all_situations()})
            elif url.path == "/api/status":
                self._json({
                    "llm": "켬" if get("LLM_ENABLED", False) else "끔",
                    "log": "켬" if get("LOG_ENABLED", False) else "끔",
                    "data_dir": str(cfg.DATA_DIR),
                    "config": cfg.SOURCE_FILE,
                    "examples": get("EXAMPLE_QUESTIONS", []),
                    "app_title": get("APP_TITLE", "온보딩 메뉴 길잡이"),
                    "app_subtitle": get("APP_SUBTITLE", ""),
                    "chat_title": get("CHAT_TITLE", "메뉴 길잡이 챗봇"),
                    "chat_examples": get("CHAT_EXAMPLES", []),
                    "log_notice": get("LOG_NOTICE", "") if get("LOG_ENABLED", False) else "",
                    "log_notice_detail": get("LOG_NOTICE_DETAIL", "") if get("LOG_ENABLED", False) else "",
                })
            else:
                self._json({"error": "없는 주소입니다"}, 404)
        except loader.DataError as e:
            self._json({"error": str(e)}, 500)
        except Exception as e:  # 화면이 멈추지 않게 오류를 글로 돌려준다
            self._json({"error": f"{type(e).__name__}: {e}"}, 500)

    def log_message(self, fmt, *args):
        # 질문 내용이 명령 창에 남지 않게 주소만 짧게 찍는다
        sys.stderr.write(f"{self.command} {urlparse(self.path).path} {args[1] if len(args) > 1 else ''}\n")


def main():
    try:
        data = loader.load_all()
    except loader.DataError as e:
        print("데이터 문제로 시작하지 못했습니다:", e)
        print("python check_data.py 로 자세히 확인해 보세요.")
        sys.exit(1)
    removed = qlog.prune()
    if removed:
        print(f"보관 기간({get('LOG_KEEP_DAYS')}일)이 지난 기록 {removed}줄을 지웠습니다.")
    host, port = get("HOST", "127.0.0.1"), get("PORT", 8000)
    print(f"설정: {cfg.SOURCE_FILE} / 데이터: {cfg.DATA_DIR} (메뉴 {len(data['menus'])}개)")
    print(f"질문 기록: {'켬(익명) → ' + str(qlog.path()) if get('LOG_ENABLED', False) else '끔'} / 사내 AI: {'켬' if get('LLM_ENABLED', False) else '끔'}")
    print(f"브라우저에서 여세요 → http://{host}:{port}   (끄기: Ctrl + C)")
    server = ThreadingHTTPServer((host, port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n길잡이를 껐습니다.")


if __name__ == "__main__":
    main()
