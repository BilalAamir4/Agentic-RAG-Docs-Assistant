"""Unit tests for tokenizer, BM25Index, VectorIndex, and index loader."""

import json
from pathlib import Path

import numpy as np
import pytest

from ragdocs.index.bm25_index import BM25Index, tokenize
from ragdocs.index.loader import _sha256_file, load_index
from ragdocs.index.vector_index import VectorIndex
from ragdocs.schemas import Chunk


def test_tokenizer_snake_case() -> None:
    tokens = tokenize("my_custom_node")
    assert "my_custom_node" in tokens
    assert "custom" in tokens
    assert "node" in tokens


def test_tokenizer_camel_case() -> None:
    tokens = tokenize("StateGraph")
    assert "stategraph" in tokens
    assert "state" in tokens
    assert "graph" in tokens


def test_tokenizer_dotted_import() -> None:
    tokens = tokenize("langgraph.checkpoint.base")
    assert "langgraph" in tokens
    assert "checkpoint" in tokens
    assert "base" in tokens


def test_tokenizer_stopwords_and_single_char() -> None:
    tokens = tokenize("a the is checkpointer x")
    assert "checkpointer" in tokens
    assert "a" not in tokens
    assert "the" not in tokens
    assert "is" not in tokens
    assert "x" not in tokens


def test_bm25_fixture_ranks_obvious_document_first(tmp_path: Path) -> None:
    docs = [
        "langgraph stategraph nodes edges compilation",
        "sqlite database storage persistence checkpoints",
        "human interrupt resume approval workflow",
        "streaming events messages tokens values",
        "subgraph parent child communication nesting",
    ]
    tokens = [tokenize(d) for d in docs]
    bm25_data = {"tokenizer_version": 1, "tokens": tokens}
    bm25_file = tmp_path / "bm25.json"
    with open(bm25_file, "w", encoding="utf-8") as f:
        json.dump(bm25_data, f)

    index = BM25Index.load(bm25_file)
    results = index.search("interrupt approval workflow", k=3)

    assert len(results) > 0
    top_row, top_score = results[0]
    assert top_row == 2
    assert top_score > 0.0


def test_vector_index_search_order() -> None:
    # 4 vectors in 3 dimensions
    vectors = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.6, 0.8, 0.0],
        ],
        dtype=np.float32,
    )
    dummy_chunk = Chunk(
        chunk_id="c0",
        doc_path="test.mdx",
        url="https://docs.langchain.com/test",
        title="Test",
        heading_path=["H1"],
        anchor="h1",
        text="text",
        embed_text="embed",
        n_tokens=10,
        has_code=False,
        source_commit="commit",
    )
    chunks = [dummy_chunk.model_copy(update={"chunk_id": f"c{i}"}) for i in range(4)]
    v_index = VectorIndex(vectors=vectors, chunks=chunks)

    query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    results = v_index.search(query, k=4)

    ranked_rows = [r[0] for r in results]
    assert ranked_rows[0] == 0
    assert ranked_rows[1] == 3
    assert v_index.chunk(0).chunk_id == "c0"
    assert v_index.chunk(3).chunk_id == "c3"


def test_loader_raises_on_tampered_hash(tmp_path: Path) -> None:
    # Set up mock valid index directory
    vec_data = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float16)
    vec_path = tmp_path / "vectors.f16.npy"
    np.save(vec_path, vec_data)

    dummy_chunk = {
        "chunk_id": "c1",
        "doc_path": "doc.mdx",
        "url": "https://example.com",
        "title": "Doc",
        "heading_path": ["H"],
        "anchor": "a",
        "text": "t",
        "embed_text": "e",
        "n_tokens": 5,
        "has_code": False,
        "source_commit": "abc",
    }
    meta_path = tmp_path / "chunk_meta.jsonl"
    with open(meta_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(dummy_chunk) + "\n")
        f.write(json.dumps(dummy_chunk) + "\n")

    bm25_data = {"tokenizer_version": 1, "tokens": [["token1"], ["token2"]]}
    bm25_path = tmp_path / "bm25.json"
    with open(bm25_path, "w", encoding="utf-8") as f:
        json.dump(bm25_data, f)

    manifest = {
        "built_on": "2026-10-22T00:00:00Z",
        "source_commit": "abc",
        "chunks_sha256": "fake",
        "n_chunks": 2,
        "embedding_model": "gemini-embedding-001",
        "embedding_dim": 2,
        "files": {
            "vectors.f16.npy": _sha256_file(vec_path),
            "chunk_meta.jsonl": _sha256_file(meta_path),
            "bm25.json": _sha256_file(bm25_path),
        },
    }
    manifest_path = tmp_path / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    # First verify it loads without error
    loaded = load_index(tmp_path)
    assert len(loaded.vector_index.vectors) == 2

    # Now tamper with bm25.json
    with open(bm25_path, "a", encoding="utf-8") as f:
        f.write(" ")

    with pytest.raises(ValueError, match="Index checksum mismatch"):
        load_index(tmp_path)
