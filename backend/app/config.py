from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "CodefyUI-OJ"
    debug: bool = Field(default=False)

    api_prefix: str = "/api"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    database_url: str = Field(default="sqlite+aiosqlite:///./oj.db")

    redis_url: str = Field(default="redis://localhost:6379/0")

    jwt_secret: str = Field(default="dev-only-secret-please-override-in-production-32b+")
    jwt_lifetime_seconds: int = 60 * 60 * 24 * 7

    storage_root: Path = Field(default=Path("./storage"))
    submissions_dir: Path = Field(default=Path("./storage/submissions"))
    problem_assets_dir: Path = Field(default=Path("./storage/problem_assets"))
    test_data_dir: Path = Field(default=Path("./storage/test_data"))

    judge_timeout_seconds: int = 90
    judge_use_docker: bool = False
    sandbox_image: str = "codefyui-oj-sandbox:latest"
    cdui_repo_path: Path = Field(default=Path("../CodefyUI"))

    submission_max_bytes: int = 1_000_000
    submission_rate_per_minute: int = 6


@lru_cache
def get_settings() -> Settings:
    return Settings()
