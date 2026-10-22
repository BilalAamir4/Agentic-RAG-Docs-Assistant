"""Unanswerable item absence checking and adjudication logic."""

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ragdocs.schemas import Chunk, EvalItem


class TermHit(BaseModel):
    """Details of a keyword match in a documentation chunk."""

    chunk_id: str
    doc_path: str
    anchor: str
    url: str
    snippet: str
    cleared: bool = False
    reason: str | None = None


class AbsenceCheckResult(BaseModel):
    """Aggregate result for absence verification across unanswerable items."""

    passed: bool
    item_hits: dict[str, dict[str, list[TermHit]]] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


def build_term_regex(term: str) -> re.Pattern[str]:
    """Build word-bounded, whitespace-normalized regex for a search term."""
    words = term.strip().split()
    escaped_words = [re.escape(w) for w in words]
    pattern = r"\s+".join(escaped_words)
    return re.compile(rf"(?<![A-Za-z0-9_]){pattern}(?![A-Za-z0-9_])", re.IGNORECASE)


def extract_chunk_full_text(chunk: dict[str, Any] | Chunk) -> str:
    """Concatenate all string fields of a chunk for keyword searching."""
    parts: list[str] = []
    data = chunk.model_dump() if isinstance(chunk, Chunk) else chunk
    for val in data.values():
        if isinstance(val, str):
            parts.append(val)
        elif isinstance(val, list):
            for elem in val:
                if isinstance(elem, str):
                    parts.append(elem)
    return " ".join(parts)


def extract_snippet(text: str, match: re.Match[str], window: int = 100) -> str:
    """Extract a context snippet of approximately 200 characters around the match."""
    start, end = match.span()
    snippet_start = max(0, start - window)
    snippet_end = min(len(text), end + window)
    raw = text[snippet_start:snippet_end].replace("\n", " ")
    snippet = " ".join(raw.split())
    if snippet_start > 0:
        snippet = f"...{snippet}"
    if snippet_end < len(text):
        snippet = f"{snippet}..."
    return snippet


def load_absence_terms(path: Path) -> dict[str, list[str]]:
    """Load search terms mapping from JSON file."""
    if not path.exists():
        return {}
    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)
    return {str(k): [str(t) for t in v] for k, v in data.items()}


def load_absence_adjudications(path: Path) -> dict[str, list[dict[str, Any]]]:
    """Load adjudication decisions from JSON file."""
    if not path.exists():
        return {}
    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)
    return {str(k): list(v) for k, v in data.items()}


def is_hit_cleared(
    item_id: str,
    term: str,
    chunk_id: str,
    adjudications_map: dict[str, list[dict[str, Any]]],
) -> tuple[bool, str | None]:
    """Determine whether a hit has been adjudicated as irrelevant."""
    records = adjudications_map.get(item_id, [])
    for rec in records:
        if (
            rec.get("term") == term
            and rec.get("chunk_id") == chunk_id
            and rec.get("verdict") == "irrelevant"
        ):
            return True, rec.get("reason", "Adjudicated as irrelevant")
    return False, None


def check_item_absence(
    item_id: str,
    terms: list[str],
    chunks: list[dict[str, Any] | Chunk],
    adjudications_map: dict[str, list[dict[str, Any]]],
) -> dict[str, list[TermHit]]:
    """Scan all chunks for an item's search terms and evaluate clearance."""
    results: dict[str, list[TermHit]] = {}

    for term in terms:
        pattern = build_term_regex(term)
        term_hits: list[TermHit] = []

        for c in chunks:
            data = c.model_dump() if isinstance(c, Chunk) else c
            full_text = extract_chunk_full_text(c)
            match = pattern.search(full_text)
            if match:
                chunk_id = str(data.get("chunk_id", ""))
                doc_path = str(data.get("doc_path", ""))
                anchor = str(data.get("anchor", ""))
                url = str(data.get("url", ""))
                cleared, reason = is_hit_cleared(item_id, term, chunk_id, adjudications_map)
                snippet = extract_snippet(full_text, match)
                term_hits.append(
                    TermHit(
                        chunk_id=chunk_id,
                        doc_path=doc_path,
                        anchor=anchor,
                        url=url,
                        snippet=snippet,
                        cleared=cleared,
                        reason=reason,
                    )
                )

        results[term] = term_hits

    return results


def check_all_unanswerable_absence(
    items: list[EvalItem],
    chunks: list[dict[str, Any] | Chunk],
    absence_terms_map: dict[str, list[str]],
    adjudications_map: dict[str, list[dict[str, Any]]],
) -> AbsenceCheckResult:
    """Run absence check for all unanswerable items against corpus chunks."""
    unanswerable_items = [it for it in items if it.category == "unanswerable"]
    item_hits: dict[str, dict[str, list[TermHit]]] = {}
    errors: list[str] = []

    for item in unanswerable_items:
        if item.id not in absence_terms_map:
            errors.append(f"Missing absence terms configuration for item {item.id}")
            continue

        terms = absence_terms_map[item.id]
        if not terms:
            errors.append(f"Item {item.id} has empty search terms list in absence_terms.json")
            continue

        hits = check_item_absence(item.id, terms, chunks, adjudications_map)
        item_hits[item.id] = hits

        for term, t_hits in hits.items():
            uncleared = [h for h in t_hits if not h.cleared]
            if uncleared:
                errors.append(
                    f"{item.id} term '{term}': {len(uncleared)} uncleared hit(s) "
                    f"in {[h.chunk_id for h in uncleared]}"
                )

    passed = len(errors) == 0
    return AbsenceCheckResult(passed=passed, item_hits=item_hits, errors=errors)
