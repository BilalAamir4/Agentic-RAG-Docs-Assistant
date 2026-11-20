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
    tavily_api_key: SecretStr | None = None
    upstash_redis_rest_url: SecretStr | None = None
    upstash_redis_rest_token: SecretStr | None = None

    # LangSmith tracing (M07). Field names match the env vars read by langsmith 0.14.7
    # (langsmith/utils.py get_env_var). ragdocs.tracing.configure_tracing exports them.
    langsmith_api_key: SecretStr | None = None
    langsmith_tracing: bool = False
    langsmith_project: str = "ragdocs-local"
    # M09: LangSmith dataset holding the frozen eval set (experiments attach to it).
    langsmith_dataset_name: str = "ragdocs-eval-set-v1"
    langsmith_endpoint: str | None = None
    langsmith_sampling_rate: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        validation_alias=AliasChoices("LANGSMITH_TRACING_SAMPLING_RATE", "langsmith_sampling_rate"),
    )

    # Model identifiers (set in M04/M05/M06/M07 after verifying current IDs;
    # never hardcode elsewhere)
    generator_model: str = "openai/gpt-oss-120b"
    grader_model: str = "openai/gpt-oss-20b"
    # Judge (M08, D7/D9): gemini-3.5-flash-lite, structured_output True in
    # langchain-google-genai 4.4.1 data/_profiles.py; verified by a live call.
    judge_model: str | None = "gemini-3.5-flash-lite"
    judge_prompt_version: int = 2
    embedding_model: str = "gemini-embedding-001"
    rerank_model: str = "rerank-v3.5"
    use_reranker: bool = False

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
    # Self-RAG (M11): regenerations allowed per question after verify_answer rejects
    # an answer (D27 call bound).
    max_regenerations: int = 1
    # Structured output for Groq answer and grader calls (M08, D23). json_schema with
    # strict=True uses Groq constrained decoding (gpt-oss-20b and gpt-oss-120b only).
    structured_output_method: Literal["function_calling", "json_schema"] = "json_schema"
    structured_output_strict: bool | None = True
    # Error-message prefixes that mark a failed attempt as rate limiting, not a
    # structured-output failure (safe_error_message starts with the exception name).
    rate_limit_error_prefixes: list[str] = Field(default_factory=lambda: ["RateLimitError"])

    # Free-tier quotas (M08). Groq values from the human's org limits page
    # (console.groq.com/settings/limits, 2026-11-15, Free plan); Gemini judge values
    # from the human's AI Studio rate-limit page (2026-11-15). Daily maps are keyed by
    # model ID. Groq's daily limits behave as a bucket draining at limit / 24 h (D7: ten
    # 429 retry-after values match the formula); Google resets RPD at midnight Pacific.
    # Embedding limits from the human's AI Studio page, 1 Day view, 2026-11-16.
    groq_tpm_limit: int = 8000
    groq_rpm_limit: int = 30
    groq_rpd_limit: dict[str, int] = Field(
        default_factory=lambda: {"openai/gpt-oss-120b": 1000, "openai/gpt-oss-20b": 1000}
    )
    groq_tpd_limit: dict[str, int] = Field(
        default_factory=lambda: {"openai/gpt-oss-120b": 200000, "openai/gpt-oss-20b": 200000}
    )
    groq_quota_timezone: str = "UTC"
    groq_quota_window: Literal["token_bucket", "rolling_24h", "calendar_day"] = "token_bucket"
    # 429 backstop (D7): wait for the provider's retry-after, at most this long per
    # wait and this many waits per item, before pausing the run (exit code 3).
    rate_limit_default_wait_s: float = 60.0
    rate_limit_max_wait_s: float = 1800.0
    rate_limit_max_waits_per_item: int = 3
    # Daily-limit 429s while the budget model predicted room; at this many, pause and
    # revert groq_quota_window to rolling_24h (human rule, D7).
    budget_model_max_misses: int = 2
    judge_tpm_limit: int = 250000
    judge_rpm_limit: int = 15
    judge_rpd_limit: int = 500
    judge_quota_timezone: str = "America/Los_Angeles"
    embedding_tpm_limit: int = 30000
    embedding_rpm_limit: int = 100
    embedding_rpd_limit: int = 1000
    embedding_quota_timezone: str = "America/Los_Angeles"
    # RAGAS scorer (M09, D19): runs in .venv-ragas via tools/ragas_score.py. The LLM is a
    # different Gemini model from the judge so each has its own daily quota (D7).
    ragas_llm_model: str = "gemini-3.1-flash-lite"
    ragas_llm_rpm_limit: int = 15
    ragas_llm_tpm_limit: int = 250000
    ragas_llm_rpd_limit: int = 500
    ragas_llm_quota_timezone: str = "America/Los_Angeles"
    # None means embedding_model; embedding limits are shared (embedding_* above).
    ragas_embedding_model: str | None = None
    ragas_response_relevancy_strictness: int = 3
    # Total attempts per LLM or embedding call (ragas RunConfig); the chat model's own
    # retries are off so every attempt passes the budget recorder.
    ragas_max_attempts: int = 3
    ragas_timeout_s: int = 180
    # Ceiling on requests per minute for the RAGAS LLM and embeddings, applied before
    # every call (human decision after the day-1 bursts of 16 per minute, D19).
    ragas_rpm_ceiling: int = 12
    # LLM calls and embedding requests per scored item and metric, used for the budget
    # plan and the per-item daily check. From day 1 (2026-11-18, cached successes on 13
    # or 14 items, retries included; mean / max): faithfulness 2.46 / 6, response_relevancy
    # 4.67 / 6, context_precision 6.42 / 9, context_recall 1.46 / 3. 48 more requests went
    # to 10 errored metrics. Values: means rounded up, response_relevancy at its maximum.
    ragas_llm_calls_per_metric: dict[str, int] = Field(
        default_factory=lambda: {
            "faithfulness": 3,
            "response_relevancy": 6,
            "context_precision": 7,
            "context_recall": 2,
        }
    )
    ragas_embedding_requests_per_metric: dict[str, int] = Field(
        default_factory=lambda: {"response_relevancy": 2}
    )
    ragas_tokens_per_llm_call: int = 2500
    ragas_venv_dir: Path = Field(default_factory=lambda: REPO_ROOT / ".venv-ragas")
    throttle_safety: float = Field(default=0.9, gt=0.0, le=1.0)
    throttle_window_s: float = 60.0
    eval_initial_token_estimate: int = 3000
    eval_context_k: int = 5
    # Attempts per item (pipeline error event or judge exception) before pausing.
    eval_item_attempts: int = 2
    eval_audit_seed: int = 21
    eval_audit_strata: dict[str, int] = Field(
        default_factory=lambda: {"single": 6, "multi": 2, "version": 2}
    )
    # Judged items with correctness below this are added to the audit after the seeded
    # draw (stratification by judge score, D9). The gate is this agreement rate on each
    # column over all audited items.
    eval_audit_add_below_correctness: int = 2
    eval_audit_gate_rate: float = Field(default=0.8, gt=0.0, le=1.0)
    # D19 noise rule for paired comparisons (M09): a paired item is a win or loss when
    # the difference exceeds the threshold; a direction is reported only when wins minus
    # losses (or losses minus wins) reaches the margin.
    compare_paired_threshold: float = 0.2
    compare_noise_margin: int = 3
    eval_set_sha256: str = "316b1d683050e426ad5bf2324b9ca7211d30ea2566276320489e6acb538a470f"
    eval_set_tag: str = "eval-set-v1"

    # Documentation corpus domain (set in M02)
    docs_domain: str = "docs.langchain.com"
    # Corrective RAG (M10). Web search results per Tavily call (restricted to
    # docs_domain, D8); a retrieval is corrected when fewer than min_relevant_chunks
    # chunks pass the grader; max_query_rewrites (above) caps rewrites per question.
    web_max_results: int = 3
    min_relevant_chunks: int = 1
    # Tavily retries on 429 and 5xx: total attempts, and the first backoff in seconds
    # (doubled after each failed attempt: 1 s, 2 s).
    web_search_max_attempts: int = 3
    web_search_backoff_s: float = 1.0
    # Web result content kept per chunk, in characters (M10 S2; Tavily snippets measured
    # 988 to 1,128 characters in S1).
    web_text_max_chars: int = 1800

    # Repository paths
    data_dir: Path = Field(default_factory=lambda: REPO_ROOT / "data")
    index_dir: Path = Field(default_factory=lambda: REPO_ROOT / "data" / "index")
    eval_path: Path = Field(default_factory=lambda: REPO_ROOT / "data" / "eval" / "eval_set.jsonl")
    results_dir: Path = Field(default_factory=lambda: REPO_ROOT / "results")
    cache_dir: Path = Field(default_factory=lambda: REPO_ROOT / "cache")
    # Evidence-backed error-kind overrides for stored failed attempts (M11 S1), read
    # by ragdocs.eval.report from results_dir; a missing file means no overrides.
    error_reclassifications_file: str = "error_reclassifications.json"

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
