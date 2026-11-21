"""Dev-only probe: run the self_rag decide_retrieval node on every eval question (M11 S2).

Usage:
    .venv\\Scripts\\python scripts\\decide_probe.py [--limit N]

Inputs: data/eval/eval_set.jsonl (Settings.eval_path), the grader model (Settings.
grader_model, D23 structured-output method) and cache/budget.json.
Outputs: cache/decide_probe.jsonl, one line per question with id, category, needs_docs,
reason and fallback (null when the call succeeded), plus a printed summary. Each call
waits on the grader model's RollingBudget first and is recorded in cache/budget.json by
the budget recorder (D7). LangSmith tracing is switched off. Nothing in ragdocs imports
this script.
"""

import argparse
import sys
from pathlib import Path
from typing import Any

from ragdocs.config import get_settings
from ragdocs.eval.budget_recorder import install_budget_recorder
from ragdocs.eval.throttle import default_store, groq_budgets
from ragdocs.io_utils import read_jsonl, write_jsonl
from ragdocs.pipelines.agentic.graph import bind_structured
from ragdocs.pipelines.agentic.self_rag_nodes import decide_retrieval
from ragdocs.pipelines.agentic.state import AgenticDeps, RetrievalDecision, initial_state
from ragdocs.providers.llm import get_chat_model
from ragdocs.tracing import configure_tracing

OUTPUT_NAME = "decide_probe.jsonl"
# Token estimate for the first call; later calls use the largest call seen so far.
INITIAL_ESTIMATE_TOKENS = 800


def _model_tokens(recorder: Any, model: str) -> int:
    """Total tokens the recorder has seen for model so far."""
    usage = recorder.record().by_model.get(model)
    return usage.input_tokens + usage.output_tokens if usage else 0


def probe_one(item: dict[str, Any], deps: AgenticDeps) -> dict[str, Any]:
    """Run decide_retrieval on one eval item and return its output row."""
    update = decide_retrieval(initial_state(item["question"], "self_rag"), deps)
    event = [e for e in update["events"] if e.type == "decision"][0]
    return {
        "id": item["id"],
        "category": item["category"],
        "needs_docs": update["needs_docs"],
        "reason": event.data.get("reason"),
        "fallback": event.data.get("fallback"),
        "error_kind": event.data.get("error_kind"),
        "outcome": event.data["outcome"],
    }


def main() -> None:
    """Probe every eval question (or the first --limit) and write cache/decide_probe.jsonl."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=None, help="Probe only the first N items")
    args = parser.parse_args()

    settings = get_settings()
    configure_tracing(settings.model_copy(update={"langsmith_tracing": False}))
    recorder = install_budget_recorder(settings)
    model = settings.grader_model
    budget = groq_budgets(settings, default_store(settings))[model]
    decider = bind_structured(get_chat_model("grader", settings), RetrievalDecision, settings)
    deps = AgenticDeps(
        retriever=None, grader_llm=None, rewriter_llm=None, generator_llm=None,
        web_search=None, settings=settings, decider_llm=decider,
    )  # fmt: skip
    items = read_jsonl(settings.eval_path)[: args.limit]
    rows, per_call, estimate = [], [], INITIAL_ESTIMATE_TOKENS
    for item in items:
        budget.wait_for(estimate, 1)
        before = _model_tokens(recorder, model)
        row = probe_one(item, deps)
        tokens = _model_tokens(recorder, model) - before
        budget.record(tokens, 1, persist=False)  # the recorder already wrote the store
        row["tokens"] = tokens
        per_call.append(tokens)
        estimate = max(estimate, tokens)
        rows.append(row)
        print(f"{row['id']} {row['category']:<12} needs_docs={row['needs_docs']} "
              f"tokens={tokens} fallback={row['fallback']} reason={row['reason']!r}")  # fmt: skip
    write_jsonl(Path(settings.cache_dir) / OUTPUT_NAME, rows)
    biggest = max(per_call, default=0)
    print(f"\n{len(rows)} calls, {sum(per_call)} tokens (max {biggest}) on {model}")
    print("needs_docs false:", [r["id"] for r in rows if not r["needs_docs"]])
    print("fallbacks:", [(r["id"], r["fallback"]) for r in rows if r["fallback"]])


if __name__ == "__main__":
    main()
