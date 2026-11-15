"""Baseline RAG pipeline implemented as an LCEL chain with streaming trace events."""

import time
from collections.abc import Iterator
from operator import itemgetter
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

from ragdocs.generation.answer import (
    StructuredLLM,
    format_context,
    validate_answer,
)
from ragdocs.generation.prompts import (
    ANSWER_SYSTEM_PROMPT,
    ANSWER_USER_TEMPLATE,
)
from ragdocs.pipelines.base import Pipeline, safe_error_message
from ragdocs.providers.llm import CallCounter
from ragdocs.schemas import Answer, PipelineResult, RetrievedChunk, TraceEvent
from ragdocs.tracing import TracedRun, traced_run


class BaselinePipeline(Pipeline):
    """Baseline LCEL RAG pipeline retrieving chunks and generating cited answers."""

    def __init__(
        self,
        retriever: Any,
        structured_llm: StructuredLLM,
        name: str = "baseline",
    ) -> None:
        self.name = name
        self.retriever = retriever
        self.structured_llm = structured_llm

        # Reusable LCEL steps
        self.retrieve_and_format_step = RunnableLambda(self._retrieve_and_format)
        self.post_process_step = RunnableLambda(self._post_process)

        # Full LCEL execution chain
        self.chain = (
            self.retrieve_and_format_step
            | RunnablePassthrough.assign(
                draft=itemgetter("messages")
                | RunnableLambda(lambda msgs: self.structured_llm.invoke(msgs))
            )
            | self.post_process_step
        )

    def _retrieve_and_format(self, input_data: str | dict[str, Any]) -> dict[str, Any]:
        """Retrieve relevant chunks and construct formatted prompt messages."""
        question = input_data["question"] if isinstance(input_data, dict) else input_data
        mode = getattr(self.retriever, "mode", None)
        if mode:
            chunks = self.retriever.retrieve(question, mode=mode)
        else:
            chunks = self.retriever.retrieve(question)

        context = format_context(chunks)
        messages = [
            SystemMessage(content=ANSWER_SYSTEM_PROMPT),
            HumanMessage(content=ANSWER_USER_TEMPLATE.format(question=question, context=context)),
        ]
        return {
            "question": question,
            "chunks": chunks,
            "messages": messages,
        }

    def _post_process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Validate answer draft against candidate chunks."""
        draft = input_data["draft"]
        chunks = input_data["chunks"]
        answer, diagnostics = validate_answer(draft, chunks)
        return {
            "question": input_data["question"],
            "chunks": chunks,
            "answer": answer,
            "diagnostics": diagnostics,
        }

    def stream(
        self, question: str, run_metadata: dict[str, Any] | None = None
    ) -> Iterator[TraceEvent]:
        """Execute baseline pipeline and stream progress TraceEvents.

        Yields:
            1. node_start 'retrieve'
            2. retrieval event with candidate summaries
            3. node_start 'generate'
            4. node_end 'generate' with validation diagnostics
            5. answer event with PipelineResult data dump
            Or on error: one error event with safe message, then stops.

        When LangSmith tracing is enabled the run is recorded as one trace: a parent run
        named after the pipeline with 'hybrid_retrieve' and 'generate' children.
        run_metadata is added to the parent run and generate run metadata; it never
        changes the yielded events.
        """
        metadata = {"pipeline": self.name, **(run_metadata or {})}
        with traced_run(
            name=self.name,
            run_type="chain",
            inputs={"question": question},
            metadata=metadata,
        ) as parent:
            yield from self._stream_events(question, metadata, parent)

    def _retrieve_traced(self, question: str) -> list[Any]:
        """Retrieve chunks inside a 'hybrid_retrieve' retriever run."""
        with traced_run(
            name="hybrid_retrieve", run_type="retriever", inputs={"query": question}
        ) as run:
            mode = getattr(self.retriever, "mode", None)
            if mode:
                chunks = self.retriever.retrieve(question, mode=mode)
            else:
                chunks = self.retriever.retrieve(question)
            run.set_outputs({"documents": [_as_trace_document(c) for c in chunks]})
        return chunks

    def _generate(
        self, question: str, chunks: list[Any], metadata: dict[str, Any]
    ) -> tuple[Answer, dict[str, Any], int]:
        """Invoke the structured LLM as run 'generate' and validate its draft.

        Returns the validated answer, diagnostics and the counted LLM calls.
        """
        counter = CallCounter()
        context = format_context(chunks)
        messages = [
            SystemMessage(content=ANSWER_SYSTEM_PROMPT),
            HumanMessage(content=ANSWER_USER_TEMPLATE.format(question=question, context=context)),
        ]
        draft = self.structured_llm.invoke(
            messages,
            config={"callbacks": [counter], "run_name": "generate", "metadata": metadata},
        )
        answer, diagnostics = validate_answer(draft, chunks)
        return answer, diagnostics, counter.llm_calls

    def _stream_events(
        self, question: str, metadata: dict[str, Any], parent: TracedRun
    ) -> Iterator[TraceEvent]:
        """Yield the baseline TraceEvents in the order documented on stream()."""
        start_time = time.perf_counter()

        def t_ms() -> int:
            return int((time.perf_counter() - start_time) * 1000)

        trace: list[TraceEvent] = []

        def emit(event_type: Any, node: str, message: str, data: Any = None) -> TraceEvent:
            event = TraceEvent(
                type=event_type, node=node, message=message, data=data or {}, t_ms=t_ms()
            )
            trace.append(event)
            return event

        try:
            yield emit("node_start", "retrieve", "Retrieving documentation excerpts")
            mode = getattr(self.retriever, "mode", None)
            chunks = self._retrieve_traced(question)
            retrieval_mode = getattr(self.retriever, "mode", "hybrid") if mode is None else mode
            yield emit(
                "retrieval",
                "retrieve",
                "Retrieved candidate excerpts",
                {"mode": retrieval_mode, "chunks": [_chunk_summary(c) for c in chunks]},
            )
            yield emit("node_start", "generate", "Generating cited answer")
            answer, diagnostics, llm_calls = self._generate(question, chunks, metadata)
            yield emit("node_end", "generate", "Answer generated and validated", diagnostics)

            pipeline_result = PipelineResult(
                question=question,
                pipeline=self.name,
                answer=answer,
                contexts=chunks,
                trace=trace,
                llm_calls=llm_calls,
                latency_ms=t_ms(),
                used_web=False,
            )
            e_answer = emit(
                "answer", "answer", "Pipeline execution finished", pipeline_result.model_dump()
            )
            # Ensure full trace including e_answer is in final data dump
            pipeline_result.trace = trace
            e_answer.data = pipeline_result.model_dump()
            parent.set_outputs(_parent_outputs(pipeline_result))
            yield e_answer

        except Exception as exc:
            e_err = emit("error", "error", safe_error_message(exc))
            parent.set_error(e_err.message)
            yield e_err


def _parent_outputs(result: PipelineResult) -> dict[str, Any]:
    """Summarise a PipelineResult as the outputs of the pipeline parent run."""
    return {
        "answer": result.answer.text,
        "abstained": result.answer.abstained,
        "n_citations": len(result.answer.citations),
        "llm_calls": result.llm_calls,
        "latency_ms": result.latency_ms,
    }


def _rank_and_score(c: Any) -> tuple[Any, int, float]:
    """Return (chunk, rank, score) for a RetrievedChunk or a bare Chunk."""
    if isinstance(c, RetrievedChunk):
        return c.chunk, c.rank, c.score
    return c, 0, 0.0


def _chunk_summary(c: Any) -> dict[str, Any]:
    """Summarise a retrieved chunk for the retrieval TraceEvent."""
    chunk_obj, rank, score = _rank_and_score(c)
    return {
        "rank": rank,
        "title": chunk_obj.title,
        "heading_path": chunk_obj.heading_path,
        "url": chunk_obj.url,
        "score": score,
    }


def _as_trace_document(c: Any) -> dict[str, Any]:
    """Format a chunk in the document shape LangSmith renders for retriever runs."""
    chunk_obj, rank, score = _rank_and_score(c)
    return {
        "page_content": chunk_obj.text,
        "type": "Document",
        "metadata": {
            "chunk_id": chunk_obj.chunk_id,
            "url": chunk_obj.url,
            "rank": rank,
            "score": score,
        },
    }
