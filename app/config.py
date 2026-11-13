"""Settings read from environment variables (see .env.example)."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./sprint_planner.db")
    secret_key: str = os.getenv("SECRET_KEY", "dev-only-insecure-key-change-me-in-production")
    token_minutes: int = int(os.getenv("ACCESS_TOKEN_MINUTES", "60"))
    bcrypt_rounds: int = int(os.getenv("BCRYPT_ROUNDS", "12"))
    algorithm: str = "HS256"


settings = Settings()
