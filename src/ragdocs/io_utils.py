"""IO utilities for text and JSONL files with deterministic UTF-8 and LF line endings."""

import json
from pathlib import Path
from typing import Any


def read_text(path: Path | str) -> str:
    """Read full text content from path using UTF-8 encoding."""
    p = Path(path)
    with open(p, encoding="utf-8") as f:
        return f.read()


def write_text(path: Path | str, content: str) -> None:
    """Write text content to path using UTF-8 encoding and LF line endings."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def read_jsonl(path: Path | str) -> list[dict[str, Any]]:
    """Read a JSONL file into a list of dictionaries."""
    p = Path(path)
    rows: list[dict[str, Any]] = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def write_jsonl(path: Path | str, rows: list[dict[str, Any]]) -> None:
    """Write dictionaries to a JSONL file.

    Enforces UTF-8 encoding, LF line endings, and ensure_ascii=False.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            line = json.dumps(row, ensure_ascii=False, sort_keys=False)
            f.write(line + "\n")
