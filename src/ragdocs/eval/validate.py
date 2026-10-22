"""Validation logic for the evaluation dataset."""

import json
import string
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ragdocs.eval.absence import (
    check_all_unanswerable_absence,
    load_absence_adjudications,
    load_absence_terms,
)
from ragdocs.eval.config import MIN_REAL_SOURCES
from ragdocs.schemas import Chunk, EvalItem

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_TERMS_PATH = REPO_ROOT / "data" / "eval" / "absence_terms.json"
DEFAULT_ADJUDICATIONS_PATH = REPO_ROOT / "data" / "eval" / "absence_adjudication.json"
DEFAULT_QUOTES_PATH = REPO_ROOT / "data" / "eval" / "source_quotes.json"
DEFAULT_SNAPSHOTS_DIR = REPO_ROOT / "data" / "eval" / "source_snapshots"


@dataclass
class CheckResult:
    """Result of a single validation check."""

    name: str
    passed: bool
    details: str


@dataclass
class ValidationReport:
    """Summary of all evaluation validation checks."""

    passed: bool
    checks: list[CheckResult]

    def format_summary(self) -> str:
        """Format report into human-readable output."""
        lines = ["=== Evaluation Dataset Validation Report ==="]
        for c in self.checks:
            status = "PASS" if c.passed else "FAIL"
            lines.append(f"[{status}] {c.name}: {c.details}")
        lines.append("=" * 44)
        lines.append(f"Overall Result: {'PASSED' if self.passed else 'FAILED'}")
        return "\n".join(lines)


def tokenize_words(text: str) -> list[str]:
    """Tokenize text into lowercase words with punctuation removed."""
    translator = str.maketrans({c: " " for c in string.punctuation})
    clean = text.lower().translate(translator)
    return clean.split()


def extract_4grams(words: list[str]) -> set[tuple[str, ...]]:
    """Extract all consecutive 4-word tuples from a token list."""
    if len(words) < 4:
        return set()
    return {tuple(words[i : i + 4]) for i in range(len(words) - 3)}


def find_4gram_overlaps(question: str, evidence_texts: list[str]) -> list[str]:
    """Find any 4-word sequences shared between question and evidence texts."""
    q_words = tokenize_words(question)
    q_grams = extract_4grams(q_words)
    if not q_grams:
        return []

    evidence_grams: set[tuple[str, ...]] = set()
    for text in evidence_texts:
        e_words = tokenize_words(text)
        evidence_grams.update(extract_4grams(e_words))

    overlap = q_grams & evidence_grams
    return [" ".join(gram) for gram in sorted(overlap)]


def load_chunks_lookup(
    chunks: list[Chunk] | list[dict[str, Any]],
) -> tuple[dict[tuple[str, str], list[str]], set[str]]:
    """Build lookup tables from chunks.

    Returns:
        tuple containing:
        - map of (doc_path, anchor) -> list of chunk texts
        - list of all chunk texts across the corpus
    """
    evidence_map: dict[tuple[str, str], list[str]] = {}
    all_texts: set[str] = set()

    for c in chunks:
        doc_path = c.doc_path if isinstance(c, Chunk) else c["doc_path"]
        anchor = c.anchor if isinstance(c, Chunk) else c["anchor"]
        text = c.text if isinstance(c, Chunk) else c["text"]

        key = (doc_path, anchor)
        evidence_map.setdefault(key, []).append(text)
        all_texts.add(text)

    return evidence_map, all_texts


def check_parsing(
    raw_lines: list[str],
) -> tuple[bool, list[EvalItem], str]:
    """Check that every line parses as an EvalItem."""
    items: list[EvalItem] = []
    errors: list[str] = []

    for idx, line in enumerate(raw_lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            data = json.loads(stripped)
            item = EvalItem.model_validate(data)
            items.append(item)
        except Exception as exc:
            errors.append(f"Line {idx}: {exc}")

    if errors:
        return False, items, f"Parsing failed for {len(errors)} line(s): {'; '.join(errors[:3])}"
    return True, items, f"Successfully parsed {len(items)} items"


def check_ids(items: list[EvalItem]) -> tuple[bool, str]:
    """Check that ids are unique and exactly q001..q050."""
    expected_ids = [f"q{i:03d}" for i in range(1, 51)]
    actual_ids = [item.id for item in items]

    if len(actual_ids) != 50:
        return False, f"Expected 50 items, got {len(actual_ids)}"
    if actual_ids != expected_ids:
        missing = [i for i in expected_ids if i not in actual_ids]
        unexpected = [i for i in actual_ids if i not in expected_ids]
        return False, f"ID sequence mismatch. Missing: {missing[:3]}, Unexpected: {unexpected[:3]}"
    return True, "IDs are unique and exactly q001..q050"


def check_category_counts(items: list[EvalItem]) -> tuple[bool, str]:
    """Check that categories match exact distribution counts."""
    counts = {
        "single": sum(1 for it in items if it.category == "single"),
        "multi": sum(1 for it in items if it.category == "multi"),
        "version": sum(1 for it in items if it.category == "version"),
        "unanswerable": sum(1 for it in items if it.category == "unanswerable"),
    }
    count_summary = (
        f"single={counts['single']}/28, multi={counts['multi']}/8, "
        f"version={counts['version']}/6, unanswerable={counts['unanswerable']}/8"
    )

    expected = {"single": 28, "multi": 8, "version": 6, "unanswerable": 8}
    if counts != expected:
        return False, f"Category count mismatch ({count_summary})"
    return True, f"Category counts exact: {count_summary}"


def check_evidence_resolution(
    items: list[EvalItem],
    evidence_map: dict[tuple[str, str], list[str]],
) -> tuple[bool, str]:
    """Check that every evidence (doc_path, anchor) resolves to at least one chunk."""
    unresolved: list[str] = []

    for item in items:
        if item.category == "unanswerable":
            if item.evidence:
                unresolved.append(f"{item.id}: unanswerable must have empty evidence")
            continue

        for ev in item.evidence:
            key = (ev.doc_path, ev.anchor)
            if key not in evidence_map:
                unresolved.append(f"{item.id}: {ev.doc_path}#{ev.anchor} not found")

    if unresolved:
        return False, f"Unresolved evidence: {', '.join(unresolved[:5])}"
    return True, "All evidence references resolve to existing chunks"


def check_overlap(
    items: list[EvalItem],
    evidence_map: dict[tuple[str, str], list[str]],
) -> tuple[bool, str]:
    """Check that no question shares 4+ consecutive words with evidence chunks."""
    overlaps: list[str] = []

    for item in items:
        if not item.evidence:
            continue
        texts: list[str] = []
        for ev in item.evidence:
            key = (ev.doc_path, ev.anchor)
            texts.extend(evidence_map.get(key, []))

        ov = find_4gram_overlaps(item.question, texts)
        if ov:
            overlaps.append(f"{item.id} ('{ov[0]}')")

    if overlaps:
        return False, f"4-word overlap found in {len(overlaps)} items: {', '.join(overlaps[:5])}"
    return True, "No 4-word overlap found between questions and evidence chunks"


def check_page_spread(items: list[EvalItem]) -> tuple[bool, str]:
    """Check that evidence spans >=15 pages and <=5 items per page."""
    page_counts: dict[str, int] = {}

    for item in items:
        if not item.evidence:
            continue
        pages_in_item = {ev.doc_path for ev in item.evidence}
        for p in pages_in_item:
            page_counts[p] = page_counts.get(p, 0) + 1

    distinct_pages = len(page_counts)
    over_limit = [f"{p} ({cnt})" for p, cnt in page_counts.items() if cnt > 5]

    max_items = max(page_counts.values()) if page_counts else 0
    details = f"{distinct_pages} pages used; max items per page: {max_items}"
    if distinct_pages < 15:
        return False, f"Evidence used only {distinct_pages} pages (minimum 15 required). {details}"
    if over_limit:
        return False, f"Pages exceeding 5 items limit: {', '.join(over_limit)}. {details}"
    return True, f"Page spread rules satisfied ({details})"


def check_sources(items: list[EvalItem], min_sources: int = MIN_REAL_SOURCES) -> tuple[bool, str]:
    """Check that at least min_sources answerable items are adapted from real user sources."""
    answerable = [it for it in items if it.category != "unanswerable"]
    user_sourced = [it for it in answerable if it.source != "docs"]

    count = len(user_sourced)
    if count < min_sources:
        return (
            False,
            f"Only {count}/42 answerable items from user sources (minimum {min_sources} required)",
        )
    return True, f"{count}/42 answerable items adapted from real user sources"


def check_must_mention(
    items: list[EvalItem],
    evidence_map: dict[tuple[str, str], list[str]],
) -> tuple[bool, str]:
    """Check that must_mention identifiers appear verbatim in evidence chunks."""
    missing: list[str] = []

    for item in items:
        if item.category == "unanswerable":
            if item.must_mention:
                missing.append(f"{item.id}: unanswerable must have empty must_mention")
            continue

        if not (1 <= len(item.must_mention) <= 4):
            missing.append(f"{item.id}: must_mention count {len(item.must_mention)} not in [1, 4]")
            continue

        evidence_texts: list[str] = []
        for ev in item.evidence:
            evidence_texts.extend(evidence_map.get((ev.doc_path, ev.anchor), []))

        for ident in item.must_mention:
            if not any(ident in text for text in evidence_texts):
                missing.append(f"{item.id}: '{ident}' not found in evidence chunks")

    if missing:
        return False, f"must_mention verification failed: {', '.join(missing[:5])}"
    return True, "All must_mention identifiers verified verbatim in evidence chunks"


def check_unanswerable_absence(
    items: list[EvalItem],
    chunks: list[Chunk] | list[dict[str, Any]],
    absence_terms_map: dict[str, list[str]] | None = None,
    adjudications_map: dict[str, list[dict[str, Any]]] | None = None,
) -> tuple[bool, str]:
    """Check that unanswerable items have absence terms defined and zero uncleared hits."""
    if absence_terms_map is None:
        absence_terms_map = load_absence_terms(DEFAULT_TERMS_PATH)
    if adjudications_map is None:
        adjudications_map = load_absence_adjudications(DEFAULT_ADJUDICATIONS_PATH)

    res = check_all_unanswerable_absence(
        items=items,
        chunks=chunks,
        absence_terms_map=absence_terms_map,
        adjudications_map=adjudications_map,
    )
    if res.passed:
        return True, "All unanswerable items have zero uncleared keyword hits"
    return False, f"Absence check failed ({len(res.errors)} error(s)): {res.errors[0]}"


def check_verification_status(items: list[EvalItem], require_verified: bool) -> tuple[bool, str]:
    """Check verified count on items."""
    verified_count = sum(1 for it in items if it.verified)
    total = len(items)
    status_str = f"{verified_count}/{total} items marked verified"

    if require_verified and verified_count < total:
        return False, f"Verification required but only {status_str}"
    return True, status_str


def check_source_quotes_registered(
    items: list[EvalItem],
    quotes_path: Path | None = None,
    snapshots_dir: Path | None = None,
) -> tuple[bool, str]:
    """Check that non-'docs' sources have source_quotes.json entries and snapshots."""
    if quotes_path is None:
        quotes_path = DEFAULT_QUOTES_PATH
    if snapshots_dir is None:
        snapshots_dir = DEFAULT_SNAPSHOTS_DIR

    user_sourced = [it for it in items if it.source != "docs"]
    if not user_sourced:
        return True, "No external user sources to verify"

    if not quotes_path.exists():
        return False, f"source_quotes.json not found at {quotes_path}"

    try:
        with open(quotes_path, encoding="utf-8") as f:
            quotes_data = json.load(f)
    except Exception as exc:
        return False, f"Failed to parse source_quotes.json: {exc}"

    missing_quotes: list[str] = []
    missing_snapshots: list[str] = []

    for it in user_sourced:
        if it.id not in quotes_data:
            missing_quotes.append(it.id)
        snap_file = snapshots_dir / f"{it.id}.txt"
        if not snap_file.exists():
            missing_snapshots.append(it.id)

    errors: list[str] = []
    if missing_quotes:
        errors.append(f"missing quotes in source_quotes.json: {', '.join(missing_quotes)}")
    if missing_snapshots:
        errors.append(f"missing snapshot files: {', '.join(missing_snapshots)}")

    if errors:
        return False, f"Source quotes verification failed: {'; '.join(errors)}"

    return True, f"All {len(user_sourced)} external source(s) have registered quotes and snapshots"


def validate_eval_dataset(
    raw_lines: list[str],
    chunks: list[Chunk] | list[dict[str, Any]],
    require_verified: bool = False,
    absence_terms_map: dict[str, list[str]] | None = None,
    adjudications_map: dict[str, list[dict[str, Any]]] | None = None,
    quotes_path: Path | None = None,
    snapshots_dir: Path | None = None,
    min_real_sources: int = MIN_REAL_SOURCES,
) -> ValidationReport:
    """Run all validation checks against evaluation dataset."""
    checks: list[CheckResult] = []

    evidence_map, _ = load_chunks_lookup(chunks)

    # Check 1: Parse
    parse_ok, items, parse_details = check_parsing(raw_lines)
    checks.append(CheckResult("Parse as EvalItem", parse_ok, parse_details))
    if not parse_ok:
        return ValidationReport(passed=False, checks=checks)

    # Check 2: IDs
    ids_ok, ids_details = check_ids(items)
    checks.append(CheckResult("IDs unique and sequential", ids_ok, ids_details))

    # Check 3: Categories
    cat_ok, cat_details = check_category_counts(items)
    checks.append(CheckResult("Category composition", cat_ok, cat_details))

    # Check 4: Evidence resolution
    ev_ok, ev_details = check_evidence_resolution(items, evidence_map)
    checks.append(CheckResult("Evidence resolution", ev_ok, ev_details))

    # Check 5: Overlap
    ov_ok, ov_details = check_overlap(items, evidence_map)
    checks.append(CheckResult("No 4-word overlap", ov_ok, ov_details))

    # Check 6: Page spread
    spread_ok, spread_details = check_page_spread(items)
    checks.append(CheckResult("Page spread", spread_ok, spread_details))

    # Check 7: Sourcing
    src_ok, src_details = check_sources(items, min_sources=min_real_sources)
    checks.append(CheckResult("Real user question sourcing", src_ok, src_details))

    # Check 8: must_mention
    mm_ok, mm_details = check_must_mention(items, evidence_map)
    checks.append(CheckResult("Must-mention identifiers", mm_ok, mm_details))

    # Check 9: Verification status
    ver_ok, ver_details = check_verification_status(items, require_verified)
    checks.append(CheckResult("Verification status", ver_ok, ver_details))

    # Check 10: Unanswerable absence
    abs_ok, abs_details = check_unanswerable_absence(
        items=items,
        chunks=chunks,
        absence_terms_map=absence_terms_map,
        adjudications_map=adjudications_map,
    )
    checks.append(CheckResult("Unanswerable absence", abs_ok, abs_details))

    # Check 11: Source quotes verified
    sq_ok, sq_details = check_source_quotes_registered(
        items=items,
        quotes_path=quotes_path,
        snapshots_dir=snapshots_dir,
    )
    checks.append(CheckResult("Source quotes verified", sq_ok, sq_details))

    passed = all(c.passed for c in checks)
    return ValidationReport(passed=passed, checks=checks)
