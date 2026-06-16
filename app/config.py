from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://app:devpassword@localhost:5432/polymarket"
    redis_url: str = "redis://localhost:6379/0"
    app_name: str = "Polymarket Smart Money Tracker"
    debug: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
