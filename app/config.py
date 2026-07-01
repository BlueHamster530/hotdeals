from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_user: str = "hotdeals"
    postgres_password: str = "change-me-in-prod"
    postgres_db: str = "hotdeals"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    ingest_interval_seconds: int = 600
    http_user_agent: str = "hotdeals-bot/0.1 (personal hotdeal aggregator)"

    # 이미지 프록시 디스크 캐시 위치(볼륨). 한 번 받은 썸네일은 우리 서버에서 서빙.
    img_cache_dir: str = "/cache"

    # CORS 허용 출처(쉼표 구분). 운영에선 실제 도메인으로. 개발 기본값은 로컬 Next.
    web_origin: str = "http://localhost:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.web_origin.split(",") if o.strip()]

    # 텔레그램 봇 (선택). 미설정이면 알림 기능 비활성.
    telegram_bot_token: str = ""
    telegram_bot_username: str = ""  # 예: hotdeals_alert_bot (프론트 안내용)

    # AI 챗봇 (선택, Google Gemini). 미설정이면 챗봇 비활성.
    # 무료 티어 키: https://aistudio.google.com/apikey
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    # 챗봇 전체 스위치. False면 키가 있어도 챗봇을 끈다(현재 품질 이슈로 비활성).
    chatbot_enabled: bool = False

    @property
    def database_url(self) -> str:
        # SQLAlchemy async 드라이버(asyncpg)용 URL
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
