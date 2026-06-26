"""DB 스키마.

핵심 관계
---------
Source 1 ── N Deal           (커뮤니티별 원본 게시글)
Item   1 ── N Deal           (정규화된 상품 한 개에 여러 커뮤니티 딜이 묶임 → 요구사항 6)
Item   1 ── N PriceHistory   (상품별 가격 이력 → 요구사항 7: 평균 할인율/역대 최저 계산용)
User   1 ── N Keyword        (저장 키워드 → 요구사항 3: 텔레그램 알림)
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Source(Base):
    """수집 대상 커뮤니티. 코드의 registry와 slug로 동기화된다."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True)  # 예: "ppomppu"
    name: Mapped[str] = mapped_column(String(80))               # 예: "뽐뿌"
    kind: Mapped[str] = mapped_column(String(10))               # "rss" | "html"
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    deals: Mapped[list[Deal]] = relationship(back_populates="source")


class Item(Base):
    """정규화된 상품. 같은 상품이 여러 커뮤니티/시점에 올라와도 하나로 묶는다."""

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 제목을 정규화한 매칭 키 (브랜드/모델 위주, 가격·쇼핑몰태그 제거). v1은 휴리스틱.
    normalized_key: Mapped[str] = mapped_column(String(255), unique=True)
    display_name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    deals: Mapped[list[Deal]] = relationship(back_populates="item")
    prices: Mapped[list[PriceHistory]] = relationship(back_populates="item")


class Deal(Base):
    """커뮤니티 원본 게시글 1건."""

    __tablename__ = "deals"
    __table_args__ = (
        # 소스 내 게시글 ID로 중복 방지 (재수집 시 upsert 키)
        UniqueConstraint("source_id", "source_post_id", name="uq_deal_source_post"),
        Index("ix_deals_posted_at", "posted_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), nullable=True)

    source_post_id: Mapped[str] = mapped_column(String(64))   # 커뮤니티 게시글 고유 ID
    title: Mapped[str] = mapped_column(Text)                  # 원본 제목
    url: Mapped[str] = mapped_column(Text)
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)   # 원 단위, 파싱 실패 시 NULL
    currency: Mapped[str] = mapped_column(String(8), default="KRW")
    category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # 품절/종료 감지용 (요구사항 8)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source: Mapped[Source] = relationship(back_populates="deals")
    item: Mapped[Item | None] = relationship(back_populates="deals")


class PriceHistory(Base):
    """상품별 관측 가격 시계열. 평균/백분위/역대최저 계산의 원천."""

    __tablename__ = "price_history"
    __table_args__ = (Index("ix_price_item_observed", "item_id", "observed_at"),)

    # Postgres에선 BIGSERIAL, SQLite에선 INTEGER(autoincrement)로 컴파일
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    # 딜에서 관측된 가격이면 연결, 시드/외부 가져온 과거가는 NULL 가능
    deal_id: Mapped[int | None] = mapped_column(ForeignKey("deals.id"), nullable=True)
    price: Mapped[int] = mapped_column(Integer)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    item: Mapped[Item] = relationship(back_populates="prices")


# --- 알림 계정/인증 (요구사항 3·10) ---
# 사이트 열람은 무인증. 알림 기능만 초대제 + 텔레그램 연결로 신원 확인한다.


class User(Base):
    """알림 사용자. 초대코드로 생성 → 텔레그램 연결 시 auth_token 발급."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(40), unique=True, nullable=True)
    # 텔레그램 연결용 일회성 코드. 봇에 /start <code> → chat_id 연결 + auth_token 발급, claim 시 비움.
    link_code: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    # 연결 후 발급되는 비밀 인증 토큰(추측 불가). 키워드 API는 이 토큰(Bearer)으로만 접근.
    auth_token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    keywords: Mapped[list[Keyword]] = relationship(back_populates="user")


class Invite(Base):
    """초대 코드. 관리자가 CLI로 발급, 1회용. 알림 등록의 진입 게이트."""

    __tablename__ = "invites"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    label: Mapped[str | None] = mapped_column(String(80), nullable=True)  # 누구용인지 메모
    used_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Keyword(Base):
    __tablename__ = "keywords"
    __table_args__ = (UniqueConstraint("user_id", "keyword", name="uq_keyword_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    keyword: Mapped[str] = mapped_column(String(100))
    # 이 가격 이하일 때만 알림 (선택)
    max_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 이 등급 이상일 때만 알림 (선택). rating 토큰: good | great. None이면 등급 무관.
    min_rating: Mapped[str | None] = mapped_column(String(10), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped[User] = relationship(back_populates="keywords")


class Notification(Base):
    """발송한 알림 기록. (keyword, deal) 유니크로 같은 딜 중복 알림 방지."""

    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("keyword_id", "deal_id", name="uq_notif_keyword_deal"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    keyword_id: Mapped[int] = mapped_column(ForeignKey("keywords.id"))
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id"))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
