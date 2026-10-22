"""Tests for source quotes verification against page snapshots."""

import json
from pathlib import Path

from ragdocs.eval.validate import check_source_quotes_registered
from ragdocs.eval.verify_sources import verify_single_item
from ragdocs.schemas import EvalItem, Evidence


def create_snapshot(
    snapshots_dir: Path,
    item_id: str,
    title: str,
    author: str,
    body: str,
) -> Path:
    """Helper to create a test snapshot file."""
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    snap_path = snapshots_dir / f"{item_id}.txt"
    content = (
        f"Title: {title}\n"
        f"URL: https://forum.example.com/t/123\n\n"
        f"=== Post 1 by {author} ===\n"
        f"{body}\n"
    )
    snap_path.write_text(content, encoding="utf-8")
    return snap_path


def test_exact_substring_passes(tmp_path: Path) -> None:
    """Exact contiguous substring from the snapshot passes verification."""
    item_id = "q001"
    url = "https://forum.example.com/t/123"
    author = "alice"
    body = (
        "Hello everyone. How can I increase the recursion limit "
        "when running my app on a deployment? Any pointers?"
    )
    quote = "How can I increase the recursion limit when running my app on a deployment?"

    create_snapshot(tmp_path, item_id, "Increasing recursion limit", author, body)
    quotes_data = {
        item_id: {
            "url": url,
            "author": author,
            "post": "post 1",
            "quote": quote,
            "accessed": "2026-10-21",
        }
    }

    result = verify_single_item(item_id, url, quotes_data, tmp_path)
    assert result.passed
    assert not result.errors


def test_paraphrase_fails(tmp_path: Path) -> None:
    """A paraphrased quote that is not a contiguous substring fails verification."""
    item_id = "q001"
    url = "https://forum.example.com/t/123"
    author = "alice"
    body = (
        "Hello everyone. How can I increase the recursion limit "
        "when running my app on a deployment? Any pointers?"
    )
    paraphrase = "I want to increase my recursion limit in my deployment because it errors out."

    create_snapshot(tmp_path, item_id, "Increasing recursion limit", author, body)
    quotes_data = {
        item_id: {
            "url": url,
            "author": author,
            "post": "post 1",
            "quote": paraphrase,
            "accessed": "2026-10-21",
        }
    }

    result = verify_single_item(item_id, url, quotes_data, tmp_path)
    assert not result.passed
    assert any("contiguous substring" in err for err in result.errors)


def test_curly_quote_normalisation_passes(tmp_path: Path) -> None:
    """Quotes with curly quotes/apostrophes normalize and match straight quotes."""
    item_id = "q001"
    url = "https://forum.example.com/t/123"
    author = "alice"
    # Body has curly quotes “ ” and apostrophe ’
    body = "Hello, I can’t find the “correct way” to increase the recursion limit when deploying."
    # Quote uses straight quotes " " and apostrophe '
    quote = 'Hello, I can\'t find the "correct way" to increase the recursion limit when deploying.'

    create_snapshot(tmp_path, item_id, "Increasing recursion limit", author, body)
    quotes_data = {
        item_id: {
            "url": url,
            "author": author,
            "post": "post 1",
            "quote": quote,
            "accessed": "2026-10-21",
        }
    }

    result = verify_single_item(item_id, url, quotes_data, tmp_path)
    assert result.passed
    assert not result.errors


def test_title_as_quote_fails(tmp_path: Path) -> None:
    """Using the thread title as the quote fails verification."""
    item_id = "q001"
    url = "https://forum.example.com/t/123"
    author = "alice"
    title = "How to solve GRAPH_RECURSION_LIMIT error in langgraph"
    body = f"Here is my code for testing {title} in practice."

    create_snapshot(tmp_path, item_id, title, author, body)
    quotes_data = {
        item_id: {
            "url": url,
            "author": author,
            "post": "post 1",
            "quote": title,
            "accessed": "2026-10-21",
        }
    }

    result = verify_single_item(item_id, url, quotes_data, tmp_path)
    assert not result.passed
    assert any("identical to thread title" in err for err in result.errors)


def test_missing_snapshot_fails(tmp_path: Path) -> None:
    """A missing snapshot file fails verification."""
    item_id = "q001"
    url = "https://forum.example.com/t/123"
    author = "alice"
    quote = "How can I increase the recursion limit when running my app on a deployment?"

    quotes_data = {
        item_id: {
            "url": url,
            "author": author,
            "post": "post 1",
            "quote": quote,
            "accessed": "2026-10-21",
        }
    }

    result = verify_single_item(item_id, url, quotes_data, tmp_path)
    assert not result.passed
    assert any("snapshot file not found" in err for err in result.errors)


def test_wrong_author_fails(tmp_path: Path) -> None:
    """An author not appearing in the snapshot fails verification."""
    item_id = "q001"
    url = "https://forum.example.com/t/123"
    author_on_page = "alice"
    fake_author = "shlomo"
    body = "How can I increase the recursion limit when running my app on a deployment?"
    quote = "How can I increase the recursion limit when running my app on a deployment?"

    create_snapshot(tmp_path, item_id, "Increasing recursion limit", author_on_page, body)
    quotes_data = {
        item_id: {
            "url": url,
            "author": fake_author,
            "post": "post 1",
            "quote": quote,
            "accessed": "2026-10-21",
        }
    }

    result = verify_single_item(item_id, url, quotes_data, tmp_path)
    assert not result.passed
    assert any("author 'shlomo' not found" in err for err in result.errors)


def test_check_source_quotes_registered(tmp_path: Path) -> None:
    """Test 11th validator check for registering source quotes and snapshots."""
    item = EvalItem(
        id="q001",
        question="How do I raise recursion limit?",
        category="single",
        difficulty="medium",
        reference_answer="Pass recursion_limit in config.",
        evidence=[Evidence(doc_path="page1.mdx", anchor="sec1")],
        must_mention=["recursion_limit"],
        source="https://forum.example.com/t/123",
        verified=False,
    )

    quotes_file = tmp_path / "source_quotes.json"
    snapshots_dir = tmp_path / "snapshots"
    snapshots_dir.mkdir()

    # Case 1: Quotes file missing
    ok, err = check_source_quotes_registered([item], quotes_file, snapshots_dir)
    assert not ok
    assert "source_quotes.json not found" in err

    # Case 2: Snapshot file missing
    quotes_file.write_text(json.dumps({"q001": {"url": "..."}}), encoding="utf-8")
    ok, err = check_source_quotes_registered([item], quotes_file, snapshots_dir)
    assert not ok
    assert "missing snapshot files" in err

    # Case 3: Both present
    (snapshots_dir / "q001.txt").write_text("Title: Test", encoding="utf-8")
    ok, details = check_source_quotes_registered([item], quotes_file, snapshots_dir)
    assert ok
    assert "All 1 external source(s) have registered quotes" in details
