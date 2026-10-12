"""Tests for IO utilities ensuring deterministic LF and UTF-8 handling."""

from pathlib import Path

from ragdocs.io_utils import read_jsonl, read_text, write_jsonl, write_text


def test_write_jsonl_no_carriage_return(tmp_path: Path) -> None:
    """write_jsonl output must contain no carriage-return bytes (LF only)."""
    file_path = tmp_path / "records.jsonl"
    rows = [
        {"id": "doc1", "title": "First Document"},
        {"id": "doc2", "title": "Second Document"},
    ]
    write_jsonl(file_path, rows)

    raw_bytes = file_path.read_bytes()
    assert b"\r" not in raw_bytes
    assert raw_bytes.endswith(b"\n")


def test_write_read_jsonl_non_ascii_roundtrip(tmp_path: Path) -> None:
    """write_jsonl and read_jsonl correctly round-trip non-ASCII text without unicode escaping."""
    file_path = tmp_path / "unicode_records.jsonl"
    urdu_text = "یہ ایک امتحانی جملہ ہے — اردو دستاویز"
    em_dash_text = "Introduction — Overview and architecture"
    rows = [
        {"id": "urdu_1", "text": urdu_text, "language": "ur"},
        {"id": "dash_1", "text": em_dash_text, "language": "en"},
        {"id": "mixed_1", "symbols": "α, β, γ — π", "cjk": "自然言語処理"},
    ]
    write_jsonl(file_path, rows)

    # Verify bytes contain raw UTF-8 characters and no \u escaping
    raw_content = file_path.read_text(encoding="utf-8")
    assert "یہ ایک امتحانی جملہ ہے" in raw_content
    assert "—" in raw_content
    assert "\\u" not in raw_content

    # Verify round-trip equality
    loaded_rows = read_jsonl(file_path)
    assert loaded_rows == rows


def test_write_read_text_deterministic_newlines(tmp_path: Path) -> None:
    """write_text enforces LF newlines and read_text faithfully recovers UTF-8 content."""
    file_path = tmp_path / "document.txt"
    sample_text = "Heading — Main Title\nParagraph 1: متن کا نمونہ\nParagraph 2: English text\n"
    write_text(file_path, sample_text)

    raw_bytes = file_path.read_bytes()
    assert b"\r" not in raw_bytes
    assert read_text(file_path) == sample_text
