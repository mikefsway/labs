from functools import lru_cache
from urllib.parse import urlparse

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_service_key: str
    supabase_anon_key: str = ""
    openai_api_key: str
    labs_mcp_api_keys: str = ""
    clerk_publishable_key: str = ""
    clerk_secret_key: str = ""
    clerk_jwt_issuer_url: str = ""
    debug: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def clerk_frontend_api(self) -> str:
        if not self.clerk_jwt_issuer_url:
            return ""
        return urlparse(self.clerk_jwt_issuer_url).netloc


@lru_cache
def get_settings() -> Settings:
    return Settings()
