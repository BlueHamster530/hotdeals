# hotdeals

국내 커뮤니티 핫딜 통합 수집·분석 서비스. 현재 단계: **수집 + DB**.

## 아키텍처 (전체 그림)

```
[수집 워커] ── 주기 polling ──► [PostgreSQL] ◄── REST ──► [FastAPI] ◄──► [Next.js 웹]
  RSS/HTML 하이브리드            deals/items/price_history        │
  정규화 + dedup                                                 ├─► [텔레그램 봇] (키워드 알림)
                                                                 └─► [AI 챗봇] (추후)
전체를 Docker Compose로 묶어 AWS Lightsail 단일 인스턴스 배포
```

## 데이터 모델

| 테이블 | 역할 |
|--------|------|
| `sources` | 수집 대상 커뮤니티 (뽐뿌, 쿨앤조이 …) |
| `deals` | 커뮤니티 원본 게시글 1건 (`source_id`+`source_post_id` 유니크로 중복 방지) |
| `items` | 정규화된 상품. 여러 커뮤니티/시점 딜을 하나로 묶음 |
| `price_history` | 상품별 가격 시계열 → 평균 할인율·역대 최저 계산 |
| `users`, `keywords` | 텔레그램 키워드 알림용 (스키마만, 로직은 추후) |

## 실행 방법

```bash
# 1) 환경변수
cp .env.example .env        # 필요시 비밀번호 수정

# 2) DB 기동
docker compose up -d db

# 3) 파이썬 의존성
python -m venv .venv && . .venv/Scripts/activate   # Windows
pip install -r requirements.txt

# 4) 테이블 생성
python -m app.cli init-db

# 5) 1회 수집 / 주기 수집
python -m app.cli ingest
python -m app.cli loop
```

확인:
```bash
docker compose exec db psql -U hotdeals -d hotdeals \
  -c "select s.name, count(*) from deals d join sources s on s.id=d.source_id group by 1;"
```

## 소스 추가하기

`app/sources/` 에 소스를 구현하고 `registry.py`의 `SOURCES`에 등록하면 끝.

- **RSS (1순위, 가장 쉬움)**: `RssSource` 상속 + `feed_url`만 지정 → 가격/카테고리/썸네일 자동.
- **HTML**: `HtmlSource` 상속 + `parse(soup)` 구현 (BeautifulSoup). `app/sources/clien.py`가 검증된 예시.
- 봇 UA를 403으로 막는 사이트는 `extra_headers = BROWSER_HEADERS` 로 브라우저 UA 사용(클리앙·다모앙).

현재 활성(2026-06 라이브 검증): 뽐뿌·쿨앤조이·루리웹·다모앙(RSS), 클리앙(HTML) — 5곳.
미활성(Cloudflare 봇차단 → 헤드리스 브라우저 필요): 아카라이브(템플릿 `arca.py`), 퀘이사존, 펨코.

## 프론트엔드 (web/)

Next.js(App Router + TS). 딜 피드(검색·카테고리 필터), 썸네일(없으면 빈 칸),
원문 링크, 가격 게이지(역대가 대비 현재가 위치)를 렌더한다.

```bash
cd web
cp .env.local.example .env.local      # NEXT_PUBLIC_API_BASE 확인
npm install
npm run dev                            # http://localhost:3000
```

백엔드(FastAPI, :8000)가 떠 있어야 데이터가 표시된다. CORS는 localhost:3000 허용됨.
`/settings`는 텔레그램 알림 설정 UI(현재는 미리보기 stub, 봇 구현 후 연동).

## 텔레그램 알림 (요구사항 3)

키워드 + (선택) 최대가격 + (선택) 할인도 등급 조건이 맞는 신규 딜이 뜨면 발송.
조건은 이미 만든 가격 분석(`rating`)을 재활용한다. 중복 발송은 `notifications` 테이블로 방지.

```bash
# 1) @BotFather로 봇 생성 → .env에 토큰/사용자명 입력
#    TELEGRAM_BOT_TOKEN=...   TELEGRAM_BOT_USERNAME=...
python -m app.cli init-db        # notifications/min_rating 등 신규 스키마 반영(개발: 재생성)
python -m app.cli bot            # 연결 봇 (long-polling) — 별도 프로세스로 상시 실행
python -m app.cli loop           # 수집 루프가 신규 딜마다 알림 매칭/발송
```

**초대제 + 토큰 인증 (요구사항 10):** 알림은 초대받은 사람만. 사이트 열람은 무인증.
```
관리자: python -m app.cli invite "친구A"   → 초대코드 발급
친구:   웹 /settings 에 초대코드 입력 → 연결코드 발급 → 봇에 /start <연결코드>
        → chat_id 연결 + 비밀 auth_token 발급 → 웹이 claim으로 수령 → 이후 Bearer 인증
```
키워드 API(`/api/alarm/keywords`)는 `auth_token`(Bearer)으로만 접근 — 추측 가능한 user_id 노출 없음.
토큰이 비어 있으면 알림만 자동 비활성(나머지 정상).

## AI 챗봇 (요구사항 4)

Google Gemini(`google-genai`) + function calling. DB·분석 엔진을 도구(`search_deals`/`get_item_analysis`/
`list_categories`)로 노출해 "콜라 핫딜 중 역대최저 있어?" 같은 자연어 질의를 실제 데이터로 답한다.
모델 `gemini-2.5-flash`(무료 티어), 수동 함수호출 루프(비동기 DB 세션 + 루프 가드).

```bash
# .env: GEMINI_API_KEY=...  (무료: https://aistudio.google.com/apikey)
pip install -r requirements.txt   # google-genai 추가됨
uvicorn app.api.main:app --reload # POST /api/chat, GET /api/chat/status
```

웹 `/chat`에서 사용. 키 미설정이면 자동 비활성(나머지 정상).

### 자동 카테고리 분류 (요구사항 2)
**규칙(키워드 사전, 무료)만으로 분류**(`app/ingest/classify.py`). AI(Gemini) 분류도 시도했지만
무료 티어 일일 요청 한도(20건)가 수집량을 감당하지 못해 걷어냈다(2026-07-08).
- 같은 상품(Item) 재게시는 캐시로 재사용, 신규 딜은 수집 시 자동 분류(`pipeline` → `classify_new`).
- 기존 딜 백필: `python -m app.cli classify`.
- 규칙 사전에 없는 품종명/신상품('새청무'처럼)은 미분류로 남는다 — 키워드 사전(`app/ingest/normalize.py`
  의 `_CATEGORY_KEYWORDS`)을 보강하면 다음 백필 때 소급 적용됨.

## 다음 단계 (로드맵)

- [x] 수집 + DB (RSS 2종 + 정규화/dedup)
- [x] FastAPI: 검색·카테고리 필터·딜 피드·상품 상세
- [x] 할인율 분석 + 게이지 시각화 (요구사항 7)
- [x] 프론트엔드: 딜 피드 + 썸네일 + 원문 링크 (요구사항 1·2·6·7)
- [x] 텔레그램 알림: 키워드+가격+할인도 조건 + 프론트 연동 (요구사항 3)
- [x] 소스 확장: 뽐뿌·쿨앤조이·루리웹(RSS, 검증) + HtmlSource 기반 + 아카라이브(HTML 템플릿)
- [x] AI 챗봇: Claude API + DB 도구 (요구사항 4)
- [x] 배포 구성: Dockerfile(백엔드/프론트) + docker-compose.prod + nginx + 가이드 (요구사항 5) → [DEPLOY.md](DEPLOY.md)
- [x] 보안: 알림 초대제 + 텔레그램 연결 + auth_token(Bearer) 인증 (요구사항 10)
- [x] 소스 5곳: 뽐뿌·쿨앤조이·루리웹·다모앙(RSS) + 클리앙(HTML), 라이브 검증
- [ ] (선택) Cloudflare 소스(아카·퀘이사존·펨코) — 헤드리스 브라우저 필요

## 테스트

```bash
pip install -r requirements-dev.txt
pytest                 # 49개: 파싱·분석·소스파서·서비스·알림보안·API·이미지프록시
```
인메모리 SQLite로 실행(외부 의존 없음). 커버: 가격/카테고리 파싱 엣지케이스, 등급 분석,
클리앙 HTML 파서(구조변경 회귀방지), 검색·필터, SQL injection 방지, 초대제 토큰 인증,
이미지 프록시 SSRF 차단, 썸네일 상대→절대경로(실제 잡았던 버그).

## 운영 배포

AWS Lightsail 단일 인스턴스 + Docker Compose. 단계별 절차(인스턴스 생성·도메인·HTTPS·HTTPS 자동갱신·
보안 체크리스트)는 **[DEPLOY.md](DEPLOY.md)** 참고.

```bash
cp .env.prod.example .env.prod   # 값 채우기 (서버에서만)
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm api python -m app.cli init-db
```
구성: nginx(80/443) → web(Next standalone) + api(FastAPI /api), 백그라운드 worker(수집 loop)·bot(텔레그램),
내부 db(Postgres, 외부 비노출).

> 스키마 메모: 아직 Alembic 없이 `create_all`이라, 컬럼/테이블이 늘면 개발 DB는 재생성이 가장 간단.
> 운영 데이터가 쌓이기 시작하면 Alembic 도입 권장.

## 보안 메모 (요구사항 10)

- DB 포트는 loopback(`127.0.0.1`)에만 바인딩 — 외부 비노출
- 비밀값은 `.env` (git 커밋 금지), 운영은 Lightsail 환경변수
- 크롤링 시 정직한 User-Agent + 호출 간격 준수 (각 사이트 ToS)
- 추후 웹/봇은 공개 가입 차단(초대제) + HTTPS 강제
