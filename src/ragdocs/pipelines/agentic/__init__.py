"""Agentic RAG pipelines built as LangGraph StateGraphs (M10 corrective, M11 self-RAG).

Modules: state (graph state, LLM output schemas, deps), prompts (grader and rewriter
prompts), nodes (node functions), graph (build_graph, real deps, Mermaid export) and
pipeline (AgenticPipeline). Runtime-safe: nothing here imports ragdocs.eval or
ragdocs.ingest. Import submodules directly; this package imports nothing eagerly.
"""
