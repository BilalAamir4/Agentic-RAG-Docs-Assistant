"""LangSmith dataset sync and experiment upload by replay (M09, D18). Offline only.

Verified against langsmith 0.14.7 (.venv\\Lib\\site-packages\\langsmith):
- Client.has_dataset / read_dataset / create_dataset / list_examples / create_examples
  (examples as dicts with inputs, outputs, metadata), client.py lines 5831 to 7396.
- evaluation.evaluate(target, data=..., evaluators=..., experiment=TracerSession, ...):
  an existing TracerSession keeps its exact name (_runner.py line 1285); a string
  gets a random suffix. Evaluators return {"results": [{"key", "score"}, ...]}.
  The comparison URL is <base>/datasets/<dataset id>/compare?selectedSessions=<id>
  (_runner.py line 1372).
No model is called: the target returns stored outputs and the evaluator returns
stored scores. Never deletes anything in LangSmith.
"""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ragdocs.config import Settings
from ragdocs.eval.judge import load_records
from ragdocs.eval.scoring import effective_verdicts
from ragdocs.io_utils import read_json, read_jsonl, write_json
from ragdocs.schemas import EvalItem, EvalRecord, JudgeVerdict

EXPERIMENT_LOG = "langsmith_experiment.json"
RAGAS_SCORES_FILE = "ragas_scores.jsonl"
RAGAS_CONFIG_FILE = "ragas_config.json"
RAGAS_FEEDBACK_KEYS = ("faithfulness", "response_relevancy", "context_precision", "context_recall")


class DatasetMismatch(RuntimeError):
    """The existing LangSmith dataset does not match the frozen eval set."""


class AlreadyUploaded(RuntimeError):
    """The run already has an experiment; pass replace=True to upload a new one."""


def dataset_description(sha256: str) -> str:
    """Dataset description carrying the eval set hash (checked on every sync)."""
    return f"ragdocs eval set v1 (50 items). eval_set sha256 {sha256}"


def example_payloads(items: list[EvalItem]) -> list[dict[str, Any]]:
    """One LangSmith example per eval item."""
    return [
        {
            "inputs": {"question": i.question},
            "outputs": {"reference_answer": i.reference_answer},
            "metadata": {
                "id": i.id,
                "category": i.category,
                "must_mention": i.must_mention,
                "evidence": [e.model_dump() for e in i.evidence],
            },
        }
        for i in items
    ]


def sync_dataset(client: Any, name: str, items: list[EvalItem], sha256: str) -> tuple[Any, bool]:
    """Create the dataset with every item, or verify an existing one; return (dataset, created).

    An existing dataset must carry the same sha256 in its description and exactly the
    same example ids; otherwise DatasetMismatch is raised and nothing is written.
    """
    if client.has_dataset(dataset_name=name):
        dataset = client.read_dataset(dataset_name=name)
        if sha256 not in (dataset.description or ""):
            raise DatasetMismatch(f"{name}: description lacks eval_set sha256 {sha256}")
        ids = sorted(
            (e.metadata or {}).get("id") for e in client.list_examples(dataset_id=dataset.id)
        )
        expected = sorted(i.id for i in items)
        if ids != expected:
            raise DatasetMismatch(f"{name}: {len(ids)} example ids differ from the eval set")
        return dataset, False
    dataset = client.create_dataset(name, description=dataset_description(sha256))
    client.create_examples(dataset_id=dataset.id, examples=example_payloads(items))
    return dataset, True


def _num(value: Any) -> float | None:
    """Numeric feedback value; booleans become 1 or 0; None stays None."""
    if value is None:
        return None
    return float(value)


def item_feedback(
    record: EvalRecord, verdict: JudgeVerdict | None, ragas: dict[str, Any] | None
) -> dict[str, float]:
    """Every stored score of one item as {feedback key: score}; missing scores are omitted.

    correctness follows the report rule: an abstained answerable item counts as 0.
    """
    s = record.scores
    answerable = record.category != "unanswerable"
    correctness = verdict.correctness if verdict else None
    if answerable and s.abstained:
        correctness = 0
    values: dict[str, Any] = {
        "correctness": correctness if answerable else None,
        "citation_support": verdict.citation_support if verdict else None,
        "abstention_correct": s.abstention_correct,
        "hallucinated": s.hallucinated,
        "context_hit_at_5": s.context_hit_at_5,
        "context_evidence_recall_at_5": s.context_evidence_recall_at_5,
        "must_mention_coverage": s.must_mention_coverage,
        "llm_calls": s.llm_calls,
        "latency_ms": s.latency_ms,
        "tokens": s.tokens_in + s.tokens_out,
    }
    for key in RAGAS_FEEDBACK_KEYS:
        values[key] = (ragas or {}).get(key)
    return {k: v for k, v in ((k, _num(v)) for k, v in values.items()) if v is not None}


def item_outputs(record: EvalRecord) -> dict[str, Any]:
    """Stored answer as experiment outputs."""
    answer = record.result.answer
    return {
        "answer": answer.text,
        "abstained": answer.abstained,
        "citations": [c.chunk_id for c in answer.citations],
        "original_langsmith_run_id": record.langsmith_run_id,
    }


def build_payload(run_dir: Path) -> dict[str, dict[str, Any]]:
    """Per item id: outputs, feedback and metadata, from stored run files only."""
    records = load_records(run_dir)
    ev = effective_verdicts(run_dir, records)
    ragas_path = Path(run_dir) / RAGAS_SCORES_FILE
    ragas = {r["id"]: r for r in read_jsonl(ragas_path)} if ragas_path.is_file() else {}
    return {
        r.id: {
            "outputs": item_outputs(r),
            "feedback": item_feedback(r, ev.verdicts.get(r.id), ragas.get(r.id)),
            "metadata": {"id": r.id, "original_langsmith_run_id": r.langsmith_run_id},
        }
        for r in records
    }


def experiment_metadata(run_dir: Path) -> dict[str, Any]:
    """Pipeline, git commit, models, judge prompt version and ragas version of a run."""
    config = read_json(Path(run_dir) / "config.json")
    records = load_records(run_dir)
    ev = effective_verdicts(run_dir, records)
    ragas_cfg_path = Path(run_dir) / RAGAS_CONFIG_FILE
    ragas_cfg = read_json(ragas_cfg_path) if ragas_cfg_path.is_file() else {}
    return {
        "pipeline": config["pipeline"],
        "git_commit": config["git_commit"],
        "models": config["model_ids"],
        "judge_model": ev.judge_model,
        "judge_prompt_version": ev.prompt_version,
        "ragas_version": ragas_cfg.get("ragas_version"),
        "ragas_llm_model": ragas_cfg.get("llm_model"),
        "run_dir": Path(run_dir).as_posix(),
    }


def read_log(run_dir: Path) -> dict[str, Any]:
    """The run's append-only upload log ({"uploads": [...]}), empty when missing."""
    path = Path(run_dir) / EXPERIMENT_LOG
    return read_json(path) if path.is_file() else {"uploads": []}


def next_experiment_name(run_dir: Path, log: dict[str, Any], replace: bool) -> str:
    """Run folder name for the first upload; <run>-r<N> for the N-th replacement."""
    base = Path(run_dir).name
    n = len(log["uploads"])
    if n and not replace:
        raise AlreadyUploaded(f"{base} already has experiment {log['uploads'][-1]['name']}")
    return base if n == 0 else f"{base}-r{n}"


def comparison_url(project: Any, dataset_id: Any) -> str | None:
    """LangSmith comparison-view URL, built as langsmith's own runner prints it."""
    if not getattr(project, "url", None):
        return None
    base = project.url.split("?")[0].split("/projects/p/")[0]
    return f"{base}/datasets/{dataset_id}/compare?selectedSessions={project.id}"


def _replay_functions(payload: dict[str, dict[str, Any]], examples: list[Any]) -> tuple:
    """Target returning stored outputs and evaluator returning stored scores."""
    from langsmith import run_helpers

    by_question = {e.inputs["question"]: (e.metadata or {})["id"] for e in examples}

    def target(inputs: dict[str, Any]) -> dict[str, Any]:
        item = payload[by_question[inputs["question"]]]
        run = run_helpers.get_current_run_tree()
        if run is not None:
            run.metadata.update(item["metadata"])
        return item["outputs"]

    def stored_scores(run: Any, example: Any) -> dict[str, Any]:
        feedback = payload[(example.metadata or {})["id"]]["feedback"]
        return {"results": [{"key": k, "score": v} for k, v in feedback.items()]}

    return target, stored_scores


def upload_experiment(
    client: Any,
    run_dir: Path,
    dataset: Any,
    *,
    replace: bool = False,
    evaluate_fn: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Upload a run as an experiment on dataset; append it to the log; return the entry."""
    log = read_log(run_dir)
    name = next_experiment_name(run_dir, log, replace)
    payload = build_payload(run_dir)
    examples = list(client.list_examples(dataset_id=dataset.id))
    if sorted((e.metadata or {}).get("id") for e in examples) != sorted(payload):
        raise DatasetMismatch("dataset example ids differ from the run's items")
    meta = experiment_metadata(run_dir)
    project = client.create_project(
        name, reference_dataset_id=dataset.id, metadata=meta, description=f"Replay of {name}"
    )
    if evaluate_fn is None:
        from langsmith.evaluation import evaluate as evaluate_fn
    target, stored_scores = _replay_functions(payload, examples)
    evaluate_fn(
        target,
        data=examples,
        evaluators=[stored_scores],
        experiment=project,
        client=client,
        max_concurrency=0,
        metadata=meta,
    )
    entry = {
        "name": name,
        "id": str(project.id),
        "url": comparison_url(project, dataset.id),
        "dataset_id": str(dataset.id),
        "examples": len(examples),
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "current": True,
    }
    for old in log["uploads"]:
        old["current"] = False
    log["uploads"].append(entry)
    write_json(Path(run_dir) / EXPERIMENT_LOG, log)
    return entry


def make_client(settings: Settings) -> Any:
    """LangSmith client from Settings (the key is never printed)."""
    from langsmith import Client

    key = settings.require("LANGSMITH_API_KEY")
    return Client(api_key=key, api_url=settings.langsmith_endpoint or None)


def payload_json(payload: dict[str, dict[str, Any]]) -> str:
    """Stable JSON of a payload (for tests and dry runs)."""
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)
