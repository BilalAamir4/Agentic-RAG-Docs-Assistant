"""Live integration test for Gemini embeddings provider."""

import numpy as np
import pytest

from ragdocs.providers.embeddings import GeminiEmbedder


@pytest.mark.live
def test_gemini_embedder_live_query() -> None:
    embedder = GeminiEmbedder()
    vec = embedder.embed_query("How do I create a LangGraph StateGraph?")

    assert isinstance(vec, np.ndarray)
    assert vec.dtype == np.float32
    assert vec.shape == (768,)

    norm = float(np.linalg.norm(vec))
    assert abs(norm - 1.0) < 1e-3
