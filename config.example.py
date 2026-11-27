# config.example.py — 설정 자리만 있는 견본 (로직 없음)
# 실행 PC에서는 이 파일을 config.py로 복사한 뒤 config.py만 고친다.
# config.py는 GitHub에 올라가지 않는다(.gitignore).

# 데이터 폴더: GitHub에서는 가짜 데이터 "samples", 실행 PC에서는 실제 데이터 "data"
DATA_DIR = "samples"

# 메뉴 ID를 끼워 넣으면 그 메뉴가 바로 열리는 주소 틀. {menu_id} 자리는 그대로 둔다.
MENU_URL_TEMPLATE = "https://portal.hanbit.example/go?id={menu_id}"

# 웹 서버
HOST = "127.0.0.1"
PORT = 8000

# 1층 검색
TOP_K = 3          # 메뉴 결과 최대 개수
MIN_SCORE = 2      # 이 점수 이상만 보여 준다
STOPWORDS = ["신청", "조회", "안내", "요청", "발급", "등록", "이용", "제출", "예약"]



# 화면 이름. 메인 = 맨 위 제목(외부 브랜드) + 규칙 검색창 + 상황 대시보드, 오른쪽 아래 동그라미 = AI 챗봇 창.
# 실제 브랜드 이름(회사 이름이 들어가면)은 실행 PC의 config.py에만 쓴다.
APP_TITLE = "온보딩 메뉴 길잡이"
APP_SUBTITLE = "궁금한 건 평소 말로 물어보세요. 바로 찾아 드리고, 못 찾으면 AI 챗봇이 이어서 도와드려요."
CHAT_TITLE = "메뉴 길잡이 챗봇"             # 챗봇 창 이름. 실행 PC에서 원하는 이름으로 바꾼다
CHAT_EXAMPLES = ["법카 어디서 신청해?", "비번 까먹었어", "차 쓰고 왔는데 뭐 써야 돼?"]

# 메인 큰 검색창 아래 예시 질문 버튼(규칙으로 찾는 질문) (실제 데이터에 맞춰 바꾼다)
EXAMPLE_QUESTIONS = ["손님 와", "다음 주에 출장 가", "기숙사 들어가고 싶어"]

# 아무것도 못 찾았을 때 보여 줄 문구. 연락처 대신 가까운 선배와 직접 이야기하도록 정중하게 권한다.
UNKNOWN_MESSAGE = "이 질문은 제가 아직 잘 몰라요. 부서 선배님께 편하게 여쭤보는 건 어떨까요? 처음에는 누구나 묻고 배워요."

# 3층 사내 AI (선택). 규칙(1·2층)으로 못 찾았을 때만 부른다. 꺼도, 연결이 안 돼도 1·2층은 동작한다.
# 사내 AI가 OpenAI 호환 API(…/v1/chat/completions)를 준다고 가정한다. 키는 여기에 쓰지 않고 .env의 LLM_API_KEY에 둔다.
LLM_ENABLED = False
LLM_BASE_URL = "https://ai.hanbit.example/v1"   # 사내 AI 안내서의 API 주소(…/v1 까지만)
LLM_MODEL = "model-name"                       # 사내 AI 안내서의 모델 이름 그대로
LLM_TIMEOUT = 20                               # 초. 넘으면 조용히 "선배에게 여쭤보기" 문구
LLM_SSL_VERIFY = True                          # 사내 인증서 때문에 연결이 안 되면 False로(사내 주소일 때만)
LLM_USE_SYSTEM_PROXY = True                    # 사내 주소인데 프록시 때문에 안 되면 False로
LLM_MAX_MENUS = 400                            # AI에게 보여 줄 메뉴 지도 최대 줄 수
LLM_MAX_TOKENS = 1000                          # AI 답 최대 길이. "길이 제한에서 잘렸습니다"가 나오면 늘린다(생각하는 모델은 2000~4000)
LLM_JSON_MODE = False                          # "JSON을 찾지 못했습니다"가 계속 나오면 True로(사내 AI가 지원할 때만. 400 오류가 나면 다시 False)

# 질의응답 기록(익명). 이 챗봇의 목적: 신입·인턴이 무엇을 가장 궁금해하는지 알고, 틀린 답을 고친다.
# 남기는 것: 시각·화면·질문(긴 숫자·전화·메일은 가림)·답 종류·보여 준 메뉴·AI 한마디·오류·응답 시간, [열기]를 누른 메뉴.
# 남기지 않는 것: 사번·이름·IP·컴퓨터 이름·세션. 요약 보기: python log_report.py
LOG_ENABLED = True
LOG_PATH = "logs/questions.csv"
LOG_KEEP_DAYS = 90                             # 이 날수가 지난 줄은 길잡이를 켤 때 지운다(0이면 지우지 않음)
LOG_MIN_GROUP = 5                              # log_report.py의 "많이 묻는 것"은 이 횟수 이상만 보여 준다

# 화면에 은은하게 보이는 수집 안내(기록이 켜져 있을 때만 보인다). 문구는 도입하는 조직의 정책에 맞춰 고친다.
LOG_NOTICE = "🔒 질문과 답변은 이름·사번 없이 익명으로 저장되어, 길잡이를 고치고 신입·인턴이 많이 묻는 것을 살피는 데만 쓰여요. 인턴십·인사 평가에는 반영되지 않아요."
LOG_NOTICE_DETAIL = "저장하는 것: 질문, 길잡이의 답, 누른 메뉴, 시각. 저장하지 않는 것: 이름, 사번, 컴퓨터 정보. 질문에 개인정보(이름·사번·연락처)는 적지 말아 주세요. 기록은 90일 뒤 지워지고, 담당자는 개인이 아닌 묶음 통계로만 봅니다."
