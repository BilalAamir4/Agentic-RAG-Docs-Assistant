"""Source quote verification against snapshot files."""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ragdocs.schemas import EvalItem


def normalize_quote_text(text: str) -> str:
    """Normalize text by unifying quotes, apostrophes and collapsing whitespace."""
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("‘", "'").replace("’", "'").replace("`", "'")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_snapshot_title(snapshot_text: str) -> str:
    """Extract thread title from the snapshot text header if present."""
    for line in snapshot_text.splitlines():
        if line.startswith("Title:"):
            return line[len("Title:") :].strip()
    return ""


@dataclass
class ItemVerificationResult:
    """Result of verifying a single item's source quote."""

    item_id: str
    passed: bool
    errors: list[str]


def verify_single_item(
    item_id: str,
    item_source: str,
    quotes_data: dict[str, Any],
    snapshots_dir: Path,
) -> ItemVerificationResult:
    """Verify that an item's source quote meets all verbatim matching rules.

    Checks:
    a) entry exists in source_quotes.json and url equals item_source;
    b) snapshot file exists;
    c) normalised quote is contiguous substring of normalised snapshot, no ellipses;
    d) author (unless starting with 'unknown') appears in snapshot;
    e) quote != thread title and len(quote) >= 40.
    """
    errors: list[str] = []

    # Check a: Entry exists in source_quotes.json and URL matches
    if item_id not in quotes_data:
        errors.append(f"{item_id}: missing entry in source_quotes.json")
        return ItemVerificationResult(item_id, False, errors)

    entry = quotes_data[item_id]
    entry_url = entry.get("url", "")
    if entry_url != item_source:
        errors.append(
            f"{item_id}: URL mismatch (eval_set source '{item_source}' "
            f"!= quotes json '{entry_url}')"
        )

    # Check b: Snapshot exists
    snap_path = snapshots_dir / f"{item_id}.txt"
    if not snap_path.exists():
        errors.append(f"{item_id}: snapshot file not found at {snap_path}")
        return ItemVerificationResult(item_id, False, errors)

    snapshot_raw = snap_path.read_text(encoding="utf-8")
    snapshot_norm = normalize_quote_text(snapshot_raw)

    raw_quote = entry.get("quote", "")
    quote_norm = normalize_quote_text(raw_quote)

    # Check c: No ellipses inside quote & contiguous substring
    if "..." in raw_quote or "…" in raw_quote:
        errors.append(f"{item_id}: quote contains ellipses")

    if quote_norm not in snapshot_norm:
        errors.append(f"{item_id}: normalised quote is not a contiguous substring of snapshot")

    # Check d: Author appears in snapshot
    author = entry.get("author", "").strip()
    if not author.lower().startswith("unknown"):
        if author not in snapshot_raw:
            errors.append(f"{item_id}: author '{author}' not found in snapshot")

    # Check e: Quote not equal to thread title and len >= 40
    title = extract_snapshot_title(snapshot_raw)
    title_norm = normalize_quote_text(title)
    if quote_norm == title_norm and title_norm:
        errors.append(f"{item_id}: quote is identical to thread title")

    if len(quote_norm) < 40:
        errors.append(
            f"{item_id}: quote length {len(quote_norm)} is shorter than minimum 40 characters"
        )

    return ItemVerificationResult(item_id, len(errors) == 0, errors)


def verify_all_source_quotes(
    items: list[EvalItem],
    quotes_path: Path,
    snapshots_dir: Path,
) -> tuple[bool, list[ItemVerificationResult]]:
    """Verify all items in eval set that have non-'docs' source."""
    if not quotes_path.exists():
        return False, [
            ItemVerificationResult(
                "global", False, [f"source_quotes.json not found at {quotes_path}"]
            )
        ]

    with open(quotes_path, encoding="utf-8") as f:
        quotes_data = json.load(f)

    results: list[ItemVerificationResult] = []
    all_ok = True

    non_docs_items = [it for it in items if it.source != "docs"]
    for it in non_docs_items:
        res = verify_single_item(
            item_id=it.id,
            item_source=it.source,
            quotes_data=quotes_data,
            snapshots_dir=snapshots_dir,
        )
        results.append(res)
        if not res.passed:
            all_ok = False

    return all_ok, results
