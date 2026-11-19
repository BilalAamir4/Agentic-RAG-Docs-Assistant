"""Score a run's ragas_input.jsonl with four RAGAS metrics (M09, D19 path A).

Purpose: standalone RAGAS scorer for the isolated .venv-ragas (requirements-ragas.txt).
It never imports ragdocs; scripts/ragas_run.py (main venv) exports the input file,
passes settings on the command line and the Gemini key in the environment.

Inputs:
  --input <run>/ragas_input.jsonl (id, category, user_input, response,
    retrieved_contexts, reference, eligible{metric: bool}), written by
    scripts/export_ragas_input.py.
  cache/budget.json (D24 contract), cache/ragas (diskcache of metric results and
    embeddings), GOOGLE_API_KEY in the environment.
Outputs (into --out-dir, refused if any already exists):
  ragas_config.json, ragas_scores.jsonl, ragas_summary.json.
  --error-log (append): one JSON line per failed LLM or embedding attempt and per metric
    error, with the full exception chain and any provider error details (quota id).
  --partial-dir: on a pause, ragas_scores.partial.jsonl and ragas_summary.partial.json
    for the items finished so far.
Exit codes: 0 done, 1 error, 3 paused on a daily limit (rerun continues from the cache).

Calls run one at a time: n-generation prompts (response_relevancy) are sent as n
sequential single requests, each with its own ragas retry, and every LLM and embedding
request waits for the per-minute throttle (--rpm-ceiling) before it starts.

Metrics: ragas 0.4.4 legacy single-turn metrics with LangChain wrappers (Faithfulness,
ResponseRelevancy, LLMContextPrecisionWithReference, LLMContextRecall); the newer
ragas.metrics.collections classes need instructor.from_genai, which the resolved
instructor 1.3.2 does not have. LangSmith tracing and ragas telemetry are turned off
before any LangChain or ragas import.
"""

import os

os.environ["RAGAS_DO_NOT_TRACK"] = "true"
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import sys  # noqa: E402
import warnings  # noqa: E402
from collections import Counter, defaultdict  # noqa: E402
from datetime import UTC, datetime  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ragas_budget import BudgetFile, CalendarBudget, DailyLimitReached  # noqa: E402

METRICS = ("faithfulness", "response_relevancy", "context_precision", "context_recall")
OUTPUT_FILES = ("ragas_config.json", "ragas_scores.jsonl", "ragas_summary.json")
EXIT_PAUSED = 3
QUOTA_MARKERS = ("RESOURCE_EXHAUSTED", "429")
CHARS_PER_TOKEN = 4
# Next to --error-log: every response_relevancy generation, to check whether the
# strictness generations differ (human request, D19).
GENERATIONS_LOG = "ragas_relevancy_generations.jsonl"


class QuotaExhausted(RuntimeError):
    """The provider returned a quota error; the run pauses instead of storing an error."""


def _jsonable(value: Any) -> Any:
    """Value as JSON-safe data (str() for anything json cannot encode)."""
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


def exception_chain(exc: BaseException) -> list[dict[str, Any]]:
    """Every exception in the cause/context chain: type, full message, provider fields."""
    chain, seen = [], set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        entry = {"type": type(current).__name__, "message": str(current)}
        for attr in ("code", "status", "details"):  # google.genai.errors.APIError fields
            if getattr(current, attr, None) is not None:
                entry[attr] = _jsonable(getattr(current, attr))
        chain.append(entry)
        current = current.__cause__ or current.__context__
    return chain


def log_generation(path: Path, response: Any, counters: Any) -> None:
    """Append the text of one response_relevancy generation (question-generation output)."""
    texts = [g.text for gens in response.generations for g in gens]
    record = {"t": datetime.now(UTC).isoformat(timespec="seconds"), **counters.context}
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({**record, "texts": texts}, ensure_ascii=False) + "\n")


def log_error(path: Path, kind: str, exc: BaseException, **context: Any) -> None:
    """Append one error record (full exception chain) to the error log."""
    chain = exception_chain(exc)
    record = {
        "t": datetime.now(UTC).isoformat(timespec="seconds"),
        "kind": kind,
        **context,
        "quota": any(m in e["message"] for e in chain for m in QUOTA_MARKERS),
        "chain": chain,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Command-line settings (all values come from ragdocs Settings via ragas_run.py)."""
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--budget-file", type=Path, required=True)
    p.add_argument("--cache-dir", type=Path, required=True)
    p.add_argument("--llm-model", required=True)
    p.add_argument("--embedding-model", required=True)
    p.add_argument("--llm-limits", required=True, help="RPM,TPM,RPD")
    p.add_argument("--embedding-limits", required=True, help="RPM,TPM,RPD")
    p.add_argument("--timezone", required=True)
    p.add_argument("--safety", type=float, required=True)
    p.add_argument("--window-s", type=float, required=True)
    p.add_argument("--strictness", type=int, required=True)
    p.add_argument("--max-attempts", type=int, required=True)
    p.add_argument("--timeout-s", type=int, required=True)
    p.add_argument("--llm-calls", type=json.loads, required=True, help="JSON {metric: n}")
    p.add_argument("--embedding-requests", type=json.loads, required=True)
    p.add_argument("--tokens-per-call", type=int, required=True)
    p.add_argument("--rpm-ceiling", type=float, required=True, help="Max requests per minute")
    p.add_argument("--error-log", type=Path, required=True)
    p.add_argument("--partial-dir", type=Path, required=True)
    p.add_argument("--refresh", action="store_true", help="Rescore the selected ids (probe)")
    p.add_argument(
        "--faithfulness-audit",
        type=Path,
        default=None,
        help="Rescore faithfulness for --ids and log statements, verdicts and contexts here",
    )
    p.add_argument("--git-commit", default="")
    p.add_argument("--ids", default="", help="Comma-separated ids to score (smoke runs)")
    p.add_argument("--plan-only", action="store_true", help="Print the budget plan and exit")
    p.add_argument(
        "--cache-check",
        action="store_true",
        help="Report cache hits and calls still needed from the cache only (no API calls)",
    )
    return p.parse_args(argv)


def read_rows(path: Path, ids: str) -> list[dict[str, Any]]:
    """Read the handoff rows, optionally restricted to the given ids."""
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    wanted = {i for i in ids.split(",") if i}
    return [r for r in rows if not wanted or r["id"] in wanted]


def cache_key(version: str, metric: str, llm: str, emb: str, row: dict[str, Any]) -> str:
    """sha1 of (ragas version, metric, LLM model, embedding model, sample fields)."""
    payload = [
        version,
        metric,
        llm,
        emb,
        row["user_input"],
        row["response"],
        row["retrieved_contexts"],
        row["reference"],
    ]
    return hashlib.sha1(json.dumps(payload, ensure_ascii=False).encode("utf-8")).hexdigest()


def cache_report(rows: list[dict[str, Any]], args: argparse.Namespace, cache, version: str) -> dict:
    """Per metric: eligible, cached (NaN results included) and missing; plus remaining needs.

    Reads only the diskcache; builds no model and makes no API call. Errored metrics are
    never cached, so they count as missing and would be retried.
    """
    report: dict[str, Any] = {"metrics": {}, "items_fully_cached": 0, "items": len(rows)}
    need_llm = need_emb = 0
    for row in rows:
        missing = [
            m
            for m in METRICS
            if row["eligible"].get(m)
            and cache_key(version, m, args.llm_model, args.embedding_model, row) not in cache
        ]
        report["items_fully_cached"] += not missing
        llm, _, emb = item_needs(row, missing, args)
        need_llm, need_emb = need_llm + llm, need_emb + emb
        for m in METRICS:
            if row["eligible"].get(m):
                s = report["metrics"].setdefault(m, {"eligible": 0, "cached": 0, "missing": []})
                s["eligible"] += 1
                if m in missing:
                    s["missing"].append(row["id"])
                else:
                    s["cached"] += 1
    report["llm_requests_needed"], report["embedding_requests_needed"] = need_llm, need_emb
    return report


def print_cache_report(report: dict[str, Any]) -> None:
    """Print cache_report as plain lines."""
    print(f"Cache check: {report['items_fully_cached']}/{report['items']} items fully cached")
    for m, s in report["metrics"].items():
        miss = len(s["missing"])
        first = ", ".join(s["missing"][:3]) + (" ..." if miss > 3 else "")
        print(f"  {m}: {s['cached']}/{s['eligible']} cached, {miss} to score ({first or 'none'})")
    print(
        f"Still needed (estimate): {report['llm_requests_needed']} LLM requests, "
        f"{report['embedding_requests_needed']} embedding requests"
    )


def budget_plan(rows: list[dict[str, Any]], args: argparse.Namespace, budgets: dict) -> int:
    """Print LLM and embedding request plans; return the days needed (overall maximum)."""
    days = 0
    for label, budget, per_metric in (
        ("Gemini LLM", budgets["llm"], args.llm_calls),
        ("Gemini embeddings", budgets["emb"], args.embedding_requests),
    ):
        parts, total = [], 0
        for m in METRICS:
            n = sum(1 for r in rows if r["eligible"].get(m))
            calls = n * int(per_metric.get(m, 0))
            total += calls
            if calls:
                parts.append(f"{m} {n} x {per_metric[m]} = {calls}")
        used, _ = budget.daily_used()
        cap = budget.rpd * budget.safety
        left_today = max(0.0, cap - used)
        need_days = 0 if total == 0 else 1 + math.ceil(max(0.0, total - left_today) / cap)
        days = max(days, need_days)
        print(
            f"{label} ({budget.model}): {'; '.join(parts) or 'none'}; total {total} requests; "
            f"used today {used}/{budget.rpd}; cap at {budget.safety} = {cap:.0f}; "
            f"days needed {need_days}"
        )
    print(f"Days needed overall: {days}")
    return days


class Counters:
    """Calls made by the current metric: LLM calls, embedding requests and texts."""

    def __init__(self) -> None:
        self.llm_calls = self.emb_requests = self.emb_texts = 0
        self.context: dict[str, str] = {}  # current item id and metric, for the error log

    def snapshot(self) -> tuple[int, int, int]:
        """Current totals."""
        return self.llm_calls, self.emb_requests, self.emb_texts


def make_recorder(budget: CalendarBudget, counters: Counters, args: argparse.Namespace) -> Any:
    """LangChain callback: throttle before every chat-model call, record every call
    (failed calls: 0 tokens) and log every failed attempt with its full error."""
    from langchain_core.callbacks import BaseCallbackHandler

    class BudgetRecorder(BaseCallbackHandler):
        def on_chat_model_start(self, *a: Any, **kwargs: Any) -> None:
            budget.throttle(args.tokens_per_call)

        def on_llm_start(self, *a: Any, **kwargs: Any) -> None:
            budget.throttle(args.tokens_per_call)

        def on_llm_end(self, response: Any, **kwargs: Any) -> None:
            tokens = 0
            for gens in response.generations:
                for g in gens:
                    usage = getattr(getattr(g, "message", None), "usage_metadata", None) or {}
                    tokens += int(usage.get("total_tokens", 0))
            counters.llm_calls += 1
            budget.record(1, tokens)
            if counters.context.get("metric") == "response_relevancy":
                log_generation(args.error_log.with_name(GENERATIONS_LOG), response, counters)

        def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
            counters.llm_calls += 1
            budget.record(1, 0)
            log_error(args.error_log, "llm_attempt", error, **counters.context)

    return BudgetRecorder()


def make_embeddings(args: argparse.Namespace, budget: CalendarBudget, counters: Counters, cache):
    """LangChain embeddings with a per-text disk cache; every API request is recorded."""
    from langchain_core.embeddings import Embeddings
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    inner = GoogleGenerativeAIEmbeddings(model=args.embedding_model)
    models = inner.client.models
    original = models.embed_content

    def counted_embed_content(*a: Any, **kw: Any) -> Any:
        contents = kw.get("contents", a[1] if len(a) > 1 else [])
        texts = contents if isinstance(contents, list) else [contents]
        chars = sum(len(t) for t in texts if isinstance(t, str))
        budget.throttle(max(1, chars // CHARS_PER_TOKEN))
        counters.emb_requests += 1
        counters.emb_texts += len(texts)
        try:
            return original(*a, **kw)
        except Exception as exc:
            log_error(args.error_log, "embedding_attempt", exc, **counters.context)
            raise
        finally:
            budget.record(1, max(1, chars // CHARS_PER_TOKEN))

    models.embed_content = counted_embed_content

    class CachedEmbeddings(Embeddings):
        def _key(self, text: str) -> str:
            return "emb:" + hashlib.sha1(f"{args.embedding_model}\n{text}".encode()).hexdigest()

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            missing = [t for t in dict.fromkeys(texts) if self._key(t) not in cache]
            if missing:
                for text, vec in zip(missing, inner.embed_documents(missing), strict=True):
                    cache[self._key(text)] = vec
            return [cache[self._key(t)] for t in texts]

        def embed_query(self, text: str) -> list[float]:
            if self._key(text) not in cache:
                cache[self._key(text)] = inner.embed_query(text)
            return cache[self._key(text)]

    return CachedEmbeddings()


def sequential_llm_class(base: type) -> type:
    """LangchainLLMWrapper subclass whose generate() sends n prompts one by one.

    ragas 0.4.4 BaseRagasLLM.generate wraps agenerate_text in tenacity (add_async_retry)
    and, with bypass_n, sends [prompt] * n as one concurrent LangChain batch, so one
    failed prompt resends all n. Here each of the n single requests has its own retry.
    """
    from langchain_core.outputs import LLMResult
    from ragas.llms.base import LLMDidNotFinishException
    from ragas.run_config import add_async_retry

    class SequentialLLM(base):
        async def generate(self, prompt, n=1, temperature=0.01, stop=None, callbacks=None):
            if temperature is None:
                temperature = self.get_temperature(n)
            one = add_async_retry(self.agenerate_text, self.run_config)
            generations = []
            for _ in range(n):
                result = await one(
                    prompt=prompt, n=1, temperature=temperature, stop=stop, callbacks=callbacks
                )
                if not self.is_finished(result):
                    raise LLMDidNotFinishException()
                generations.append(result.generations[0][0])
            return LLMResult(generations=[generations])

    return SequentialLLM


def build_metrics(args: argparse.Namespace, budgets: dict, counters: Counters, cache) -> dict:
    """Instantiate the four metrics with the wrapped Gemini LLM and embeddings."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # ragas 0.4.4 marks these import paths deprecated
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.llms.base import LangchainLLMWrapper  # real class (ragas.llms has a proxy)
        from ragas.metrics import (
            Faithfulness,
            LLMContextPrecisionWithReference,
            LLMContextRecall,
            ResponseRelevancy,
        )
        from ragas.run_config import RunConfig

        # max_workers only limits ragas's Executor (evaluate()); single_turn_score does
        # not use it, so SequentialLLM enforces one request at a time.
        run_config = RunConfig(max_retries=args.max_attempts, timeout=args.timeout_s, max_workers=1)
        chat = ChatGoogleGenerativeAI(
            model=args.llm_model,
            max_retries=0,  # ragas RunConfig retries, so each attempt is recorded
            callbacks=[make_recorder(budgets["llm"], counters, args)],
        )
        # bypass_n: Gemini rejects n > 1 ("Multiple candidates is not enabled for this
        # model"); SequentialLLM sends the prompt n times, one request at a time.
        llm = sequential_llm_class(LangchainLLMWrapper)(chat, run_config=run_config, bypass_n=True)
        emb = LangchainEmbeddingsWrapper(
            make_embeddings(args, budgets["emb"], counters, cache), run_config=run_config
        )
    metrics = {
        "faithfulness": Faithfulness(llm=llm),
        "response_relevancy": ResponseRelevancy(
            llm=llm, embeddings=emb, strictness=args.strictness
        ),
        "context_precision": LLMContextPrecisionWithReference(llm=llm),
        "context_recall": LLMContextRecall(llm=llm),
    }
    for metric in metrics.values():
        metric.init(run_config)
    return metrics


def score_metric(metric: Any, row: dict[str, Any]) -> float:
    """Score one sample synchronously; a provider quota error raises QuotaExhausted."""
    from ragas.dataset_schema import SingleTurnSample

    sample = SingleTurnSample(
        user_input=row["user_input"],
        response=row["response"],
        retrieved_contexts=row["retrieved_contexts"],
        reference=row["reference"],
    )
    try:
        return float(metric.single_turn_score(sample))
    except Exception as exc:  # noqa: BLE001 - every metric error is recorded or pauses
        if any(marker in str(exc) for marker in QUOTA_MARKERS):
            raise QuotaExhausted(str(exc)) from exc
        raise


def item_needs(row: dict[str, Any], todo: list[str], args: argparse.Namespace) -> tuple:
    """(LLM requests, LLM tokens, embedding requests) expected for the uncached metrics."""
    llm = sum(int(args.llm_calls.get(m, 0)) for m in todo)
    emb = sum(int(args.embedding_requests.get(m, 0)) for m in todo)
    return llm, llm * args.tokens_per_call, emb


def score_row(row, metrics, args, budgets, counters, cache, version) -> dict[str, Any]:
    """Score every eligible metric of one row, from the cache where possible."""
    keys = {
        m: cache_key(version, m, args.llm_model, args.embedding_model, row)
        for m in METRICS
        if row["eligible"].get(m)
    }
    todo = [m for m, k in keys.items() if args.refresh or k not in cache]
    if todo:
        llm_req, _, emb_req = item_needs(row, todo, args)
        budgets["llm"].check_daily(llm_req)  # per-call throttling happens in the callbacks
        if emb_req:
            budgets["emb"].check_daily(emb_req)
    errors: dict[str, str] = {}
    for m in todo:
        before = counters.snapshot()
        counters.context = {"id": row["id"], "metric": m}
        try:
            value = score_metric(metrics[m], row)
        except QuotaExhausted as exc:
            log_error(args.error_log, "metric_quota", exc, **counters.context)
            raise
        except Exception as exc:  # noqa: BLE001
            log_error(args.error_log, "metric_error", exc, **counters.context)
            errors[m] = f"{type(exc).__name__}: {str(exc)[:300]}"
            continue
        after = counters.snapshot()
        calls = [a - b for a, b in zip(after, before, strict=True)]
        nan = math.isnan(value)
        cache[keys[m]] = {
            "value": None if nan else value,
            "error": "NaN" if nan else None,
            "llm_calls": calls[0],
            "emb_requests": calls[1],
            "emb_texts": calls[2],
        }
    out: dict[str, Any] = {"id": row["id"], "category": row["category"]}
    for m, k in keys.items():
        hit = None if m in errors else cache.get(k)
        out[m] = hit["value"] if hit else None
        if hit and hit["error"]:
            errors[m] = hit["error"]
    out["errors"] = errors
    return out


def summarize(rows: list[dict[str, Any]], scores: list[dict[str, Any]]) -> dict[str, Any]:
    """Per metric: mean over non-null values, n eligible, n scored, n errored; per category."""
    by_id = {s["id"]: s for s in scores}
    summary: dict[str, Any] = {"metrics": {}, "per_category": defaultdict(dict)}
    for m in METRICS:
        eligible = [r for r in rows if r["eligible"].get(m)]
        values = [by_id[r["id"]][m] for r in eligible if by_id[r["id"]].get(m) is not None]
        errored = sum(1 for r in eligible if m in by_id[r["id"]]["errors"])
        summary["metrics"][m] = {
            "mean": sum(values) / len(values) if values else None,
            "n_eligible": len(eligible),
            "n_scored": len(values),
            "n_errored": errored,
        }
        for cat in sorted({r["category"] for r in eligible}):
            vals = [
                by_id[r["id"]][m]
                for r in eligible
                if r["category"] == cat and by_id[r["id"]].get(m) is not None
            ]
            summary["per_category"][cat][m] = {
                "mean": sum(vals) / len(vals) if vals else None,
                "n_scored": len(vals),
            }
    summary["per_category"] = dict(summary["per_category"])
    return summary


def measured_calls(rows, args, cache, version) -> dict[str, Any]:
    """Mean LLM calls, embedding requests and texts per request, per metric, from the cache."""
    totals: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        for m in METRICS:
            if not row["eligible"].get(m):
                continue
            hit = cache.get(cache_key(version, m, args.llm_model, args.embedding_model, row))
            if hit:
                totals[m].update(
                    n=1, llm=hit["llm_calls"], req=hit["emb_requests"], texts=hit["emb_texts"]
                )
    return {
        m: {
            "items": c["n"],
            "llm_calls_per_item": c["llm"] / c["n"],
            "embedding_requests_per_item": c["req"] / c["n"],
            "embedding_texts_per_request": (c["texts"] / c["req"]) if c["req"] else None,
        }
        for m, c in totals.items()
        if c["n"]
    }


def write_outputs(out_dir, rows, scores, args, cache, version, metrics) -> None:
    """Write ragas_config.json, ragas_scores.jsonl and ragas_summary.json."""

    def dump(name: str, text: str) -> None:
        with open(out_dir / name, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    config = {
        "ragas_version": version,
        "metric_classes": {m: type(obj).__name__ for m, obj in metrics.items()},
        "llm_model": args.llm_model,
        "embedding_model": args.embedding_model,
        "response_relevancy_strictness": args.strictness,
        "max_attempts": args.max_attempts,
        "input": args.input.as_posix(),
        "items_scored": len(scores),
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_commit": args.git_commit,
        "measured_calls_per_metric": measured_calls(rows, args, cache, version),
    }
    dump("ragas_config.json", json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    dump("ragas_scores.jsonl", "".join(json.dumps(s, ensure_ascii=False) + "\n" for s in scores))
    summary = summarize(rows, scores)
    dump("ragas_summary.json", json.dumps(summary, ensure_ascii=False, indent=2) + "\n")


async def audit_faithfulness_row(metric: Any, row: dict[str, Any]) -> dict[str, Any]:
    """Run Faithfulness's two steps (ragas 0.4.4 _create_statements, _create_verdicts)
    on one row and return statements, verdicts, the exact contexts and the score."""
    from ragas.dataset_schema import SingleTurnSample

    sample_row = SingleTurnSample(
        user_input=row["user_input"],
        response=row["response"],
        retrieved_contexts=row["retrieved_contexts"],
        reference=row["reference"],
    ).to_dict()
    statements = (await metric._create_statements(sample_row, None)).statements
    record: dict[str, Any] = {
        "id": row["id"],
        "user_input": sample_row["user_input"],
        "response": sample_row["response"],
        "retrieved_contexts": sample_row["retrieved_contexts"],
        # The NLI prompt receives the contexts joined with "\n" (_create_verdicts).
        "nli_context": "\n".join(sample_row["retrieved_contexts"]),
        "statements": statements,
        "verdicts": [],
        "score": None,
    }
    if statements:
        verdicts = await metric._create_verdicts(sample_row, statements, None)
        record["verdicts"] = [v.model_dump() for v in verdicts.statements]
        score = metric._compute_score(verdicts)
        record["score"] = None if math.isnan(score) else float(score)
    return record


def run_faithfulness_audit(rows: list, args: argparse.Namespace, budgets: dict) -> int:
    """Rescore faithfulness on the selected rows and write one audit line per row.

    Writes a new file (refuses an existing one); the metric cache and outputs are
    not touched. Exit 3 on a daily cap or quota error, with the rows done so far kept.
    """
    import asyncio

    import diskcache

    if not args.ids:
        print("--faithfulness-audit needs --ids", file=sys.stderr)
        return 1
    if args.faithfulness_audit.exists():
        print(f"Refusing to overwrite {args.faithfulness_audit}", file=sys.stderr)
        return 1
    counters = Counters()
    with diskcache.Cache(str(args.cache_dir)) as cache:
        metric = build_metrics(args, budgets, counters, cache)["faithfulness"]
    records = []
    try:
        for row in rows:
            budgets["llm"].check_daily(int(args.llm_calls.get("faithfulness", 0)))
            counters.context = {"id": row["id"], "metric": "faithfulness_audit"}
            before = counters.llm_calls
            rec = asyncio.run(audit_faithfulness_row(metric, row))
            rec["llm_calls"] = counters.llm_calls - before
            records.append(rec)
            print(f"{row['id']}: score {rec['score']}, {len(rec['statements'])} statements")
    except Exception as exc:  # noqa: BLE001 - logged in full; rows done so far are kept
        log_error(args.error_log, "faithfulness_audit", exc, **counters.context)
        print(f"Stopped: {type(exc).__name__}: {exc}", file=sys.stderr)
        code = EXIT_PAUSED if isinstance(exc, DailyLimitReached) else 1
    else:
        code = 0
    args.faithfulness_audit.parent.mkdir(parents=True, exist_ok=True)
    with open(args.faithfulness_audit, "w", encoding="utf-8", newline="\n") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
    print(f"Wrote {len(records)} rows to {args.faithfulness_audit.as_posix()}")
    return code


def write_partial(args: argparse.Namespace, rows: list, scores: list, reason: str) -> None:
    """On a pause: scores and summary of the finished items, outside the run folder."""
    args.partial_dir.mkdir(parents=True, exist_ok=True)
    summary = {"paused": reason, "items_done": len(scores), **summarize(rows, scores)}
    files = {
        "ragas_scores.partial.jsonl": "".join(
            json.dumps(s, ensure_ascii=False) + "\n" for s in scores
        ),
        "ragas_summary.partial.json": json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
    }
    for name, text in files.items():
        with open(args.partial_dir / name, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)


def make_budgets(args: argparse.Namespace) -> dict[str, CalendarBudget]:
    """One CalendarBudget per resource (LLM, embeddings) on the shared budget file."""
    store = BudgetFile(args.budget_file)
    budgets = {}
    for key, model, limits in (
        ("llm", args.llm_model, args.llm_limits),
        ("emb", args.embedding_model, args.embedding_limits),
    ):
        rpm, tpm, rpd = (int(x) for x in limits.split(","))
        budgets[key] = CalendarBudget(
            model,
            store,
            requests_per_min=rpm,
            tokens_per_min=tpm,
            requests_per_day=rpd,
            safety=args.safety,
            timezone=args.timezone,
            window_s=args.window_s,
            rpm_ceiling=args.rpm_ceiling,
        )
    return budgets


def main(argv: list[str] | None = None) -> int:
    """Plan, score with resume from the cache, and write outputs when every row is done."""
    args = parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    rows = [r for r in read_rows(args.input, args.ids) if any(r["eligible"].values())]
    budgets = make_budgets(args)
    budget_plan(rows, args, budgets)
    if args.plan_only:
        return 0
    if args.cache_check:
        import diskcache
        import ragas

        with diskcache.Cache(str(args.cache_dir)) as cache:
            print_cache_report(cache_report(rows, args, cache, ragas.__version__))
        return 0
    if args.faithfulness_audit:
        return run_faithfulness_audit(rows, args, budgets)
    existing = [n for n in OUTPUT_FILES if (args.out_dir / n).exists()]
    if existing:
        print(f"Refusing to overwrite {', '.join(existing)} in {args.out_dir}", file=sys.stderr)
        return 1
    import diskcache
    import ragas

    version = ragas.__version__
    counters = Counters()
    with diskcache.Cache(str(args.cache_dir)) as cache:
        metrics = build_metrics(args, budgets, counters, cache)
        scores = []
        try:
            for i, row in enumerate(rows, start=1):
                scores.append(score_row(row, metrics, args, budgets, counters, cache, version))
                vals = {m: scores[-1].get(m) for m in METRICS if m in scores[-1]}
                print(f"{row['id']} ({i}/{len(rows)}) {vals} errors={list(scores[-1]['errors'])}")
        except (DailyLimitReached, QuotaExhausted) as exc:
            write_partial(args, rows[: len(scores)], scores, str(exc))
            print(f"Paused: {exc}")
            print(
                f"Partial outputs in {args.partial_dir.as_posix()}; errors in "
                f"{args.error_log.as_posix()}. Rerun the same command to continue."
            )
            return EXIT_PAUSED
        args.out_dir.mkdir(parents=True, exist_ok=True)
        write_outputs(args.out_dir, rows, scores, args, cache, version, metrics)
    print(f"Wrote {', '.join(OUTPUT_FILES)} to {args.out_dir.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
