from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    llm_api_key: Optional[str] = Field(default=None, alias="LLM_API_KEY")
    llm_base_url: Optional[str] = Field(default=None, alias="LLM_BASE_URL")
    llm_chat_model: str = Field(default="gpt-4o-mini", alias="LLM_CHAT_MODEL")
    llm_embedding_model: str = Field(
        default="text-embedding-3-small",
        alias="LLM_EMBEDDING_MODEL",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @property
    def is_live_mode(self) -> bool:
        return bool(self.llm_api_key and self.llm_base_url)

    @property
    def runtime_mode_label(self) -> str:
        return "live" if self.is_live_mode else "mock"

    @property
    def masked_api_key(self) -> str:
        if not self.llm_api_key:
            return "not-set"
        if len(self.llm_api_key) <= 8:
            return "*" * len(self.llm_api_key)
        return f"{self.llm_api_key[:4]}...{self.llm_api_key[-4:]}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
