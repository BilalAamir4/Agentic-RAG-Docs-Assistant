"""Configuration and settings for ragdocs."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Literal["local", "production"] = Field(
        default="local",
        validation_alias=AliasChoices("RAGDOCS_ENV", "env"),
    )

    # API keys and credentials
    groq_api_key: SecretStr | None = None
    google_api_key: SecretStr | None = None
    cohere_api_key: SecretStr | None = None
    tavily_api_key: SecretStr | None = None
    upstash_redis_rest_url: SecretStr | None = None
    upstash_redis_rest_token: SecretStr | None = None

    # Model identifiers (set in M04/M05/M06/M07 after verifying current IDs;
    # never hardcode elsewhere)
    generator_model: str | None = None
    grader_model: str | None = None
    judge_model: str | None = None
    embedding_model: str | None = None
    rerank_model: str | None = None

    # Embeddings and retrieval parameters
    embedding_dim: int = 768
    dense_k: int = 20
    bm25_k: int = 20
    rrf_k: int = 60
    fused_k: int = 20
    rerank_top_n: int = 5
    final_k: int = 5

    # Application limits and guardrails
    max_question_chars: int = 500
    rate_limit_per_ip_per_hour: int = 20
    daily_global_cap: int = 300
    max_query_rewrites: int = 1
    max_regenerations: int = 1

    # Documentation corpus domain (set in M02)
    docs_domain: str = "docs.langchain.com"

    # Repository paths
    data_dir: Path = Field(default_factory=lambda: REPO_ROOT / "data")
    index_dir: Path = Field(default_factory=lambda: REPO_ROOT / "data" / "index")
    eval_path: Path = Field(default_factory=lambda: REPO_ROOT / "data" / "eval" / "eval_set.jsonl")
    results_dir: Path = Field(default_factory=lambda: REPO_ROOT / "results")
    cache_dir: Path = Field(default_factory=lambda: REPO_ROOT / "cache")

    def require(self, name: str) -> str:
        """Return the secret value or raise RuntimeError naming the missing env var."""
        attr_name = name.lower()
        if not hasattr(self, attr_name):
            raise RuntimeError(f"Missing required environment variable: {name.upper()}")

        val = getattr(self, attr_name)
        if val is None:
            raise RuntimeError(f"Missing required environment variable: {name.upper()}")

        if isinstance(val, SecretStr):
            secret_val = val.get_secret_value()
            if not secret_val:
                raise RuntimeError(f"Missing required environment variable: {name.upper()}")
            return secret_val

        str_val = str(val)
        if not str_val:
            raise RuntimeError(f"Missing required environment variable: {name.upper()}")
        return str_val


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
