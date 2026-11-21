"""Self-RAG graph nodes (M11): decide_retrieval, out_of_scope, verify_answer, regenerate, abstain.

Same conventions as ragdocs.pipelines.agentic.nodes: each node is a function of
(state, deps) returning a partial update with node_start, its decision event (with
data["outcome"], D25) and node_end. The corrective nodes are reused unchanged.

Failure policy (D26): a structured call that fails with an error for which
is_structured_output_error is True takes the node's fallback, appends its name to
diagnostics["fallbacks"] (a merged copy; other keys kept) and puts data["fallback"] and
data["error_kind"] on the decision event. Any other exception propagates, so
AgenticPipeline yields one error event, as in corrective. No node retries a call.

Runtime-safe: never imports ragdocs.eval or ragdocs.ingest.
"""

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END

from ragdocs.generation.answer import format_context, generate_answer
from ragdocs.generation.prompts import ABSTAIN_TEXT
from ragdocs.pipelines.agentic.nodes import _decision, _event
from ragdocs.pipelines.agentic.prompts import (
    DECIDE_SYSTEM_PROMPT,
    DECIDE_USER_TEMPLATE,
    OUT_OF_SCOPE_TEXT,
    REGENERATE_FEEDBACK_TEMPLATE,
    VERIFY_SYSTEM_PROMPT,
    VERIFY_USER_TEMPLATE,
)
from ragdocs.pipelines.agentic.state import AgenticDeps, AgentState, AnswerVerification
from ragdocs.providers.errors import error_kind, is_structured_output_error
from ragdocs.schemas import Answer

# Line used in the regenerate feedback when the verifier listed no claims.
NO_CLAIMS_LINE = "- (the checker listed no specific claims)"


def with_fallback(diagnostics: dict[str, Any], name: str, **extra: Any) -> dict[str, Any]:
    """Copy of diagnostics with name appended to diagnostics["fallbacks"] and extra keys set."""
    out = {**diagnostics, **extra}
    out["fallbacks"] = [*diagnostics.get("fallbacks", []), name]
    return out


def _structured_failure(exc: Exception) -> str:
    """Return error_kind(exc) for a D26 structured-output failure; re-raise anything else."""
    if not is_structured_output_error(exc):
        raise exc
    return error_kind(exc)


def decide_retrieval(state: AgentState, deps: AgenticDeps) -> dict[str, Any]:
    """One structured call on the original question: search the docs or answer out of scope."""
    start = _event("node_start", "decide_retrieval", "Deciding whether to retrieve")
    messages = [
        SystemMessage(content=DECIDE_SYSTEM_PROMPT),
        HumanMessage(content=DECIDE_USER_TEMPLATE.format(question=state["question"])),
    ]
    diagnostics = state["diagnostics"]
    try:
        decision = deps.decider_llm.invoke(messages)
    except Exception as exc:
        kind = _structured_failure(exc)
        event = _decision(
            "decide_retrieval",
            "retrieval decision failed; retrieving by default",
            "info",
            {"needs_docs": True, "fallback": "decide_failed", "error_kind": kind},
        )
        needs_docs, diagnostics = True, with_fallback(diagnostics, "decide_failed")
    else:
        needs_docs = bool(decision.needs_docs)
        verb = "retrieval needed" if needs_docs else "no retrieval needed"
        event = _decision(
            "decide_retrieval",
            f"{verb}: {decision.reason}",
            "ok" if needs_docs else "stop",
            {"needs_docs": needs_docs, "reason": decision.reason},
        )
    end = _event("node_end", "decide_retrieval", "Retrieval decided")
    return {
        "needs_docs": needs_docs,
        "next_step": "retrieve" if needs_docs else "out_of_scope",
        "diagnostics": diagnostics,
        "events": [start, event, end],
    }


def out_of_scope(state: AgentState, deps: AgenticDeps) -> dict[str, Any]:
    """Answer a question that needs no documentation with the fixed text; no LLM call."""
    start = _event("node_start", "out_of_scope", "Question outside the documentation")
    answer = Answer(text=OUT_OF_SCOPE_TEXT, citations=[], abstained=True)
    event = _decision("out_of_scope", "out of scope; answered without retrieval", "stop")
    end = _event("node_end", "out_of_scope", "Answered out of scope")
    return {"answer": answer, "contexts": [], "events": [start, event, end]}


def _verify_call(state: AgentState, deps: AgenticDeps) -> AnswerVerification:
    """One structured verifier call over the question, state.contexts and the answer."""
    answer = state["answer"]
    assert answer is not None
    messages = [
        SystemMessage(content=VERIFY_SYSTEM_PROMPT),
        HumanMessage(
            content=VERIFY_USER_TEMPLATE.format(
                question=state["question"],
                context=format_context(state["contexts"]),
                answer=answer.text,
            )
        ),
    ]
    return deps.verifier_llm.invoke(messages)


def verify_route(
    v: AnswerVerification, regenerations: int, max_regenerations: int
) -> tuple[str, Any, str | None]:
    """Return (next_step, outcome, abstain_reason) for a verification result."""
    if v.grounded and v.answers_question:
        return END, "ok", None
    if not v.grounded and regenerations < max_regenerations:
        return "regenerate", "retry", None
    return "abstain", "stop", "not_grounded" if not v.grounded else "does_not_answer"


def verify_answer(state: AgentState, deps: AgenticDeps) -> dict[str, Any]:
    """Check the answer against state.contexts; end, regenerate or abstain (D26 on failure)."""
    start = _event("node_start", "verify_answer", "Verifying the answer")
    end = _event("node_end", "verify_answer", "Verification finished")
    answer, regenerations = state["answer"], state["regenerations"]
    if answer is None or answer.abstained:
        event = _decision("verify_answer", "verification skipped: abstained", "info")
        return {"verification": None, "next_step": END, "events": [start, event, end]}
    diagnostics = state["diagnostics"]
    try:
        v = _verify_call(state, deps)
    except Exception as exc:
        kind = _structured_failure(exc)
        verification: dict[str, Any] = {"failed": True, "error_kind": kind}
        event = _decision(
            "verify_answer",
            "verification failed; answer kept unchecked",
            "info",
            {"fallback": "verify_failed", "error_kind": kind, "regenerations": regenerations},
        )
        diagnostics = with_fallback(diagnostics, "verify_failed")
        return {
            "verification": verification,
            "next_step": END,
            "diagnostics": diagnostics,
            "events": [start, event, end],
        }
    verification = v.model_dump()
    next_step, outcome, reason = verify_route(v, regenerations, deps.settings.max_regenerations)
    message = {END: "answer verified", "regenerate": "answer not grounded; regenerating"}.get(
        next_step, f"abstaining: {reason}"
    )
    data = {**verification, "regenerations": regenerations}
    if reason is not None:
        diagnostics = {**diagnostics, "abstain_reason": reason}
        data["abstain_reason"] = reason
    event = _decision("verify_answer", message, outcome, data)
    return {
        "verification": verification,
        "next_step": next_step,
        "diagnostics": diagnostics,
        "events": [start, event, end],
    }


def feedback_claims(verification: dict[str, Any] | None) -> list[str]:
    """Unsupported claims from the last verification (empty when none were listed)."""
    return [str(c) for c in (verification or {}).get("unsupported_claims", [])]


def feedback_message(claims: list[str]) -> HumanMessage:
    """REGENERATE_FEEDBACK_TEMPLATE with one '- ' line per claim (or NO_CLAIMS_LINE)."""
    lines = "\n".join(f"- {c}" for c in claims) if claims else NO_CLAIMS_LINE
    return HumanMessage(content=REGENERATE_FEEDBACK_TEMPLATE.format(claims=lines))


def regenerate(state: AgentState, deps: AgenticDeps) -> dict[str, Any]:
    """Generate again from the same contexts with the verifier's claims as feedback."""
    regenerations = state["regenerations"] + 1
    claims = feedback_claims(state.get("verification"))
    start = _event("node_start", "regenerate", "Regenerating the answer")
    end = _event("node_end", "regenerate", "Answer regenerated")
    try:
        answer, gen_diag = generate_answer(
            state["question"],
            state["contexts"],
            deps.generator_llm,
            extra_messages=[feedback_message(claims)],
        )
    except Exception as exc:
        kind = _structured_failure(exc)
        event = _decision(
            "regenerate",
            "regeneration failed; abstaining",
            "stop",
            {
                "claims": claims,
                "regenerations": regenerations,
                "fallback": "regenerate_failed",
                "error_kind": kind,
            },
        )
        diagnostics = with_fallback(
            state["diagnostics"], "regenerate_failed", abstain_reason="regenerate_failed"
        )
        return {
            "regenerations": regenerations,
            "next_step": "abstain",
            "diagnostics": diagnostics,
            "events": [start, event, end],
        }
    event = _decision(
        "regenerate",
        f"regenerating without {len(claims)} unsupported claim(s)",
        "retry",
        {"claims": claims, "regenerations": regenerations},
    )
    return {
        "answer": answer,
        "regenerations": regenerations,
        "next_step": "verify_answer",
        "diagnostics": {**state["diagnostics"], **gen_diag},
        "events": [start, event, end],
    }


def abstain(state: AgentState, deps: AgenticDeps) -> dict[str, Any]:
    """Replace the answer with the standard abstention; contexts unchanged; no LLM call."""
    reason = state["diagnostics"].get("abstain_reason")
    start = _event("node_start", "abstain", "Abstaining")
    answer = Answer(text=ABSTAIN_TEXT, citations=[], abstained=True)
    event = _decision("abstain", f"abstained: {reason}", "stop", {"abstain_reason": reason})
    end = _event("node_end", "abstain", "Abstained")
    return {"answer": answer, "events": [start, event, end]}
