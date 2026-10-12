"""Tests for documentation parsing and chunking logic."""

from pathlib import Path

from ragdocs.ingest.chunk import chunk_document
from ragdocs.ingest.parse import parse_file

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_frontmatter_title_used():
    fixture_path = FIXTURES_DIR / "sample_guide.md"
    doc = parse_file(fixture_path, FIXTURES_DIR, "https://docs.langchain.com/oss/python/langgraph")
    assert doc.title == "Guide to Graphs"


def test_js_block_removed_and_python_kept():
    fixture_path = FIXTURES_DIR / "sample_guide.md"
    doc = parse_file(fixture_path, FIXTURES_DIR, "https://docs.langchain.com/oss/python/langgraph")
    assert "intro_func" in doc.body
    assert "python_only" in doc.body
    assert "introFunc" not in doc.body
    assert "js_only" not in doc.body
    assert ":::python" not in doc.body
    assert ":::js" not in doc.body


def test_heading_path_correct_for_h2_and_h3():
    fixture_path = FIXTURES_DIR / "sample_guide.md"
    doc = parse_file(fixture_path, FIXTURES_DIR, "https://docs.langchain.com/oss/python/langgraph")
    chunks = chunk_document(doc, source_commit="abc1234")

    # Find chunk for Principle Two
    p2_chunks = [c for c in chunks if c.heading_path == ["Core Principles", "Principle Two"]]
    assert len(p2_chunks) >= 1
    assert p2_chunks[0].anchor == "principle-two"


def test_tiny_section_merged():
    fixture_path = FIXTURES_DIR / "sample_guide.md"
    doc = parse_file(fixture_path, FIXTURES_DIR, "https://docs.langchain.com/oss/python/langgraph")
    chunks = chunk_document(doc, source_commit="abc1234")

    # Principle One is under 80 tokens, followed by Principle Two
    # with the same parent heading 'Core Principles'.
    # Principle One should have merged into Principle Two.
    p1_chunks = [c for c in chunks if c.anchor == "principle-one"]
    assert len(p1_chunks) == 0

    p2_chunks = [c for c in chunks if c.anchor == "principle-two"]
    assert len(p2_chunks) >= 1
    assert "This is a tiny section under 80 tokens" in p2_chunks[0].text
    assert "Here is the detailed second principle" in p2_chunks[0].text


def test_long_section_split_at_paragraph_boundary():
    fixture_path = FIXTURES_DIR / "sample_guide.md"
    doc = parse_file(fixture_path, FIXTURES_DIR, "https://docs.langchain.com/oss/python/langgraph")
    chunks = chunk_document(doc, source_commit="abc1234")

    adv_chunks = [c for c in chunks if c.heading_path == ["Advanced Graph Execution"]]
    # The advanced section has > 450 tokens, so it must be split into multiple pieces
    assert len(adv_chunks) >= 2


def test_code_fence_never_split():
    fixture_path = FIXTURES_DIR / "sample_guide.md"
    doc = parse_file(fixture_path, FIXTURES_DIR, "https://docs.langchain.com/oss/python/langgraph")
    chunks = chunk_document(doc, source_commit="abc1234")

    for chunk in chunks:
        lines = [line.strip() for line in chunk.text.splitlines() if line.strip().startswith("```")]
        assert len(lines) % 2 == 0, f"Unbalanced code fence in chunk: {chunk.chunk_id}"


def test_chunk_id_stable_across_two_runs():
    fixture_path = FIXTURES_DIR / "sample_guide.md"
    doc = parse_file(fixture_path, FIXTURES_DIR, "https://docs.langchain.com/oss/python/langgraph")
    chunks_1 = chunk_document(doc, source_commit="abc1234")
    chunks_2 = chunk_document(doc, source_commit="abc1234")

    ids_1 = [c.chunk_id for c in chunks_1]
    ids_2 = [c.chunk_id for c in chunks_2]
    assert ids_1 == ids_2


def test_embed_text_format():
    fixture_path = FIXTURES_DIR / "sample_guide.md"
    doc = parse_file(fixture_path, FIXTURES_DIR, "https://docs.langchain.com/oss/python/langgraph")
    chunks = chunk_document(doc, source_commit="abc1234")

    for chunk in chunks:
        if chunk.heading_path:
            expected_prefix = f"{chunk.title} > {' > '.join(chunk.heading_path)}\n\n"
        else:
            expected_prefix = f"{chunk.title}\n\n"
        assert chunk.embed_text.startswith(expected_prefix)
        assert chunk.embed_text.endswith(chunk.text)
