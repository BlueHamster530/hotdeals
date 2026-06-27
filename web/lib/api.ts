// FastAPI 백엔드 클라이언트 + 응답 타입 (app/analysis/service.py 의 반환 형태와 일치)

// 기본은 상대경로("") — 운영에선 nginx가 같은 도메인의 /api 를 FastAPI로 프록시.
// 로컬 개발(next dev, api는 :8000 별도)에서는 .env.local 에 절대주소를 지정한다.
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "";

export type Rating = "great" | "good" | "normal" | "poor" | "unknown";

export interface PriceAnalysis {
  sample_size: number;
  current_price: number | null;
  min_price: number | null;
  max_price: number | null;
  avg_price: number | null;
  median_price: number | null;
  discount_vs_avg_pct: number | null;
  price_position: number | null;
  deal_score: number | null;
  is_lowest_ever: boolean;
  verdict: string;
  rating: Rating;
}

export interface Deal {
  id: number;
  title: string;
  url: string;
  price: number | null;
  category: string | null;
  source: string;
  posted_at: string | null;
  fetched_at: string | null;
  item_id: number | null;
  analysis: PriceAnalysis;
}

// 등록 시각을 상대 표현으로 ("방금" / "3시간 전" / "2일 전" / "2026.06.20")
export function relativeTime(iso: string | null): string {
  if (!iso) return "";
  const dt = new Date(iso);
  const t = dt.getTime();
  if (Number.isNaN(t)) return "";
  const mins = Math.floor((Date.now() - t) / 60000);
  if (mins < 1) return "방금";
  if (mins < 60) return `${mins}분 전`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}시간 전`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}일 전`;
  const p = (n: number) => String(n).padStart(2, "0");
  return `${dt.getFullYear()}.${p(dt.getMonth() + 1)}.${p(dt.getDate())}`;
}

export interface DealsResponse {
  count: number;
  deals: Deal[];
}

export async function fetchDeals(params: {
  q?: string;
  category?: string;
  limit?: number;
}): Promise<Deal[]> {
  const qs = new URLSearchParams();
  if (params.q) qs.set("q", params.q);
  if (params.category) qs.set("category", params.category);
  qs.set("limit", String(params.limit ?? 30));

  const res = await fetch(`${API_BASE}/api/deals?${qs.toString()}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`딜 조회 실패: ${res.status}`);
  const data: DealsResponse = await res.json();
  return data.deals;
}

export async function fetchCategories(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/api/categories`, { cache: "no-store" });
  if (!res.ok) throw new Error(`카테고리 조회 실패: ${res.status}`);
  const data: { categories: string[] } = await res.json();
  return data.categories;
}

export function formatKRW(value: number | null): string {
  if (value == null) return "-";
  return value.toLocaleString("ko-KR") + "원";
}

// --- 알림: 초대제 + 텔레그램 연결 + 토큰 인증 (요구사항 3·10) ---

export interface RegisterResponse {
  link_code: string;
  bot_username: string | null;
}

export interface KeywordItem {
  id: number;
  keyword: string;
  max_price: number | null;
  min_rating: string | null;
  enabled: boolean;
}

/** 인증 토큰을 만료/무효로 판별하기 위한 커스텀 에러 */
export class AuthError extends Error {}

function authHeaders(token: string): HeadersInit {
  return { "Content-Type": "application/json", Authorization: `Bearer ${token}` };
}

export async function registerAlarm(inviteCode: string): Promise<RegisterResponse> {
  const res = await fetch(`${API_BASE}/api/alarm/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ invite_code: inviteCode }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `등록 실패: ${res.status}`);
  }
  return res.json();
}

export async function claimAlarm(
  linkCode: string
): Promise<{ connected: boolean; auth_token?: string }> {
  const res = await fetch(`${API_BASE}/api/alarm/claim?link_code=${encodeURIComponent(linkCode)}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`연결 확인 실패: ${res.status}`);
  return res.json();
}

export async function listAlarmKeywords(token: string): Promise<KeywordItem[]> {
  const res = await fetch(`${API_BASE}/api/alarm/keywords`, {
    headers: authHeaders(token),
    cache: "no-store",
  });
  if (res.status === 401) throw new AuthError("unauthorized");
  if (!res.ok) throw new Error(`키워드 조회 실패: ${res.status}`);
  return (await res.json()).keywords;
}

export async function addAlarmKeyword(
  token: string,
  body: { keyword: string; max_price?: number | null; min_rating?: string | null }
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/alarm/keywords`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (res.status === 401) throw new AuthError("unauthorized");
  if (!res.ok) throw new Error(`키워드 추가 실패: ${res.status}`);
}

export async function deleteAlarmKeyword(token: string, keywordId: number): Promise<void> {
  await fetch(`${API_BASE}/api/alarm/keywords/${keywordId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
}

// --- AI 챗봇 (요구사항 4) ---

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export async function chatStatus(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/chat/status`, { cache: "no-store" });
    if (!res.ok) return false;
    return (await res.json()).enabled;
  } catch {
    return false;
  }
}

export async function sendChat(messages: ChatMessage[]): Promise<string> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `채팅 실패: ${res.status}`);
  }
  return (await res.json()).reply;
}
