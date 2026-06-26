"use client";

// 알림 설정 — 초대제 + 텔레그램 연결 + 토큰 인증 (요구사항 3·10).
// 흐름: 초대코드 입력 → 연결코드 발급 → 봇 /start <코드> → claim으로 auth_token 수령 → 키워드 관리.
// auth_token(비밀)을 localStorage에 저장해 신원으로 사용(추측 가능한 user_id 노출 없음).

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AuthError,
  KeywordItem,
  addAlarmKeyword,
  claimAlarm,
  deleteAlarmKeyword,
  listAlarmKeywords,
  registerAlarm,
} from "@/lib/api";

const TOKEN_KEY = "hotdeals_alarm_token";
type Phase = "loading" | "register" | "connecting" | "manage";

const cardStyle: React.CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--border-2)",
  borderRadius: "var(--radius)",
  padding: 16,
  marginTop: 12,
};

export default function SettingsPage() {
  const [phase, setPhase] = useState<Phase>("loading");
  const [token, setToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 등록/연결
  const [invite, setInvite] = useState("");
  const [linkCode, setLinkCode] = useState<string | null>(null);
  const [botUsername, setBotUsername] = useState<string | null>(null);

  // 키워드
  const [keywords, setKeywords] = useState<KeywordItem[]>([]);
  const [keyword, setKeyword] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [minRating, setMinRating] = useState("");

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadKeywords = useCallback(async (t: string) => {
    try {
      setKeywords(await listAlarmKeywords(t));
      setPhase("manage");
    } catch (e) {
      if (e instanceof AuthError) {
        window.localStorage.removeItem(TOKEN_KEY);
        setToken(null);
        setPhase("register");
      } else {
        setError((e as Error).message);
      }
    }
  }, []);

  useEffect(() => {
    const stored = typeof window !== "undefined" ? window.localStorage.getItem(TOKEN_KEY) : null;
    if (stored) {
      setToken(stored);
      loadKeywords(stored);
    } else {
      setPhase("register");
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [loadKeywords]);

  async function handleRegister() {
    setError(null);
    try {
      const res = await registerAlarm(invite.trim());
      setLinkCode(res.link_code);
      setBotUsername(res.bot_username);
      setPhase("connecting");
      // 연결 완료(=/start 처리)될 때까지 폴링
      pollRef.current = setInterval(async () => {
        try {
          const r = await claimAlarm(res.link_code);
          if (r.connected && r.auth_token) {
            if (pollRef.current) clearInterval(pollRef.current);
            window.localStorage.setItem(TOKEN_KEY, r.auth_token);
            setToken(r.auth_token);
            loadKeywords(r.auth_token);
          }
        } catch {
          /* 일시 오류는 무시하고 계속 폴링 */
        }
      }, 2500);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleAdd() {
    if (!token || !keyword.trim()) return;
    try {
      await addAlarmKeyword(token, {
        keyword: keyword.trim(),
        max_price: maxPrice ? Number(maxPrice) : null,
        min_rating: minRating || null,
      });
      setKeyword("");
      setMaxPrice("");
      setMinRating("");
      loadKeywords(token);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleDelete(id: number) {
    if (!token) return;
    await deleteAlarmKeyword(token, id);
    loadKeywords(token);
  }

  return (
    <main>
      <h2 style={{ fontSize: 18, fontWeight: 600 }}>텔레그램 알림 설정</h2>
      <p style={{ color: "var(--text-2)", fontSize: 14 }}>
        알림은 <strong>초대제</strong>예요. 초대 코드로 등록하고 텔레그램을 연결하면, 저장한 키워드의
        핫딜이 조건에 맞게 뜰 때 알려드립니다. (사이트 둘러보기는 누구나 가능)
      </p>
      {error && <p style={{ color: "#A32D2D", fontSize: 14 }}>오류: {error}</p>}

      {phase === "loading" && <p style={{ color: "var(--text-3)" }}>불러오는 중…</p>}

      {phase === "register" && (
        <section style={cardStyle}>
          <h3 style={{ fontSize: 15, fontWeight: 500, marginTop: 0 }}>초대 코드로 시작</h3>
          <p style={{ fontSize: 14, color: "var(--text-2)" }}>
            관리자에게 받은 초대 코드를 입력하세요.
          </p>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <input
              className="search-input"
              style={{ flex: 1, minWidth: 200 }}
              placeholder="초대 코드"
              value={invite}
              onChange={(e) => setInvite(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleRegister()}
            />
            <button className="chip" onClick={handleRegister} disabled={!invite.trim()}>
              등록
            </button>
          </div>
        </section>
      )}

      {phase === "connecting" && linkCode && (
        <section style={cardStyle}>
          <h3 style={{ fontSize: 15, fontWeight: 500, marginTop: 0 }}>텔레그램 연결</h3>
          <p style={{ fontSize: 14 }}>
            아래 버튼으로 봇을 열어 <code>/start {linkCode}</code> 를 보내면 연결됩니다.
            연결되면 이 화면이 자동으로 넘어가요.
          </p>
          {botUsername ? (
            <a
              href={`https://t.me/${botUsername}?start=${linkCode}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              @{botUsername} 열고 자동 연결 ↗
            </a>
          ) : (
            <div style={{ color: "var(--text-3)", fontSize: 14 }}>
              봇 채팅에서 <code>/start {linkCode}</code> 를 보내세요.
            </div>
          )}
          <p style={{ color: "var(--text-3)", fontSize: 13, marginTop: 10 }}>연결 대기 중…</p>
        </section>
      )}

      {phase === "manage" && (
        <section style={cardStyle}>
          <h3 style={{ fontSize: 15, fontWeight: 500, marginTop: 0 }}>
            알림 키워드 <span style={{ color: "#27500A", fontSize: 13 }}>· 연결됨</span>
          </h3>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <input
              className="search-input"
              style={{ flex: 2, minWidth: 160 }}
              placeholder="키워드 (예: 코카콜라 제로)"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            />
            <input
              className="search-input"
              style={{ flex: 1, minWidth: 110 }}
              placeholder="최대가격(선택)"
              inputMode="numeric"
              value={maxPrice}
              onChange={(e) => setMaxPrice(e.target.value.replace(/[^0-9]/g, ""))}
            />
            <select
              className="search-input"
              style={{ flex: 1, minWidth: 130 }}
              value={minRating}
              onChange={(e) => setMinRating(e.target.value)}
            >
              <option value="">할인도 무관</option>
              <option value="good">좋은 가격 이상</option>
              <option value="great">역대급만</option>
            </select>
            <button className="chip" onClick={handleAdd}>추가</button>
          </div>

          <ul style={{ listStyle: "none", padding: 0, marginTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
            {keywords.length === 0 && (
              <li style={{ color: "var(--text-3)", fontSize: 14 }}>아직 등록한 키워드가 없습니다.</li>
            )}
            {keywords.map((k) => (
              <li
                key={k.id}
                style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  border: "1px solid var(--border-2)", borderRadius: "var(--radius-sm)", padding: "8px 12px",
                }}
              >
                <span style={{ fontSize: 14 }}>
                  <strong>{k.keyword}</strong>
                  {k.max_price ? ` · ${k.max_price.toLocaleString("ko-KR")}원 이하` : ""}
                  {k.min_rating === "good" ? " · 좋은가격↑" : k.min_rating === "great" ? " · 역대급만" : ""}
                </span>
                <button className="chip" onClick={() => handleDelete(k.id)}>삭제</button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
