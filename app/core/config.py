from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Ops-Pilot"
    app_env: str = "development"
    debug: bool = True
    model_provider: str = "local"
    model_name: str = ""
    github_token: str = ""
    github_repository: str = ""
    github_api_url: str = "https://api.github.com"
    reviewer_max_files: int = 40
    reviewer_max_file_size: int = 120_000
    reviewer_max_context_chars: int = 400_000
    reviewer_max_findings: int = 50

    model_config = SettingsConfigDict(env_file=".env")


@lru_cache
def get_settings() -> Settings:
    return Settings()
