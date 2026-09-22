from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Ops-Pilot"
    app_env: str = "development"
    debug: bool = True
    model_provider: str = "local"
    model_name: str = ""

    model_config = SettingsConfigDict(env_file=".env")


@lru_cache
def get_settings() -> Settings:
    return Settings()
