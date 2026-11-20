"""Tests for ragdocs.docs_urls and the ingest URL mapping that now uses it (M10). No network."""

from pathlib import Path

import pytest

from ragdocs.config import REPO_ROOT
from ragdocs.docs_urls import (
    DOCS_BASE_URL,
    chunk_url,
    doc_path_to_url,
    doc_ref_to_url,
    is_docs_host,
    known_doc_paths,
    url_to_doc_ref,
)
from ragdocs.ingest.chunk import chunk_document
from ragdocs.ingest.parse import parse_file
from ragdocs.io_utils import read_jsonl
from ragdocs.schemas import Evidence

CHUNK_META = REPO_ROOT / "data" / "index" / "chunk_meta.jsonl"
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _meta_rows() -> list[dict]:
    return list(read_jsonl(CHUNK_META))


def _sample_rows() -> list[dict]:
    """5 real chunks: with and without anchor, nested path, and a .md page."""
    rows = _meta_rows()
    picks = [
        next(r for r in rows if r["anchor"] and "/" not in r["doc_path"]),
        next(r for r in rows if not r["anchor"]),
        next(r for r in rows if "/" in r["doc_path"]),
        next(r for r in rows if r["doc_path"].endswith(".md")),
        rows[len(rows) // 2],
    ]
    assert len({r["chunk_id"] for r in picks}) == 5
    return picks


@pytest.mark.parametrize("row", _sample_rows(), ids=lambda r: r["chunk_id"])
def test_url_round_trip_on_real_chunks(row: dict) -> None:
    ref = url_to_doc_ref(row["url"])
    assert ref == Evidence(doc_path=row["doc_path"], anchor=row["anchor"])
    assert doc_ref_to_url(ref) == row["url"]


def test_url_to_doc_ref_rejects_unmapped_urls() -> None:
    assert url_to_doc_ref("https://example.com/oss/python/langgraph/add-memory") is None
    assert url_to_doc_ref("https://docs.langchain.com/oss/python/langchain/overview") is None
    assert url_to_doc_ref(f"{DOCS_BASE_URL}/no-such-page#x") is None
    assert url_to_doc_ref(DOCS_BASE_URL) is None


def test_url_to_doc_ref_tolerates_trailing_slash_and_query() -> None:
    row = next(r for r in _meta_rows() if r["anchor"])
    page = doc_path_to_url(row["doc_path"])
    ref = url_to_doc_ref(f"{page}/?utm=1#{row['anchor']}")
    assert ref == Evidence(doc_path=row["doc_path"], anchor=row["anchor"])


def test_every_index_url_follows_the_mapping() -> None:
    rows = _meta_rows()
    assert all(doc_ref_to_url(Evidence(**{k: r[k] for k in ("doc_path", "anchor")})) == r["url"]
               for r in rows)  # fmt: skip
    assert known_doc_paths() == frozenset(r["doc_path"] for r in rows)


def test_ingest_builds_urls_with_docs_urls() -> None:
    doc = parse_file(FIXTURES_DIR / "sample_guide.md", FIXTURES_DIR, DOCS_BASE_URL)
    assert doc.public_url == f"{DOCS_BASE_URL}/sample_guide"  # behaviour before the move
    assert doc.public_url == doc_path_to_url(doc.doc_path)
    chunks = chunk_document(doc, source_commit="x")
    assert any(c.anchor for c in chunks)
    for c in chunks:
        assert c.url == chunk_url(doc.public_url, c.anchor)
        assert c.url == doc_ref_to_url(Evidence(doc_path=c.doc_path, anchor=c.anchor))


def test_is_docs_host() -> None:
    assert is_docs_host("https://docs.langchain.com/x", "docs.langchain.com")
    assert is_docs_host("https://API.docs.langchain.com/x", "docs.langchain.com")
    assert not is_docs_host("https://python.langchain.com/x", "docs.langchain.com")
    assert not is_docs_host("https://docs.langchain.com.evil.io/x", "docs.langchain.com")
    assert not is_docs_host("not a url", "docs.langchain.com")
