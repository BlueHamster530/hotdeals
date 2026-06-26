"""AI 챗봇 에이전트 (요구사항 4) — Google Gemini.

google-genai SDK + function calling. 우리 DB/분석 엔진을 도구로 노출해
"콜라 핫딜 중에 역대최저인 거 있어?" 같은 자연어 질의를 실제 데이터로 답한다.

수동 함수호출 루프를 쓰는 이유: 커스텀 툴이 비동기 DB 세션을 써야 하고(SDK 자동 호출은 동기 함수 가정),
무한 루프 가드 등 제어가 필요하기 때문. 비동기 호출은 client.aio 사용.
"""

from __future__ import annotations

import json
import logging

from google import genai
from google.genai import types

from app.analysis import service
from app.analysis.price_stats import meets_rating
from app.config import get_settings
from app.db import SessionLocal

logger = logging.getLogger("ai")

_MAX_ITERATIONS = 6  # 함수호출 왕복 상한 (무한 루프 방지)

SYSTEM_PROMPT = """너는 '핫딜 모아보기' 서비스의 AI 어시스턴트야.
국내 커뮤니티(뽐뿌·쿨앤조이·루리웹 등) 핫딜 데이터를 도구로 조회해 사용자 질문에 답한다.

규칙:
- 현재 딜·가격·할인 정보가 필요하면 반드시 search_deals 또는 get_item_analysis 도구를 먼저 호출해
  실제 데이터로 답한다. 절대 추측하지 않는다.
- "이거 진짜 싸?" 류의 질문엔 rating(great=역대급/good=좋은가격/normal=평범/poor=비싼편)과
  평균 대비 할인율(discount_vs_avg_pct), 역대 최저가(min_price)를 근거로 설명한다.
- 답변은 한국어로 간결하게. 가격은 원 단위로, 가능하면 원문 링크(url)도 함께 제시한다.
- 도구 결과에 없는 내용은 모른다고 솔직히 말한다."""


def _build_tools() -> list[types.Tool]:
    search = types.FunctionDeclaration(
        name="search_deals",
        description=(
            "현재 수집된 핫딜을 검색한다. 키워드/카테고리/최소 할인등급으로 거를 수 있다. "
            "사용자가 특정 상품이나 카테고리의 딜을 물을 때 호출하라."
        ),
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "q": types.Schema(type="STRING", description="제목 검색 키워드 (예: 콜라, SSD)"),
                "category": types.Schema(type="STRING", description="카테고리 (예: 제로음료, 전자기기)"),
                "min_rating": types.Schema(
                    type="STRING",
                    enum=["good", "great"],
                    description="이 할인등급 이상만. great=역대급, good=좋은가격 이상",
                ),
                "limit": types.Schema(type="INTEGER", description="최대 개수 (기본 10)"),
            },
        ),
    )
    item = types.FunctionDeclaration(
        name="get_item_analysis",
        description=(
            "특정 상품(item_id)의 가격 이력과 분석(역대 최저/평균/현재가 위치)을 가져온다. "
            "search_deals 결과의 item_id로 호출해 '진짜 싼지' 깊이 분석할 때 쓴다."
        ),
        parameters=types.Schema(
            type="OBJECT",
            properties={"item_id": types.Schema(type="INTEGER", description="상품 ID")},
            required=["item_id"],
        ),
    )
    cats = types.FunctionDeclaration(
        name="list_categories",
        description="필터에 쓸 수 있는 카테고리 목록을 반환한다.",
        parameters=types.Schema(type="OBJECT", properties={}),
    )
    return [types.Tool(function_declarations=[search, item, cats])]


def _compact_deal(d: dict) -> dict:
    """토큰 절약: 딜에서 모델이 답하는 데 필요한 필드만 추린다."""
    a = d["analysis"]
    return {
        "title": d["title"],
        "price": d["price"],
        "source": d["source"],
        "category": d["category"],
        "url": d["url"],
        "item_id": d["item_id"],
        "rating": a["rating"],
        "deal_score": a["deal_score"],
        "discount_vs_avg_pct": a["discount_vs_avg_pct"],
        "min_price": a["min_price"],
        "avg_price": a["avg_price"],
        "verdict": a["verdict"],
    }


async def _execute_tool(name: str, args: dict, session) -> str:
    """툴 실행 → JSON 문자열 반환 (function_response 내용)."""
    if name == "search_deals":
        deals = await service.list_deals(
            session,
            q=args.get("q"),
            category=args.get("category"),
            limit=min(int(args.get("limit", 10)), 30),
        )
        min_rating = args.get("min_rating")
        if min_rating:
            deals = [d for d in deals if meets_rating(d["analysis"]["rating"], min_rating)]
        return json.dumps([_compact_deal(d) for d in deals], ensure_ascii=False)

    if name == "get_item_analysis":
        detail = await service.item_detail(session, int(args["item_id"]))
        if detail is None:
            return json.dumps({"error": "item not found"}, ensure_ascii=False)
        return json.dumps(
            {
                "display_name": detail["display_name"],
                "category": detail["category"],
                "analysis": detail["analysis"],
                "history_points": len(detail["price_history"]),
                "recent_deals": [
                    {"title": x["title"], "price": x["price"], "source": x["source"], "url": x["url"]}
                    for x in detail["recent_deals"][:5]
                ],
            },
            ensure_ascii=False,
        )

    if name == "list_categories":
        return json.dumps(await service.list_categories(session), ensure_ascii=False)

    return json.dumps({"error": f"unknown tool: {name}"}, ensure_ascii=False)


def is_enabled() -> bool:
    return bool(get_settings().gemini_api_key)


async def run_agent(history: list[dict]) -> str:
    """대화 이력(history: [{role, content(str)}, ...])을 받아 어시스턴트 답변 텍스트를 반환."""
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)
    config = types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, tools=_build_tools())

    # Gemini 역할: 사용자="user", 어시스턴트="model"
    contents: list[types.Content] = [
        types.Content(
            role="model" if m["role"] == "assistant" else "user",
            parts=[types.Part(text=m["content"])],
        )
        for m in history
    ]

    async with SessionLocal() as session:
        for _ in range(_MAX_ITERATIONS):
            resp = await client.aio.models.generate_content(
                model=settings.gemini_model, contents=contents, config=config
            )
            cand = resp.candidates[0] if resp.candidates else None
            parts = cand.content.parts if (cand and cand.content and cand.content.parts) else []
            calls = [p.function_call for p in parts if getattr(p, "function_call", None)]

            if calls:
                contents.append(cand.content)  # 모델의 함수호출 턴 보존
                fr_parts = []
                for fc in calls:
                    try:
                        result = await _execute_tool(fc.name, dict(fc.args or {}), session)
                    except Exception as exc:
                        logger.warning("툴 실행 오류 %s: %s", fc.name, exc)
                        result = json.dumps({"error": str(exc)}, ensure_ascii=False)
                    fr_parts.append(
                        types.Part.from_function_response(name=fc.name, response={"result": result})
                    )
                contents.append(types.Content(role="user", parts=fr_parts))
                continue

            text = (resp.text or "").strip()
            return text or "죄송해요, 답변을 생성하지 못했어요."

    return "요청이 복잡해 처리하지 못했어요. 좀 더 구체적으로 물어봐 주세요."
