/** @type {import('next').NextConfig} */
// 썸네일은 여러 커뮤니티 CDN에서 오므로 next/image 대신 <img>를 쓴다(도메인 화이트리스트 불필요).
const nextConfig = {
  reactStrictMode: true,
  // Docker 운영 이미지용 독립 실행 빌드(.next/standalone)
  output: "standalone",
};

module.exports = nextConfig;
