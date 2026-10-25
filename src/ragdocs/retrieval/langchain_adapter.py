"""LangChain retriever adapter for HybridRetriever."""

from typing import Any

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict, Field

from ragdocs.retrieval.retriever import HybridRetriever, RetrievalMode


class DocsRetriever(BaseRetriever):
    """LangChain BaseRetriever wrapper over HybridRetriever."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    retriever: HybridRetriever = Field(description="Underlying HybridRetriever instance")
    mode: RetrievalMode = Field(
        default="hybrid_rerank",
        description="Retrieval mode to execute",
    )

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun | None = None,
        **kwargs: Any,
    ) -> list[Document]:
        """Retrieve relevant documents for the query, wrapping RetrievedChunk as Document."""
        chunks = self.retriever.retrieve(query=query, mode=self.mode)
        documents: list[Document] = []
        for rc in chunks:
            doc = Document(
                page_content=rc.chunk.text,
                metadata={
                    "chunk_id": rc.chunk.chunk_id,
                    "url": rc.chunk.url,
                    "title": rc.chunk.title,
                    "heading_path": rc.chunk.heading_path,
                    "score": rc.score,
                    "rank": rc.rank,
                },
            )
            documents.append(doc)
        return documents
