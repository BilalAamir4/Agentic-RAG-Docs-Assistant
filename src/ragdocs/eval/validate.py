"""Validation logic for the evaluation dataset."""

import json
import string
from dataclasses import dataclass
from typing import Any

from ragdocs.schemas import Chunk, EvalItem


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
    """Check that categories match exact counts and ordering."""
    expected_order = ["single"] * 28 + ["multi"] * 8 + ["version"] * 6 + ["unanswerable"] * 8
    actual_order = [item.category for item in items]

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

    if actual_order != expected_order:
        return False, f"Category count/order mismatch ({count_summary})"
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


def check_sources(items: list[EvalItem]) -> tuple[bool, str]:
    """Check that at least 20 answerable items are adapted from real user sources."""
    answerable = [it for it in items if it.category != "unanswerable"]
    user_sourced = [it for it in answerable if it.source != "docs"]

    count = len(user_sourced)
    if count < 20:
        return False, f"Only {count}/42 answerable items from user sources (minimum 20 required)"
    return True, f"{count}/42 answerable items adapted from real user sources"


def check_must_mention(
    items: list[EvalItem],
    evidence_map: dict[tuple[str, str], list[str]],
    all_texts: set[str],
) -> tuple[bool, str]:
    """Check that must_mention identifiers appear verbatim in evidence or corpus."""
    missing: list[str] = []

    for item in items:
        if item.category == "unanswerable":
            if item.must_mention:
                missing.append(f"{item.id}: unanswerable must have empty must_mention")
            continue

        if not (1 <= len(item.must_mention) <= 4):
            missing.append(f"{item.id}: must_mention count {len(item.must_mention)} not in [1, 4]")
            continue

        if item.category == "version":
            for ident in item.must_mention:
                if not any(ident in text for text in all_texts):
                    missing.append(f"{item.id}: '{ident}' not found in corpus")
        else:
            evidence_texts: list[str] = []
            for ev in item.evidence:
                evidence_texts.extend(evidence_map.get((ev.doc_path, ev.anchor), []))
            for ident in item.must_mention:
                if not any(ident in text for text in evidence_texts):
                    missing.append(f"{item.id}: '{ident}' not found in evidence chunks")

    if missing:
        return False, f"must_mention verification failed: {', '.join(missing[:5])}"
    return True, "All must_mention identifiers verified verbatim in evidence/corpus"


def check_verification_status(items: list[EvalItem], require_verified: bool) -> tuple[bool, str]:
    """Check verified count on items."""
    verified_count = sum(1 for it in items if it.verified)
    total = len(items)
    status_str = f"{verified_count}/{total} items marked verified"

    if require_verified and verified_count < total:
        return False, f"Verification required but only {status_str}"
    return True, status_str


def validate_eval_dataset(
    raw_lines: list[str],
    chunks: list[Chunk] | list[dict[str, Any]],
    require_verified: bool = False,
) -> ValidationReport:
    """Run all validation checks against evaluation dataset."""
    checks: list[CheckResult] = []

    evidence_map, all_texts = load_chunks_lookup(chunks)

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
    src_ok, src_details = check_sources(items)
    checks.append(CheckResult("Real user question sourcing", src_ok, src_details))

    # Check 8: must_mention
    mm_ok, mm_details = check_must_mention(items, evidence_map, all_texts)
    checks.append(CheckResult("Must-mention identifiers", mm_ok, mm_details))

    # Check 9: Verified count
    ver_ok, ver_details = check_verification_status(items, require_verified)
    checks.append(CheckResult("Verification status", ver_ok, ver_details))

    passed = all(c.passed for c in checks)
    return ValidationReport(passed=passed, checks=checks)
