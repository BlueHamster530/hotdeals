# 배포 가이드 — AWS Lightsail (요구사항 5)

단일 Lightsail 인스턴스(2GB)에 Docker Compose로 전체 스택(db·api·worker·bot·web·nginx)을 띄운다.
외부엔 nginx(80/443)만 노출하고 DB는 내부망에만 둔다. (보안: 요구사항 10)

> 비밀값(DB 비번, 텔레그램 토큰, Anthropic 키)은 **서버의 `.env.prod`에만** 넣는다. 저장소/채팅에 올리지 말 것.

---

## 0. 준비물 체크
- [x] AWS Lightsail 계정 (보유)
- [x] 텔레그램 봇 토큰 (보유) — 봇 사용자명도 확인(@BotFather → 봇 설정)
- [ ] 도메인 (새로 구매 예정 — 3단계)
- [ ] Anthropic API 키 (선택 — 없으면 AI 챗봇만 비활성, 나중에 추가 가능)

---

## 1. Lightsail 인스턴스 생성
1. Lightsail 콘솔 → **Create instance**
2. Linux/Unix → **Ubuntu 22.04 LTS**
3. 플랜: **2GB RAM / 2 vCPU** (월 $12 수준)
4. 인스턴스 생성 후 **Networking → Create static IP** 로 고정 IP 할당(필수: 재부팅해도 IP 유지)
5. **Networking → Firewall** 에서 인바운드 규칙:
   - 허용: **22(SSH), 80(HTTP), 443(HTTPS)**
   - **5432(Postgres)는 절대 열지 않는다** (DB는 컨테이너 내부망만)

## 2. 서버 기본 설정 (SSH 접속 후)
```bash
sudo apt update && sudo apt -y upgrade
# Docker + Compose 설치
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && newgrp docker

# 코드 가져오기 (git 사용 시)
git clone <레포주소> hotdeals && cd hotdeals
# 또는 scp/rsync로 업로드
```

## 3. 도메인 구매 + DNS 연결
1. 도메인 등록기관에서 구매(가비아·후이즈·Cloudflare·Namecheap 등). `.com` 기준 연 1~2만원대.
2. DNS에 **A 레코드** 추가: `@` 와 `www` → **Lightsail 고정 IP**
   - Cloudflare를 쓰면 프록시(주황 구름)는 처음엔 끄고(DNS only) certbot 발급 후 켜는 걸 권장
3. `dig +short your-domain.com` 로 IP가 보이면 전파 완료(수 분~수 시간)

## 4. 환경변수 설정
```bash
cp .env.prod.example .env.prod
nano .env.prod
```
- `POSTGRES_PASSWORD` : 강력하게. 예) `openssl rand -base64 24`
- `WEB_ORIGIN` : `https://your-domain.com` (도메인 전이면 `http://<고정IP>`)
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME` 입력
- `ANTHROPIC_API_KEY` : 있으면 입력(없으면 비워둠 → 챗봇 비활성)

## 5. 최초 기동 (HTTP)
```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
# 스키마 생성 (최초 1회)
docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm api python -m app.cli init-db
```
- `http://<고정IP>` 또는 `http://your-domain.com` 접속 확인
- 로그: `docker compose -f docker-compose.prod.yml logs -f api worker`

## 6. HTTPS 전환 (Let's Encrypt)
도메인 A레코드가 서버를 가리키는지 확인 후:
```bash
mkdir -p nginx/certbot/www nginx/certbot/conf
# 인증서 발급 (도메인/이메일 교체)
docker run --rm \
  -v $(pwd)/nginx/certbot/conf:/etc/letsencrypt \
  -v $(pwd)/nginx/certbot/www:/var/www/certbot \
  certbot/certbot certonly --webroot -w /var/www/certbot \
  -d your-domain.com -d www.your-domain.com \
  --email you@example.com --agree-tos --no-eff-email
```
발급 성공하면 `nginx/conf.d/default.conf` 의 `server { listen 80; ... }` **아래에** 다음 블록을 추가하고,
기존 80 서버의 `location /api/`·`location /`·`location /healthz` 는 **HTTPS로 리다이렉트**하도록 바꾼다:

```nginx
# 80 서버: 인증 챌린지만 남기고 나머지는 443으로 리다이렉트
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 301 https://$host$request_uri; }
}

server {
    listen 443 ssl;
    server_name your-domain.com www.your-domain.com;

    ssl_certificate     /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location /api/ {
        proxy_pass http://hotdeals_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    location /healthz { proxy_pass http://hotdeals_api; }
    location / {
        proxy_pass http://hotdeals_web;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
그리고 `docker-compose.prod.yml` 의 nginx 인증서 마운트를 `:ro` 로 이미 걸어뒀으니 nginx만 재시작:
```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod restart nginx
```
`.env.prod` 의 `WEB_ORIGIN` 을 `https://your-domain.com` 으로 두고 `api` 재시작.

**자동 갱신**(인증서 90일): crontab에 등록
```bash
0 3 * * * cd ~/hotdeals && docker run --rm -v $(pwd)/nginx/certbot/conf:/etc/letsencrypt -v $(pwd)/nginx/certbot/www:/var/www/certbot certbot/certbot renew --quiet && docker compose -f docker-compose.prod.yml restart nginx
```

## 7. 알림 초대 + 텔레그램 연결 + 데이터 확인
- 초대 코드 발급(관리자): `docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm api python -m app.cli invite "친구A"`
- 친구: 웹 `/settings` 에 초대코드 입력 → 연결코드 발급 → 봇에 `/start <연결코드>` (자동 연결됨)
- 수집은 `worker`(loop)가 `INGEST_INTERVAL_SECONDS` 주기로 자동. 즉시 한 번 돌리려면:
  ```bash
  docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm api python -m app.cli ingest
  ```

## 8. 운영 명령 모음
```bash
# 상태/로그
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f worker

# 코드 업데이트 후 재배포 (nginx는 Docker DNS resolver로 IP 변경 자동 추적 → 502 없음)
git pull
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build

# DB 백업
docker compose -f docker-compose.prod.yml exec db pg_dump -U hotdeals hotdeals > backup_$(date +%F).sql
```

---

## 보안 체크리스트 (요구사항 10)
- [x] DB 포트 비공개(컨테이너 내부망만), 방화벽 5432 차단
- [x] 비밀값은 `.env.prod`(git 제외), 채팅/저장소 노출 금지
- [x] HTTPS 강제(6단계 후) + 자동 갱신
- [x] **알림 초대제 + 토큰 인증** — 알림은 초대코드로만 등록, 텔레그램 연결 시 발급되는
      비밀 `auth_token`(Bearer)으로만 키워드 API 접근. 사이트 열람은 무인증(누구나).
- [ ] (선택) SSH 키 인증만 허용, root 로그인 비활성, fail2ban
- [ ] (선택) Lightsail 스냅샷 정기 백업
