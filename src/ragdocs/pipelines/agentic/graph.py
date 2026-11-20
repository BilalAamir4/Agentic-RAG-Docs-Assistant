"""LangGraph construction for the agentic pipelines (M10 corrective; M11 self-RAG).

Graph (corrective):
    START -> retrieve -> grade_documents -> {generate | rewrite_query | web_search}
    rewrite_query -> retrieve; web_search -> generate; generate -> END
With max_query_rewrites = 1 the worst case is 4 LLM calls: grade, rewrite, grade,
generate.

Runtime-safe: never imports ragdocs.eval or ragdocs.ingest.
"""

from functools import partial
from typing import Any, Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from ragdocs.config import Settings, get_settings
from ragdocs.pipelines.agentic import nodes
from ragdocs.pipelines.agentic.state import AgenticDeps, AgentState, GradeBatch, RewrittenQuery

Mode = Literal["corrective", "self_rag"]
# Branches of the conditional edge after grade_documents (identity path_map for drawing).
GRADING_BRANCHES = ("generate", "rewrite_query", "web_search")


def route_after_grading(state: AgentState) -> str:
    """Return the branch grade_documents stored in next_step (no events, no updates)."""
    return str(state["next_step"])


def build_graph(mode: Mode, deps: AgenticDeps) -> Any:
    """Build and compile the graph for mode; 'self_rag' is not implemented yet (M11)."""
    if mode == "self_rag":
        raise NotImplementedError("M11")
    if mode != "corrective":
        raise ValueError(f"Unknown agentic mode: {mode!r}")
    graph = StateGraph(AgentState)
    graph.add_node("retrieve", partial(nodes.retrieve, deps=deps))
    graph.add_node("grade_documents", partial(nodes.grade_documents, deps=deps))
    graph.add_node("rewrite_query", partial(nodes.rewrite_query, deps=deps))
    graph.add_node("web_search", partial(nodes.web_search, deps=deps))
    graph.add_node("generate", partial(nodes.generate, deps=deps))
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "grade_documents")
    graph.add_conditional_edges(
        "grade_documents", route_after_grading, {b: b for b in GRADING_BRANCHES}
    )
    graph.add_edge("rewrite_query", "retrieve")
    graph.add_edge("web_search", "generate")
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
