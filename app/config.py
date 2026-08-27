from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://app:devpassword@localhost:5432/polymarket"
    app_name: str = "Polymarket Smart Money Tracker"
    debug: bool = False
    discord_webhook_url: str = ""
    alert_poll_interval_seconds: int = 10
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    api_key: str

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()  # type: ignore[call-arg]
