"""
MemoraGraph Configuration

Loads all settings from environment variables with sensible defaults.
Uses pydantic-settings for validation and type coercion.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "MemoraGraph"
    app_version: str = "0.1.0"
    debug: bool = True

    # --- Backend Server ---
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    # --- PostgreSQL ---
    database_url: str = "postgresql+asyncpg://memoragraph:memoragraph@localhost:5432/memoragraph"

    # --- Neo4j ---
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "memoragraph"

    # --- Qdrant ---
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: Optional[str] = None
    qdrant_collection: str = "organizational_memory"

    # --- LLM Provider ---
    llm_provider: str = "openai"
    llm_api_key: Optional[str] = None
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2048

    # --- Embedding Model ---
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimension: int = 384

    # --- JWT Authentication ---
    jwt_secret: str = "change-this-to-a-random-secret-key"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 1440

    # --- File Storage ---
    upload_dir: str = "./data/documents"
    processed_dir: str = "./data/processed"

    # --- Logging ---
    log_level: str = "INFO"

    # --- Intent Classification Threshold ---
    intent_confidence_threshold: float = 0.5

    # --- Max Context Size ---
    max_context_tokens: int = 1500


# Singleton settings instance
settings = Settings()
