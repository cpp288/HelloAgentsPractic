from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Agent 层配置，来源：环境变量 > .env。"""

    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_timeout: int = 60
    llm_mock: bool = False

    amap_api_key: str = ""
    amap_rest_base: str = "https://restapi.amap.com"

    internal_token: str = "dev-internal-token"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def use_mock_llm(self) -> bool:
        return self.llm_mock or not self.llm_api_key.strip()

    @property
    def use_mock_tools(self) -> bool:
        return not self.amap_api_key.strip()


@lru_cache
def get_settings() -> Settings:
    return Settings()
