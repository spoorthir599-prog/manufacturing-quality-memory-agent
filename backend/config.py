from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Azure OpenAI
    azure_openai_endpoint: Optional[str] = None
    azure_openai_api_key: Optional[str] = None
    azure_openai_deployment_name: str = "gpt-4o"
    azure_openai_embedding_deployment: str = "text-embedding-ada-002"
    azure_openai_api_version: str = "2024-02-01"

    # Database
    database_url: str = "sqlite:///./quality_memory.db"

    # App
    app_env: str = "development"
    ai_provider: str = "azure"  # azure | local
    search_provider: str = "local"
    log_level: str = "INFO"

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def azure_available(self) -> bool:
        return bool(self.azure_openai_endpoint and self.azure_openai_api_key)

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
