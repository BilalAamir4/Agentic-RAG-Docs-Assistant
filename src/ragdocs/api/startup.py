"""Startup validation of runtime settings (called from the app lifespan)."""

import logging

from ragdocs.config import Settings

logger = logging.getLogger(__name__)

# D18: production tracing needs a sampling rate at or below this value.
MAX_PRODUCTION_SAMPLING_RATE = 0.1

REQUIRED_KEYS = ("GROQ_API_KEY", "GOOGLE_API_KEY", "TAVILY_API_KEY", "IP_HASH_SALT")
UPSTASH_KEYS = ("UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN")


def _is_missing(settings: Settings, env_name: str) -> bool:
    value = getattr(settings, env_name.lower())
    if value is None:
        return True
    return not (value.get_secret_value() if hasattr(value, "get_secret_value") else str(value))


def validate_runtime_settings(settings: Settings) -> None:
    """Raise RuntimeError in production for unsafe settings; warn locally.

    Messages name settings, never values. IP_HASH_SALT is required too: without it the rate-limit
    keys would be unsalted hashes of client IPs. COHERE_API_KEY is not checked: the API runs
    with use_reranker False.
    """
    missing = [n for n in (*UPSTASH_KEYS, *REQUIRED_KEYS) if _is_missing(settings, n)]
    problems = [f"{n} is missing" for n in missing]
    if (
        settings.langsmith_tracing
        and settings.langsmith_sampling_rate > MAX_PRODUCTION_SAMPLING_RATE
    ):
        problems.append(
            f"LANGSMITH_TRACING_SAMPLING_RATE must be {MAX_PRODUCTION_SAMPLING_RATE} or lower "
            "when tracing is enabled (D18)"
        )
    if settings.env == "production":
        if problems:
            raise RuntimeError("Invalid production settings: " + "; ".join(problems) + ".")
        return
    for name in missing:
        logger.warning("%s is not set.", name)
