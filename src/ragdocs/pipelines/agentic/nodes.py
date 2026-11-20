"""Corrective RAG graph nodes (M10).

Each node is a plain function of (state, deps), bound with functools.partial in
graph.py. It returns a partial state update whose events hold node_start, the node's
retrieval or decision events, and node_end, all with t_ms=0 (the pipeline stamps t_ms
when it yields them). Every decision event carries data["outcome"] (D25). No node
retries an LLM call; a grading parse failure is handled here, other errors propagate.

Runtime-safe: never imports ragdocs.eval or ragdocs.ingest.
"""

import hashlib
import math
from collections.abc import Sequence
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from ragdocs.docs_urls import url_to_doc_ref
from ragdocs.generation.answer import format_context, generate_answer
from ragdocs.generation.prompts import ABSTAIN_TEXT
from ragdocs.pipelines.agentic.prompts import (
    GRADE_SYSTEM_PROMPT,
    GRADE_USER_TEMPLATE,
    REWRITE_SYSTEM_PROMPT,
    REWRITE_USER_TEMPLATE,
)
from ragdocs.pipelines.agentic.state import AgenticDeps, AgentState, Grade, GradeBatch, Outcome
from ragdocs.schemas import Answer, Chunk, RetrievedChunk, TraceEvent
from ragdocs.tracing import traced_run

# Rough characters-per-token estimate for web text (same convention as D7 embeddings).
CHARS_PER_TOKEN = 4
WEB_CHUNK_PREFIX = "web-"
WEB_CHUNK_HASH_CHARS = 12
WEB_DOC_PATH_PREFIX = "web:"
CODE_FENCE = "```"
# Grader output errors handled as "every document not relevant" (no retry).
GRADING_PARSE_ERRORS: tuple[type[Exception], ...] = (OutputParserException, ValidationError)


def _event(
    event_type: Any, node: str, message: str, data: dict[str, Any] | None = None
) -> TraceEvent:
    """Build an unstamped TraceEvent (t_ms=0)."""
    return TraceEvent(type=event_type, node=node, message=message, data=data or {}, t_ms=0)


def _decision(
    node: str, message: str, outcome: Outcome, data: dict[str, Any] | None = None
) -> TraceEvent:
    """Build a decision event; data["outcome"] is always set (D25)."""
    return _event("decision", node, message, {**(data or {}), "outcome": outcome})


def chunk_summary(rc: RetrievedChunk) -> dict[str, Any]:
    """Per-chunk data of a retrieval event (chunk_id and url for first_retrieval_hit@5)."""
    c = rc.chunk
    return {
        "chunk_id": c.chunk_id,
        "url": c.url,
        "rank": rc.rank,
        "score": rc.score,
        "title": c.title,
        "heading_path": c.heading_path,
    }


def _trace_document(rc: RetrievedChunk) -> dict[str, Any]:
    """Format a chunk in the document shape LangSmith renders for retriever runs (M07)."""
    c = rc.chunk
    meta = {"chunk_id": c.chunk_id, "url": c.url, "rank": rc.rank, "score": rc.score}
    return {"page_content": c.text, "type": "Document", "metadata": meta}


def merge_relevant(
    existing: Sequence[RetrievedChunk], new: Sequence[RetrievedChunk]
) -> list[RetrievedChunk]:
    """Append new chunks not already present (by chunk_id), keeping first-appearance order."""
    seen = {rc.chunk.chunk_id for rc in existing}
    merged = list(existing)
    for rc in new:
        if rc.chunk.chunk_id not in seen:
            seen.add(rc.chunk.chunk_id)
            merged.append(rc)
    return merged


def retrieve(state: AgentState, deps: AgenticDeps) -> dict[str, Any]:
    """Run hybrid retrieval for state.query inside a 'hybrid_retrieve' retriever run."""
    query = state["query"]
    start = _event("node_start", "retrieve", "Retrieving documentation excerpts")
    with traced_run(name="hybrid_retrieve", run_type="retriever", inputs={"query": query}) as run:
        documents = list(deps.retriever.retrieve(query))
        run.set_outputs({"documents": [_trace_document(rc) for rc in documents]})
    mode = "hybrid_rerank" if deps.settings.use_reranker else "hybrid"
    data = {"mode": mode, "query": query, "chunks": [chunk_summary(rc) for rc in documents]}
    retrieval = _event("retrieval", "retrieve", "Retrieved candidate excerpts", data)
    end = _event("node_end", "retrieve", f"Retrieved {len(documents)} excerpts")
    return {"documents": documents, "events": [start, retrieval, end]}


def collect_grades(batch: GradeBatch, n: int) -> tuple[dict[int, Grade], int]:
    """Keep the first grade per valid 1-based index; return (grades by index, invalid count).

    Out-of-range and duplicate indices are invalid and ignored.
    """
    kept: dict[int, Grade] = {}
    invalid = 0
    for grade in batch.grades:
        if not 1 <= grade.index <= n or grade.index in kept:
            invalid += 1
            continue
        kept[grade.index] = grade
    return kept, invalid


def _grade_call(question: str, documents: list[RetrievedChunk], llm: Any) -> GradeBatch:
    """One structured grader call against the original question."""
    messages = [
        SystemMessage(content=GRADE_SYSTEM_PROMPT),
        HumanMessage(
            content=GRADE_USER_TEMPLATE.format(question=question, context=format_context(documents))
        ),
    ]
    return llm.invoke(messages)


def _grade_rows(
    documents: list[RetrievedChunk], kept: dict[int, Grade], failed: bool
) -> list[dict[str, Any]]:
    """Per-chunk grading data for the decision event, in documents order."""
    rows = []
    for i, rc in enumerate(documents, start=1):
        grade = kept.get(i)
        if grade is not None:
            relevant, reason = grade.relevant, grade.reason
        else:
            relevant, reason = False, "grading failed" if failed else "no valid grade returned"
        rows.append(
            {"index": i, "chunk_id": rc.chunk.chunk_id, "relevant": relevant, "reason": reason}
        )
    return rows


def route_decision(n_relevant: int, rewrites: int, settings: Any) -> tuple[str, str]:
    """Return (next node, reason) after grading."""
    if n_relevant >= settings.min_relevant_chunks:
        return "generate", f"{n_relevant} relevant chunk(s) >= {settings.min_relevant_chunks}"
    if rewrites < settings.max_query_rewrites:
        return (
            "rewrite_query",
            f"too few relevant chunks; rewrite {rewrites + 1} of {settings.max_query_rewrites}",
        )
    return "web_search", f"too few relevant chunks after {rewrites} rewrite(s)"


def _counted(diagnostics: dict[str, Any], **increments: int) -> dict[str, Any]:
    """Return a copy of diagnostics with each counter increased (missing counters start at 0)."""
    out = dict(diagnostics)
    for key, inc in increments.items():
        out[key] = int(out.get(key, 0)) + inc
    return out


def grade_documents(state: AgentState, deps: AgenticDeps) -> dict[str, Any]:
    """Grade the latest documents in one call, accumulate relevant chunks and pick the route."""
    documents, settings = state["documents"], deps.settings
    n = len(documents)
    start = _event("node_start", "grade_documents", f"Grading {n} excerpts")
    kept: dict[int, Grade] = {}
    invalid, failed, error_name = 0, False, ""
    if documents:
        try:
            kept, invalid = collect_grades(
                _grade_call(state["question"], documents, deps.grader_llm), n
            )
        except GRADING_PARSE_ERRORS as exc:
            failed, error_name = True, type(exc).__name__
    missing = 0 if failed else n - len(kept)
    rows = _grade_rows(documents, kept, failed)
    new_relevant = [documents[r["index"] - 1] for r in rows if r["relevant"]]
    relevant = merge_relevant(state["relevant"], new_relevant)
    enough = len(relevant) >= settings.min_relevant_chunks
    message = f"{len(new_relevant)} of {n} chunks relevant"
    if failed:
        message += f" (grading failed: {error_name}; all treated as not relevant)"
    grading = _decision(
        "grade_documents",
        message,
        "ok" if enough else "retry",
        {
            "grades": rows,
            "relevant_total": len(relevant),
            "missing_grades": missing,
            "invalid_grades": invalid,
            "grading_failed": failed,
        },
    )
    branch, why = route_decision(len(relevant), state["rewrites"], settings)
    routing = _decision(
        "grade_documents",
        f"Route to {branch}: {why}",
        "ok" if branch == "generate" else "retry",
        {"branch": branch},
    )
    end = _event("node_end", "grade_documents", f"Graded {n} excerpts")
    diagnostics = _counted(
        state["diagnostics"],
        missing_grades=missing,
        invalid_grades=invalid,
        grading_failures=int(failed),
    )
    return {
        "relevant": relevant,
        "next_step": branch,
        "diagnostics": diagnostics,
        "events": [start, grading, routing, end],
    }


def heading_lines(documents: Sequence[RetrievedChunk]) -> str:
    """One line per document: '<n>. <title> > <heading > path>'."""
    lines = []
    for i, rc in enumerate(documents, start=1):
        parts = [rc.chunk.title, *rc.chunk.heading_path]
        lines.append(f"{i}. {' > '.join(parts)}")
    return "\n".join(lines)


def rewrite_query(state: AgentState, deps: AgenticDeps) -> dict[str, Any]:
    """Rewrite the search query in one structured call; keep the old one if unchanged."""
    old = state["query"]
    start = _event("node_start", "rewrite_query", "Rewriting the search query")
    messages = [
        SystemMessage(content=REWRITE_SYSTEM_PROMPT),
        HumanMessage(
            content=REWRITE_USER_TEMPLATE.format(
                question=state["question"], query=old, headings=heading_lines(state["documents"])
            )
        ),
    ]
    new = deps.rewriter_llm.invoke(messages).query.strip()
    diagnostics = dict(state["diagnostics"])
    unchanged = not new or new.lower() == old.lower()
    if unchanged:
        new = old
        diagnostics["rewrite_unchanged"] = True
    rewritten = _decision(
        "rewrite_query",
        "query rewritten",
        "retry",
        {"old_query": old, "new_query": new, "unchanged": unchanged},
    )
    end = _event("node_end", "rewrite_query", "Query rewritten")
    return {
        "query": new,
        "rewrites": state["rewrites"] + 1,
        "diagnostics": diagnostics,
        "events": [start, rewritten, end],
    }


def web_chunk_id(url: str) -> str:
    """'web-' plus the first 12 hex characters of sha1(url)."""
    return WEB_CHUNK_PREFIX + hashlib.sha1(url.encode("utf-8")).hexdigest()[:WEB_CHUNK_HASH_CHARS]


def web_result_to_chunk(result: dict[str, Any], rank: int, max_chars: int) -> RetrievedChunk:
    """Convert one web search result (url, title, content[, score]) into a RetrievedChunk."""
    url = str(result.get("url") or "")
    text = str(result.get("content") or "")[:max_chars]
    ref = url_to_doc_ref(url)
    if ref is not None:
        doc_path, anchor = ref.doc_path, ref.anchor
    else:
        doc_path, anchor = WEB_DOC_PATH_PREFIX + urlsplit(url).path, ""
    chunk = Chunk(
        chunk_id=web_chunk_id(url),
        doc_path=doc_path,
        url=url,
        title=str(result.get("title") or ""),
        heading_path=[],
        anchor=anchor,
        text=text,
        embed_text=text,
        n_tokens=math.ceil(len(text) / CHARS_PER_TOKEN),
        has_code=CODE_FENCE in text,
        source_commit="web",
    )
    score = float(result.get("score") or 0.0)
    return RetrievedChunk(chunk=chunk, score=score, rank=rank, retriever="web")


def web_page_key(url: str) -> str:
    """De-duplication key of a web result: lowercased host + path without trailing slash."""
    parts = urlsplit(url.strip())
    return f"{parts.hostname or ''}{parts.path}".lower().rstrip("/")


def dedupe_web_results(results: Sequence[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Keep the first result per page (web_page_key), in order; return (kept, dropped count).

    Tavily can return one page several times as plain, #fragment and ?query URLs (M10
    S2 smoke, q043). Each kept result's URL loses its query string but keeps its
    fragment, so url_to_doc_ref can still resolve the anchor.
    """
    kept: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r in results:
        url = str(r.get("url") or "")
        key = web_page_key(url)
        if key in seen:
            continue
        seen.add(key)
        p = urlsplit(url.strip())
        kept.append({**r, "url": urlunsplit((p.scheme, p.netloc, p.path, "", p.fragment))})
    return kept, len(results) - len(kept)


def web_search(state: AgentState, deps: AgenticDeps) -> dict[str, Any]:
    """Search the docs domain with the original question; results are not graded."""
    question = state["question"]
    start = _event("node_start", "web_search", "Searching the documentation site")
    with traced_run(name="tavily_search", run_type="tool", inputs={"query": question}) as run:
        raw = list(deps.web_search.search(question))
        run.set_outputs({"urls": [str(r.get("url") or "") for r in raw]})
    results, dropped = dedupe_web_results(raw)
    max_chars = deps.settings.web_text_max_chars
    web_docs = [web_result_to_chunk(r, i, max_chars) for i, r in enumerate(results, start=1)]
    urls = [rc.chunk.url for rc in web_docs]
    fallback = _decision(
        "web_search",
        "fell back to web search",
        "retry" if web_docs else "stop",
        {"urls": urls, "n_results": len(web_docs), "web_duplicates_dropped": dropped},
    )
    end = _event("node_end", "web_search", f"{len(web_docs)} web results")
    diagnostics = {**state["diagnostics"], "web_duplicates_dropped": dropped}
    return {
        "web_docs": web_docs,
        "used_web": True,
        "diagnostics": diagnostics,
        "events": [start, fallback, end],
    }


def generate(state: AgentState, deps: AgenticDeps) -> dict[str, Any]:
    """Answer from relevant chunks plus web results, or abstain without a call if there are none."""
    settings = deps.settings
    cap = settings.final_k + settings.web_max_results
    contexts = [*state["relevant"], *state["web_docs"]][:cap]
    start = _event("node_start", "generate", "Generating cited answer")
    if not contexts:
        answer = Answer(text=ABSTAIN_TEXT, citations=[], abstained=True)
        decision = _decision(
            "generate", "No relevant excerpts or web results; abstained without generation", "stop"
        )
        end = _event("node_end", "generate", "Abstained")
        return {"answer": answer, "contexts": [], "events": [start, decision, end]}
    n_web = sum(1 for rc in contexts if rc.retriever == "web")
    decision = _decision(
        "generate",
        f"Generating from {len(contexts) - n_web} graded excerpts and {n_web} web results",
        "info",
        {"n_contexts": len(contexts), "n_web": n_web},
    )
    answer, gen_diag = generate_answer(state["question"], contexts, deps.generator_llm)
    end = _event("node_end", "generate", "Answer generated and validated", gen_diag)
    return {
        "answer": answer,
        "contexts": contexts,
        "diagnostics": {**state["diagnostics"], **gen_diag},
        "events": [start, decision, end],
    }
