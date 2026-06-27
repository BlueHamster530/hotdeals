"""REST API.

  GET /api/deals?q=&category=&limit=&offset=   검색·필터된 딜 피드(+가격분석)  [요구사항 1·2·7]
  GET /api/items/{item_id}                     상품 상세: 가격이력+분석+최근딜      [요구사항 6·7]
  GET /api/categories                          필터용 카테고리 목록                [요구사항 2]
  GET /healthz

실행: uvicorn app.api.main:app --reload
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import alarm
from app.analysis import service
from app.config import get_settings
from app.db import get_session
from app.models import Keyword, User

app = FastAPI(title="hotdeals API", version="0.1")

# CORS 허용 출처는 WEB_ORIGIN 환경변수로 제어(운영=실제 도메인, 개발=localhost:3000).
# 운영에서 nginx가 같은 도메인의 /api로 프록시하면 동일 출처라 CORS는 사실상 미사용.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@app.get("/api/deals")
async def get_deals(
    q: str | None = Query(default=None, description="제목 검색어"),
    category: str | None = Query(default=None, description="카테고리 필터"),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> dict:
    deals = await service.list_deals(session, q=q, category=category, limit=limit, offset=offset)
    return {"count": len(deals), "deals": deals}


@app.get("/api/items/{item_id}")
async def get_item(
    item_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict:
    detail = await service.item_detail(session, item_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="item not found")
    return detail


@app.get("/api/categories")
async def get_categories(session: AsyncSession = Depends(get_session)) -> dict:
    return {"categories": await service.list_categories(session)}


# --- 알림: 초대제 + 텔레그램 연결 + 토큰 인증 (요구사항 3·10) ---
# 사이트 열람은 무인증. 알림만 초대코드로 진입 → 텔레그램 연결 시 비밀 auth_token 발급 →
# 키워드 API는 Bearer auth_token으로만 접근(추측 가능한 user_id 노출 제거).

_ALLOWED_RATINGS = {"good", "great"}


class RegisterRequest(BaseModel):
    invite_code: str


class KeywordRequest(BaseModel):
    keyword: str
    max_price: int | None = None
    min_rating: str | None = None  # "good" | "great" | None


def _normalize_rating(value: str | None) -> str | None:
    return value if value in _ALLOWED_RATINGS else None


async def require_user(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Authorization: Bearer <auth_token> 로 사용자 인증. 실패 시 401."""
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    user = await alarm.user_by_token(session, token)
    if user is None:
        raise HTTPException(status_code=401, detail="알림 기능은 인증이 필요합니다")
    return user


@app.post("/api/alarm/register")
async def alarm_register(
    body: RegisterRequest, session: AsyncSession = Depends(get_session)
) -> dict:
    """초대코드로 알림 등록 시작. 유효하면 텔레그램 연결코드를 발급한다."""
    user = await alarm.consume_invite(session, body.invite_code.strip())
    if user is None:
        raise HTTPException(status_code=400, detail="유효하지 않거나 이미 사용된 초대 코드입니다")
    return {
        "link_code": user.link_code,
        "bot_username": get_settings().telegram_bot_username or None,
    }


@app.get("/api/alarm/claim")
async def alarm_claim(link_code: str, session: AsyncSession = Depends(get_session)) -> dict:
    """텔레그램 연결 완료를 확인하고 auth_token을 1회 수령(폴링용)."""
    token = await alarm.claim(session, link_code)
    if token is None:
        return {"connected": False}
    return {"connected": True, "auth_token": token}


@app.get("/api/alarm/keywords")
async def alarm_list_keywords(
    user: User = Depends(require_user), session: AsyncSession = Depends(get_session)
) -> dict:
    rows = (
        await session.execute(
            select(Keyword).where(Keyword.user_id == user.id).order_by(Keyword.id.desc())
        )
    ).scalars().all()
    return {
        "keywords": [
            {
                "id": k.id,
                "keyword": k.keyword,
                "max_price": k.max_price,
                "min_rating": k.min_rating,
                "enabled": k.enabled,
            }
            for k in rows
        ]
    }


@app.post("/api/alarm/keywords")
async def alarm_add_keyword(
    body: KeywordRequest,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    kw = (body.keyword or "").strip()
    if not kw:
        raise HTTPException(status_code=400, detail="keyword required")

    existing = (
        await session.execute(
            select(Keyword).where(Keyword.user_id == user.id, Keyword.keyword == kw)
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = Keyword(user_id=user.id, keyword=kw)
        session.add(existing)
    existing.max_price = body.max_price
    existing.min_rating = _normalize_rating(body.min_rating)
    existing.enabled = True
    await session.commit()
    return {"id": existing.id, "keyword": existing.keyword,
            "max_price": existing.max_price, "min_rating": existing.min_rating}


@app.delete("/api/alarm/keywords/{keyword_id}")
async def alarm_delete_keyword(
    keyword_id: int,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    kw = await session.get(Keyword, keyword_id)
    if kw is not None and kw.user_id == user.id:  # 본인 키워드만 삭제 가능
        await session.delete(kw)
        await session.commit()
    return {"ok": True}


# --- AI 챗봇 (요구사항 4) ---


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


@app.get("/api/chat/status")
async def chat_status() -> dict:
    from app.ai import agent

    return {"enabled": agent.is_enabled()}


@app.post("/api/chat")
async def chat(body: ChatRequest) -> dict:
    from app.ai import agent

    if not agent.is_enabled():
        raise HTTPException(status_code=503, detail="AI 챗봇이 비활성화되어 있습니다 (GEMINI_API_KEY 미설정)")
    history = [{"role": m.role, "content": m.content} for m in body.messages if m.content.strip()]
    if not history or history[-1]["role"] != "user":
        raise HTTPException(status_code=400, detail="마지막 메시지는 사용자 메시지여야 합니다")
    reply = await agent.run_agent(history)
    return {"reply": reply}
