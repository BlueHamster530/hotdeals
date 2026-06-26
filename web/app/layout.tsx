import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "핫딜 모아보기",
  description: "국내 커뮤니티 핫딜 통합 + 가격 분석",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <div className="container">
          <header className="site-header">
            <h1>
              <Link href="/" style={{ textDecoration: "none" }}>핫딜 모아보기</Link>
            </h1>
            <nav style={{ display: "flex", gap: 8 }}>
              <Link href="/chat">AI 챗봇</Link>
              <Link href="/settings">알림 설정</Link>
            </nav>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
