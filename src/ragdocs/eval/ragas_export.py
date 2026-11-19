"""Project stored eval records into the RAGAS handoff file (M09, D19).

The RAGAS scorer runs in a separate venv (tools/ragas_score.py, D19 path A) and never
imports ragdocs, so this module writes everything it needs into <run>/ragas_input.jsonl:
one line per eval item with the RAGAS sample fields and per-metric eligibility flags.

Population rules (D19): unanswerable items are never scored; faithfulness and response
relevancy need an answer that did not abstain; context precision and context recall
need at least one context. Contexts keep the order the generator saw them.
"""

import json
from pathlib import Path
from typing import Any

from ragdocs.eval.judge import load_records
from ragdocs.io_utils import read_text, write_jsonl
from ragdocs.schemas import EvalRecord

RAGAS_INPUT_FILE = "ragas_input.jsonl"
RAGAS_METRICS = ("faithfulness", "response_relevancy", "context_precision", "context_recall")
INPUT_FIELDS = (
    "id",
    "category",
    "user_input",
    "response",
    "retrieved_contexts",
    "reference",
    "eligible",
)


def eligibility(record: EvalRecord) -> dict[str, bool]:
    """Per-metric eligibility for one record (D19 population rules)."""
    answerable = record.category != "unanswerable"
    answered = answerable and not record.result.answer.abstained
    has_contexts = answerable and len(record.context_texts) > 0
    return {
        "faithfulness": answered,
        "response_relevancy": answered,
        "context_precision": has_contexts,
        "context_recall": has_contexts,
    }


def to_ragas_row(record: EvalRecord) -> dict[str, Any]:
    """Project one record onto the RAGAS single-turn sample fields plus eligibility."""
    row = {
        "id": record.id,
        "category": record.category,
        "user_input": record.question,
        "response": record.result.answer.text,
        "retrieved_contexts": list(record.context_texts),
        "reference": record.reference_answer,
        "eligible": eligibility(record),
    }
    return {key: row[key] for key in INPUT_FIELDS}


def build_ragas_input(records: list[EvalRecord]) -> list[dict[str, Any]]:
    """Return handoff rows for every record, in the order given."""
    return [to_ragas_row(r) for r in records]


def export_ragas_input(run_dir: Path) -> tuple[Path, list[dict[str, Any]]]:
    """Write <run>/ragas_input.jsonl from per_question.jsonl and return (path, rows).

    The file is derived data: it is written when missing and left alone when an
    identical file exists; a different existing file raises FileExistsError, since run
    files are never modified.
    """
    rows = build_ragas_input(load_records(run_dir))
    path = Path(run_dir) / RAGAS_INPUT_FILE
    tmp = path.with_suffix(".jsonl.tmp")
    write_jsonl(tmp, rows)
    if path.is_file():
        same = read_text(path) == read_text(tmp)
        tmp.unlink()
        if not same:
            raise FileExistsError(f"{path} exists with different content; not overwriting")
        return path, rows
    tmp.replace(path)
    return path, rows


RAGAS_TOOL = "tools/ragas_score.py"
RAGAS_CACHE_SUBDIR = "ragas"
RAGAS_ERROR_LOG = "ragas_errors.jsonl"
RAGAS_PARTIAL_SUBDIR = "ragas_partial"
RAGAS_FAITHFULNESS_AUDIT = "ragas_faithfulness_audit.jsonl"


def ragas_python(settings: Any) -> Path:
    """Path of the .venv-ragas interpreter (Windows or POSIX layout)."""
    venv = Path(settings.ragas_venv_dir)
    win = venv / "Scripts" / "python.exe"
    return win if win.exists() else venv / "bin" / "python"


def ragas_tool_args(
    settings: Any, input_path: Path, out_dir: Path, git_commit: str = ""
) -> list[str]:
    """Command-line arguments for tools/ragas_score.py, all taken from Settings."""
    emb_model = settings.ragas_embedding_model or settings.embedding_model
    return [
        "--input", Path(input_path).as_posix(),
        "--out-dir", Path(out_dir).as_posix(),
        "--budget-file", (Path(settings.cache_dir) / "budget.json").as_posix(),
        "--cache-dir", (Path(settings.cache_dir) / RAGAS_CACHE_SUBDIR).as_posix(),
        "--llm-model", str(settings.ragas_llm_model),
        "--embedding-model", str(emb_model),
        "--llm-limits",
        f"{settings.ragas_llm_rpm_limit},{settings.ragas_llm_tpm_limit},"
        f"{settings.ragas_llm_rpd_limit}",
        "--embedding-limits",
        f"{settings.embedding_rpm_limit},{settings.embedding_tpm_limit},"
        f"{settings.embedding_rpd_limit}",
        "--timezone", str(settings.ragas_llm_quota_timezone),
        "--safety", str(settings.throttle_safety),
        "--window-s", str(settings.throttle_window_s),
        "--strictness", str(settings.ragas_response_relevancy_strictness),
        "--max-attempts", str(settings.ragas_max_attempts),
        "--timeout-s", str(settings.ragas_timeout_s),
        "--llm-calls", json.dumps(settings.ragas_llm_calls_per_metric),
        "--embedding-requests", json.dumps(settings.ragas_embedding_requests_per_metric),
        "--tokens-per-call", str(settings.ragas_tokens_per_llm_call),
        "--rpm-ceiling", str(settings.ragas_rpm_ceiling),
        "--error-log", (Path(settings.cache_dir) / RAGAS_ERROR_LOG).as_posix(),
        "--partial-dir",
        (Path(settings.cache_dir) / RAGAS_PARTIAL_SUBDIR / Path(out_dir).name).as_posix(),
        "--git-commit", git_commit,
    ]  # fmt: skip


def ragas_tool_env(settings: Any, base: dict[str, str]) -> dict[str, str]:
    """Environment for the scorer: no LangSmith or LangChain variables, the Gemini key set.

    The key is read through Settings (AGENTS.md) and passed only in the child's
    environment, never on the command line or in a file.
    """
    env = {k: v for k, v in base.items() if not k.upper().startswith(("LANGSMITH", "LANGCHAIN"))}
    env["GOOGLE_API_KEY"] = settings.require("GOOGLE_API_KEY")
    env["PYTHONIOENCODING"] = "utf-8"
    return env
