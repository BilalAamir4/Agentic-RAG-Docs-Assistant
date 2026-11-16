"""Pipeline registry and process-level lazy singleton factory."""

from ragdocs.pipelines.base import Pipeline

_PIPELINES: dict[str, Pipeline] = {}


def list_pipelines() -> list[str]:
    """Return sorted list of supported pipeline names."""
    return ["baseline"]


def get_pipeline(name: str) -> Pipeline:
    """Return pipeline instance by name, constructing heavy objects lazily once per process.

    Args:
        name: Name of the pipeline (e.g. 'baseline').

    Returns:
        The requested Pipeline instance.

    Raises:
        ValueError: If pipeline name is not recognized, listing valid names.
    """
    valid = list_pipelines()
    if name not in valid:
        valid_str = ", ".join(repr(p) for p in valid)
        raise ValueError(f"Unknown pipeline {name!r}. Valid pipeline names: [{valid_str}].")

    if name not in _PIPELINES:
        if name == "baseline":
            from ragdocs.generation.answer import build_structured_llm
            from ragdocs.pipelines.baseline import BaselinePipeline
            from ragdocs.providers.llm import get_chat_model
            from ragdocs.retrieval.retriever import get_retriever

            retriever = get_retriever()
            chat_model = get_chat_model("generator")
            from ragdocs.config import get_settings

            settings = get_settings()
            structured_llm = build_structured_llm(
                chat_model,
                method=settings.structured_output_method,
                strict=settings.structured_output_strict,
            )
            _PIPELINES[name] = BaselinePipeline(
                retriever=retriever,
                structured_llm=structured_llm,
                name="baseline",
            )

    return _PIPELINES[name]


def clear_pipeline_cache() -> None:
    """Clear cached pipeline instances for testing."""
    _PIPELINES.clear()
