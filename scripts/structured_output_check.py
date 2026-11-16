"""Compare Groq structured-output methods on real eval questions (M08, D23).

Usage:
    .venv\\Scripts\\python scripts\\structured_output_check.py [--ids q015,q028,...]

For each eval item, retrieves contexts once (one query embedding), builds the shared
answer prompt, and calls the generator once with method="function_calling" and once
with method="json_schema", strict=True, alternating which goes first. A call counts as
a failure when it raises (for example Groq 400 tool_use_failed) or does not return an
AnswerDraft. Calls are throttled with the eval budgets and recorded in cache/budget.json.

Inputs: data/eval/eval_set.jsonl, data/index/, .env (GROQ_API_KEY, GOOGLE_API_KEY).
Output: results/structured_output_check-YYYYMMDD.json with every call's outcome, and
a printed failure count per method.
"""

import argparse
import sys
from datetime import UTC, datetime
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from ragdocs.config import get_settings
from ragdocs.eval.budget_recorder import install_budget_recorder
from ragdocs.eval.runner import load_eval_items
from ragdocs.eval.throttle import default_store, groq_budgets
from ragdocs.generation.answer import AnswerDraft, build_structured_llm, format_context
from ragdocs.generation.prompts import ANSWER_SYSTEM_PROMPT, ANSWER_USER_TEMPLATE
from ragdocs.io_utils import write_json
from ragdocs.pipelines.base import safe_error_message
from ragdocs.providers.llm import get_chat_model
from ragdocs.providers.usage import TokenUsage
from ragdocs.retrieval.retriever import get_retriever

DEFAULT_IDS = "q015,q028,q001,q002,q003,q004,q005,q006,q007,q008"
METHODS: dict[str, dict[str, Any]] = {
    "function_calling": {"method": "function_calling", "strict": None},
    "json_schema_strict": {"method": "json_schema", "strict": True},
}


def _call(llm: Any, messages: list[Any], budget: Any, est_tokens: int) -> dict[str, Any]:
    """Invoke once under the budget; return outcome, error and token usage."""
    budget.wait_for(est_tokens, 1)
    usage = TokenUsage()
    outcome: dict[str, Any] = {"ok": False, "error": None}
    try:
        draft = llm.invoke(messages, config={"callbacks": [usage]})
        outcome["ok"] = isinstance(draft, AnswerDraft)
        if not outcome["ok"]:
            outcome["error"] = f"unexpected output type {type(draft).__name__}"
        else:
            outcome["abstain"] = draft.abstain
            outcome["cited"] = draft.cited
    except Exception as exc:  # every provider or parsing error counts as a failure
        outcome["error"] = safe_error_message(exc)[:300]
    rec = usage.record()
    # Per-minute window only; the installed BudgetRecorder persists every call.
    budget.record(
        rec.tokens_in + rec.tokens_out,
        max(sum(u.calls for u in rec.by_model.values()), 1),
        persist=False,
    )
    outcome["tokens"] = rec.tokens_in + rec.tokens_out
    return outcome


def main() -> int:
    """Run the comparison and write the results file."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ids", default=DEFAULT_IDS, help="Comma-separated eval item ids")
    args = parser.parse_args()
    settings = get_settings()
    ids = args.ids.split(",")
    items = {i.id: i for i in load_eval_items(settings)}
    chat_model = get_chat_model("generator", settings)
    llms = {name: build_structured_llm(chat_model, **kw) for name, kw in METHODS.items()}
    install_budget_recorder(settings)
    budget = groq_budgets(settings, default_store(settings))[settings.generator_model]
    retriever = get_retriever()
    calls: list[dict[str, Any]] = []
    for n, item_id in enumerate(ids):
        item = items[item_id]
        chunks = retriever.retrieve(item.question)
        messages = [
            SystemMessage(content=ANSWER_SYSTEM_PROMPT),
            HumanMessage(
                content=ANSWER_USER_TEMPLATE.format(
                    question=item.question, context=format_context(chunks)
                )
            ),
        ]
        order = list(METHODS) if n % 2 == 0 else list(reversed(METHODS))
        for name in order:
            outcome = _call(llms[name], messages, budget, settings.eval_initial_token_estimate)
            calls.append({"id": item_id, "method": name, **outcome})
            print(f"{item_id} {name}: {'ok' if outcome['ok'] else 'FAIL ' + str(outcome['error'])}")
    failures = {m: sum(1 for c in calls if c["method"] == m and not c["ok"]) for m in METHODS}
    out = settings.results_dir / f"structured_output_check-{datetime.now(UTC):%Y%m%d}.json"
    write_json(
        out,
        {
            "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "generator_model": settings.generator_model,
            "ids": ids,
            "failures": failures,
            "calls_per_method": len(ids),
            "calls": calls,
        },
    )
    for m, f in failures.items():
        print(f"{m}: {f}/{len(ids)} failed")
    print(f"Wrote {out.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
