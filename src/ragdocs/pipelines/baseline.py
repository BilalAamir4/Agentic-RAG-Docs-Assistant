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
from ragdocs.schemas import PipelineResult, RetrievedChunk, TraceEvent


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

    def stream(self, question: str) -> Iterator[TraceEvent]:
        """Execute baseline pipeline and stream progress TraceEvents.

        Yields:
            1. node_start 'retrieve'
            2. retrieval event with candidate summaries
            3. node_start 'generate'
            4. node_end 'generate' with validation diagnostics
            5. answer event with PipelineResult data dump
            Or on error: one error event with safe message, then stops.
        """
        start_time = time.perf_counter()

        def t_ms() -> int:
            return int((time.perf_counter() - start_time) * 1000)

        trace: list[TraceEvent] = []

        try:
            # 1. node_start "retrieve"
            e_start_retrieve = TraceEvent(
                type="node_start",
                node="retrieve",
                message="Retrieving documentation excerpts",
                t_ms=t_ms(),
            )
            trace.append(e_start_retrieve)
            yield e_start_retrieve

            # Retrieve candidate excerpts
            mode = getattr(self.retriever, "mode", None)
            if mode:
                chunks = self.retriever.retrieve(question, mode=mode)
            else:
                chunks = self.retriever.retrieve(question)

            retrieval_mode = getattr(self.retriever, "mode", "hybrid") if mode is None else mode
            chunks_summary = []
            for c in chunks:
                chunk_obj = c.chunk if isinstance(c, RetrievedChunk) else c
                score = c.score if isinstance(c, RetrievedChunk) else 0.0
                rank = c.rank if isinstance(c, RetrievedChunk) else 0
                chunks_summary.append(
                    {
                        "rank": rank,
                        "title": chunk_obj.title,
                        "heading_path": chunk_obj.heading_path,
                        "url": chunk_obj.url,
                        "score": score,
                    }
                )

            # 2. retrieval event
            e_retrieval = TraceEvent(
                type="retrieval",
                node="retrieve",
                message="Retrieved candidate excerpts",
                data={"mode": retrieval_mode, "chunks": chunks_summary},
                t_ms=t_ms(),
            )
            trace.append(e_retrieval)
            yield e_retrieval

            # 3. node_start "generate"
            e_start_gen = TraceEvent(
                type="node_start",
                node="generate",
                message="Generating cited answer",
                t_ms=t_ms(),
            )
            trace.append(e_start_gen)
            yield e_start_gen

            # Invoke generation with CallCounter
            counter = CallCounter()
            context = format_context(chunks)
            messages = [
                SystemMessage(content=ANSWER_SYSTEM_PROMPT),
                HumanMessage(
                    content=ANSWER_USER_TEMPLATE.format(question=question, context=context)
                ),
            ]

            # Pass config callbacks to structured_llm if supported
            try:
                draft = self.structured_llm.invoke(messages, config={"callbacks": [counter]})
            except TypeError:
                # Stub or protocol implementation without config keyword
                draft = self.structured_llm.invoke(messages)

            answer, diagnostics = validate_answer(draft, chunks)

            # 4. node_end "generate"
            e_end_gen = TraceEvent(
                type="node_end",
                node="generate",
                message="Answer generated and validated",
                data=diagnostics,
                t_ms=t_ms(),
            )
            trace.append(e_end_gen)
            yield e_end_gen

            # 5. answer event
            pipeline_result = PipelineResult(
                question=question,
                pipeline=self.name,
                answer=answer,
                contexts=chunks,
                trace=trace,
                llm_calls=counter.llm_calls,
                latency_ms=t_ms(),
                used_web=False,
            )

            e_answer = TraceEvent(
                type="answer",
                node="answer",
                message="Pipeline execution finished",
                data=pipeline_result.model_dump(),
                t_ms=t_ms(),
            )
            trace.append(e_answer)
            # Ensure full trace including e_answer is in final data dump
            pipeline_result.trace = trace
            e_answer.data = pipeline_result.model_dump()
            yield e_answer

        except Exception as exc:
            e_err = TraceEvent(
                type="error",
                node="error",
                message=safe_error_message(exc),
                t_ms=t_ms(),
            )
            trace.append(e_err)
            yield e_err
