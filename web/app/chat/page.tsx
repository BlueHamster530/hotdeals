"use client";

// AI 챗봇 UI. 백엔드 /api/chat 에 대화 이력을 보내고 답변을 받는다.

import { useEffect, useRef, useState } from "react";
import { ChatMessage, chatStatus, sendChat } from "@/lib/api";

const SUGGESTIONS = [
  "콜라 핫딜 중에 역대최저인 거 있어?",
  "전자기기 카테고리에서 좋은 가격 딜 보여줘",
  "지금 살 만한 제로음료 특가 있어?",
];

export default function ChatPage() {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatStatus().then(setEnabled);
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function send(text: string) {
    const content = text.trim();
    if (!content || loading) return;
    const next: ChatMessage[] = [...messages, { role: "user", content }];
    setMessages(next);
    setInput("");
    setLoading(true);
    setError(null);
    try {
      const reply = await sendChat(next);
      setMessages([...next, { role: "assistant", content: reply }]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  if (enabled === false) {
    return (
      <main>
        <h2 style={{ fontSize: 18, fontWeight: 600 }}>AI 챗봇</h2>
        <p style={{ color: "var(--text-2)" }}>
          현재 AI 챗봇 기능은 비활성화되어 있습니다.
        </p>
      </main>
    );
  }

  return (
    <main>
      <h2 style={{ fontSize: 18, fontWeight: 600 }}>AI 챗봇</h2>
      <p style={{ color: "var(--text-2)", fontSize: 14 }}>
        실제 수집된 핫딜 데이터를 바탕으로 답해드려요. 자연어로 물어보세요.
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: 12, margin: "16px 0" }}>
        {messages.length === 0 && (
          <div className="chips">
            {SUGGESTIONS.map((s) => (
              <button key={s} className="chip" onClick={() => send(s)}>
                {s}
              </button>
            ))}
          </div>
        )}

        {messages.map((m, i) => (
          <div
            key={i}
            style={{
              alignSelf: m.role === "user" ? "flex-end" : "flex-start",
              maxWidth: "85%",
              background: m.role === "user" ? "var(--text)" : "var(--surface)",
              color: m.role === "user" ? "var(--bg-page)" : "var(--text)",
              border: m.role === "user" ? "none" : "1px solid var(--border-2)",
              borderRadius: "var(--radius)",
              padding: "10px 14px",
              fontSize: 15,
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
            }}
          >
            {m.content}
          </div>
        ))}

        {loading && (
          <div style={{ alignSelf: "flex-start", color: "var(--text-3)", fontSize: 14 }}>
            생각하는 중…
          </div>
        )}
        {error && <div style={{ color: "#A32D2D", fontSize: 14 }}>오류: {error}</div>}
        <div ref={endRef} />
      </div>

      <div style={{ display: "flex", gap: 8, position: "sticky", bottom: 0, paddingBottom: 8, background: "var(--bg-page)" }}>
        <input
          className="search-input"
          style={{ flex: 1 }}
          placeholder="메시지를 입력하세요"
          value={input}
          disabled={loading || enabled === null}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send(input)}
        />
        <button className="chip" onClick={() => send(input)} disabled={loading || !input.trim()}>
          전송
        </button>
      </div>
    </main>
  );
}
