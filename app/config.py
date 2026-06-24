from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://app:devpassword@localhost:5432/polymarket"
    app_name: str = "Polymarket Smart Money Tracker"
    debug: bool = False
    discord_webhook_url: str = ""
    alert_poll_interval_seconds: int = 10

    model_config = {"env_file": ".env.app", "env_file_encoding": "utf-8"}


settings = Settings()
