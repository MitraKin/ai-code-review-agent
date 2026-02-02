from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )
    
    # OpenAI
    openai_api_key: str = Field(alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4-turbo-preview", alias="OPENAI_MODEL")
    
    # GitHub
    github_token: Optional[str] = Field(default=None, alias="GITHUB_TOKEN")
    github_app_id: Optional[str] = Field(default=None, alias="GITHUB_APP_ID")
    github_private_key_path: Optional[str] = Field(default=None, alias="GITHUB_PRIVATE_KEY_PATH")
    github_webhook_secret: Optional[str] = Field(default=None, alias="GITHUB_WEBHOOK_SECRET")
    
    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://localhost:5432/code_review_db",
        alias="DATABASE_URL"
    )
    
    # ChromaDB
    chroma_persist_directory: str = Field(
        default="./chroma_data",
        alias="CHROMA_PERSIST_DIRECTORY"
    )
    
    # Application
    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
