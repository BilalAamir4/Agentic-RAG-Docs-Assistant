"""LangGraph construction for the agentic pipelines (M10 corrective; M11 self-RAG).

Graph (corrective):
    START -> retrieve -> grade_documents -> {generate | rewrite_query | web_search}
    rewrite_query -> retrieve; web_search -> generate; generate -> END
With max_query_rewrites = 1 the worst case is 4 LLM calls: grade, rewrite, grade,
generate.

Graph (self_rag, M11):
    START -> decide_retrieval -> {retrieve | out_of_scope}; out_of_scope -> END
    retrieve, grade_documents, rewrite_query and web_search as in corrective
    generate -> verify_answer -> {END | regenerate | abstain}
    regenerate -> {verify_answer | abstain}; abstain -> END
No edge leads from verify_answer or regenerate back to retrieval. With
max_query_rewrites = 1 and max_regenerations = 1 the worst case is 8 LLM calls (D27).

Runtime-safe: never imports ragdocs.eval or ragdocs.ingest.
"""

from functools import partial
from typing import Any, Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from ragdocs.config import Settings, get_settings
from ragdocs.pipelines.agentic import nodes, self_rag_nodes
from ragdocs.pipelines.agentic.state import (
    AgenticDeps,
    AgentState,
    AnswerVerification,
    GradeBatch,
    RetrievalDecision,
    RewrittenQuery,
)

Mode = Literal["corrective", "self_rag"]
# Branches of the conditional edge after grade_documents (identity path_map for drawing).
GRADING_BRANCHES = ("generate", "rewrite_query", "web_search")
# Self-RAG conditional edges: explicit path maps, so the Mermaid export draws each target.
DECIDE_BRANCHES = ("retrieve", "out_of_scope")
VERIFY_BRANCHES = (END, "regenerate", "abstain")
REGENERATE_BRANCHES = ("verify_answer", "abstain")


def route_after_grading(state: AgentState) -> str:
    """Return the branch grade_documents stored in next_step (no events, no updates)."""
    return str(state["next_step"])


def route_next_step(state: AgentState) -> str:
    """Return the next_step a self_rag node stored (no events, no updates)."""
    return str(state["next_step"])


def _identity(branches: tuple[str, ...]) -> dict[Any, str]:
    """Identity path map for add_conditional_edges."""
    return {b: b for b in branches}


def _add_corrective_core(graph: StateGraph, deps: AgenticDeps) -> None:
    """Add the five corrective nodes in their M10 order (the Mermaid export lists them so)."""
    graph.add_node("retrieve", partial(nodes.retrieve, deps=deps))
    graph.add_node("grade_documents", partial(nodes.grade_documents, deps=deps))
    graph.add_node("rewrite_query", partial(nodes.rewrite_query, deps=deps))
    graph.add_node("web_search", partial(nodes.web_search, deps=deps))
    graph.add_node("generate", partial(nodes.generate, deps=deps))


def _add_self_rag_nodes(graph: StateGraph, deps: AgenticDeps) -> None:
    """The five self_rag nodes (M11)."""
    for name in ("decide_retrieval", "out_of_scope", "verify_answer", "regenerate", "abstain"):
        graph.add_node(name, partial(getattr(self_rag_nodes, name), deps=deps))


def build_graph(mode: Mode, deps: AgenticDeps) -> Any:
    """Build and compile the graph for mode ("corrective" as in M10, or "self_rag")."""
    if mode not in ("corrective", "self_rag"):
        raise ValueError(f"Unknown agentic mode: {mode!r}")
    graph = StateGraph(AgentState)
    _add_corrective_core(graph, deps)
    if mode == "self_rag":
        _add_self_rag_nodes(graph, deps)
        graph.add_edge(START, "decide_retrieval")
        graph.add_conditional_edges("decide_retrieval", route_next_step, _identity(DECIDE_BRANCHES))
        graph.add_edge("out_of_scope", END)
    else:
        graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "grade_documents")
    graph.add_conditional_edges("grade_documents", route_after_grading, _identity(GRADING_BRANCHES))
    graph.add_edge("rewrite_query", "retrieve")
    graph.add_edge("web_search", "generate")
    if mode == "self_rag":
        graph.add_edge("generate", "verify_answer")
        graph.add_conditional_edges("verify_answer", route_next_step, _identity(VERIFY_BRANCHES))
        graph.add_conditional_edges("regenerate", route_next_step, _identity(REGENERATE_BRANCHES))
        graph.add_edge("abstain", END)
    else:
        graph.add_edge("generate", END)
    return graph.compile(name=mode)


def bind_structured(chat_model: BaseChatModel, schema: type[BaseModel], settings: Settings) -> Any:
    """Bind a schema with the same structured-output method as the answer LLM (D23)."""
    method = settings.structured_output_method
    if method == "json_schema":
        return chat_model.with_structured_output(
            schema, method=method, strict=settings.structured_output_strict
        )
    return chat_model.with_structured_output(schema, method=method)


def build_default_deps() -> AgenticDeps:
    """Real dependencies from get_settings(): hybrid retriever, Groq models, Tavily search.

    get_retriever is lru_cached on its arguments, so it is called without Settings
    (as the baseline registry does) and reads get_settings() itself.
    """
    from ragdocs.generation.answer import build_structured_llm
    from ragdocs.providers.llm import get_chat_model
    from ragdocs.providers.websearch import TavilySearch
    from ragdocs.retrieval.retriever import get_retriever

    settings = get_settings()
    grader = get_chat_model("grader", settings)
    return AgenticDeps(
        retriever=get_retriever(),
        grader_llm=bind_structured(grader, GradeBatch, settings),
        rewriter_llm=bind_structured(grader, RewrittenQuery, settings),
        decider_llm=bind_structured(grader, RetrievalDecision, settings),
        verifier_llm=bind_structured(grader, AnswerVerification, settings),
        generator_llm=build_structured_llm(
            get_chat_model("generator", settings),
            method=settings.structured_output_method,
            strict=settings.structured_output_strict,
        ),
        web_search=TavilySearch(settings),
        settings=settings,
    )


def export_mermaid(mode: Mode) -> str:
    """Mermaid source of the compiled graph, drawn offline (draw_mermaid, never _png)."""
    placeholder = AgenticDeps(
        retriever=None,
        grader_llm=None,
        rewriter_llm=None,
        generator_llm=None,
        web_search=None,
        settings=None,
    )
    text = build_graph(mode, placeholder).get_graph().draw_mermaid()
    return text.rstrip("\n") + "\n"
