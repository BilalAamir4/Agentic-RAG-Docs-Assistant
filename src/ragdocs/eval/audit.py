"""Mechanical audit logic for evaluation dataset items against documentation chunks."""

import re
from typing import Any

from pydantic import BaseModel, Field

from ragdocs.eval.validate import find_4gram_overlaps
from ragdocs.schemas import Chunk, EvalItem

CODE_TOKEN_RE = re.compile(
    r"(?:@[A-Za-z_][A-Za-z0-9_]*)"
    r"|(?:[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+)"
    r"|(?:[A-Za-z0-9_\-]+\.(?:json|py|mdx|toml))"
    r"|(?:[A-Z][A-Z0-9_]{1,})"
    r"|(?:[A-Za-z0-9]+_[A-Za-z0-9_]+)"
    r"|(?:[A-Z][a-z0-9]+(?:[A-Z][A-Za-z0-9]*)+)"
    r"|(?:[A-Z]{2,}[a-z0-9]+[A-Za-z0-9]*)"
)

IGNORED_TOKENS = {"e.g", "i.e", "e.g.", "i.e."}


class EvidencePairAudit(BaseModel):
    """Resolution details for an individual (doc_path, anchor) evidence reference."""

    doc_path: str
    anchor: str
    resolved: bool
    chunk_ids: list[str] = Field(default_factory=list)


class ItemAudit(BaseModel):
    """Audit report for an individual evaluation item."""

    item_id: str
    category: str
    question: str
    evidence_resolution: list[EvidencePairAudit] = Field(default_factory=list)
    resolved_chunk_ids: list[str] = Field(default_factory=list)
    must_mention_failures: list[str] = Field(default_factory=list)
    extracted_tokens: list[str] = Field(default_factory=list)
    grounding_failures: list[str] = Field(default_factory=list)
    overlaps_4gram: list[str] = Field(default_factory=list)
    is_noisy_evidence: bool = False
    version_proof_ok: bool = True
    version_proof_details: str = ""


class AuditSummary(BaseModel):
    """Global summary metrics for dataset audit."""

    total_items: int
    answerable_items: int
    unresolved_items: list[str] = Field(default_factory=list)
    must_mention_failed_items: list[str] = Field(default_factory=list)
    grounding_failed_items: list[str] = Field(default_factory=list)
    overlap_failed_items: list[str] = Field(default_factory=list)
    noisy_evidence_items: list[str] = Field(default_factory=list)
    version_proof_failed_items: list[str] = Field(default_factory=list)
    distinct_pages: int
    max_items_per_page: int
    page_counts: dict[str, int] = Field(default_factory=dict)


def extract_code_tokens(text: str) -> list[str]:
    """Extract code-like identifiers from text."""
    raw_matches = CODE_TOKEN_RE.findall(text)
    clean_set: set[str] = set()

    for m in raw_matches:
        cleaned = m.strip(".,;:()[]{}'\"")
        if cleaned in IGNORED_TOKENS:
            continue
        if len(cleaned) > 1:
            clean_set.add(cleaned)

    return sorted(clean_set)


def build_chunks_by_anchor(
    chunks: list[Chunk] | list[dict[str, Any]],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """Map (doc_path, anchor) to full chunk dicts."""
    mapping: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for c in chunks:
        data = c.model_dump() if isinstance(c, Chunk) else c
        key = (str(data["doc_path"]), str(data["anchor"]))
        mapping.setdefault(key, []).append(data)
    return mapping


def audit_answerable_item(
    item: EvalItem,
    chunks_by_anchor: dict[tuple[str, str], list[dict[str, Any]]],
) -> ItemAudit:
    """Run all audit checks on a single answerable item."""
    ev_audits: list[EvidencePairAudit] = []
    resolved_chunk_ids: list[str] = []
    evidence_texts: list[str] = []

    for ev in item.evidence:
        key = (ev.doc_path, ev.anchor)
        matched_chunks = chunks_by_anchor.get(key, [])
        c_ids = [str(c["chunk_id"]) for c in matched_chunks]
        ev_audits.append(
            EvidencePairAudit(
                doc_path=ev.doc_path,
                anchor=ev.anchor,
                resolved=len(matched_chunks) > 0,
                chunk_ids=c_ids,
            )
        )
        resolved_chunk_ids.extend(c_ids)
        evidence_texts.extend([str(c.get("text", "")) for c in matched_chunks])

    full_ev_text = " ".join(evidence_texts)

    # b) must_mention EVIDENCE-ONLY
    mm_failures = [
        ident for ident in item.must_mention if not any(ident in text for text in evidence_texts)
    ]

    # c) Reference answer grounding
    extracted_tokens = extract_code_tokens(item.reference_answer or "")
    grounding_failures: list[str] = []
    for token in extracted_tokens:
        raw_token = token.lstrip("@")
        if token not in full_ev_text and raw_token not in full_ev_text:
            grounding_failures.append(token)

    # d) 4-gram overlap (case-insensitive)
    overlaps = find_4gram_overlaps(item.question, evidence_texts)

    # e) Evidence noise (> 3 chunks)
    is_noisy = len(resolved_chunk_ids) > 3

    # g) Version proof check
    version_ok = True
    version_details = "N/A"
    if item.category == "version":
        has_proof = "proof:" in item.notes.lower()
        has_http = "http://" in item.notes.lower() or "https://" in item.notes.lower()
        has_version_docs = "requires langgraph" in item.notes.lower()
        if (has_proof or has_version_docs) and has_http:
            version_ok = True
            version_details = "Documented proof with external release/docs URL"
        else:
            version_ok = False
            version_details = "Missing required 'Proof:' or version URL in notes"

    return ItemAudit(
        item_id=item.id,
        category=item.category,
        question=item.question,
        evidence_resolution=ev_audits,
        resolved_chunk_ids=resolved_chunk_ids,
        must_mention_failures=mm_failures,
        extracted_tokens=extracted_tokens,
        grounding_failures=grounding_failures,
        overlaps_4gram=overlaps,
        is_noisy_evidence=is_noisy,
        version_proof_ok=version_ok,
        version_proof_details=version_details,
    )


def run_eval_audit(
    items: list[EvalItem],
    chunks: list[Chunk] | list[dict[str, Any]],
) -> tuple[list[ItemAudit], AuditSummary]:
    """Execute complete mechanical audit over the evaluation set."""
    chunks_by_anchor = build_chunks_by_anchor(chunks)
    item_audits: list[ItemAudit] = []

    answerable = [it for it in items if it.category != "unanswerable"]

    unresolved_items: list[str] = []
    mm_failed: list[str] = []
    grounding_failed: list[str] = []
    overlap_failed: list[str] = []
    noisy_items: list[str] = []
    version_failed: list[str] = []

    page_items: dict[str, set[str]] = {}

    for item in answerable:
        audit = audit_answerable_item(item, chunks_by_anchor)
        item_audits.append(audit)

        if any(not ev.resolved for ev in audit.evidence_resolution):
            unresolved_items.append(item.id)

        if audit.must_mention_failures:
            mm_failed.append(item.id)

        if audit.grounding_failures:
            grounding_failed.append(item.id)

        if audit.overlaps_4gram:
            overlap_failed.append(item.id)

        if audit.is_noisy_evidence:
            noisy_items.append(item.id)

        if not audit.version_proof_ok:
            version_failed.append(item.id)

        for ev in item.evidence:
            page_items.setdefault(ev.doc_path, set()).add(item.id)

    page_counts = {p: len(ids) for p, ids in page_items.items()}

    summary = AuditSummary(
        total_items=len(items),
        answerable_items=len(answerable),
        unresolved_items=unresolved_items,
        must_mention_failed_items=mm_failed,
        grounding_failed_items=grounding_failed,
        overlap_failed_items=overlap_failed,
        noisy_evidence_items=noisy_items,
        version_proof_failed_items=version_failed,
        distinct_pages=len(page_counts),
        max_items_per_page=max(page_counts.values()) if page_counts else 0,
        page_counts=page_counts,
    )

    return item_audits, summary


def generate_audit_markdown(
    item_audits: list[ItemAudit],
    summary: AuditSummary,
) -> str:
    """Format audit results as a detailed Markdown report for AUDIT.md."""
    lines: list[str] = [
        "# Mechanical Evaluation Audit Report",
        "",
        "## Summary Metrics",
        f"- Total Items Audited: {summary.total_items} (Answerable: {summary.answerable_items})",
        f"- Unresolved Evidence References: {len(summary.unresolved_items)}",
        f"- must_mention Failures (Evidence-Only): {len(summary.must_mention_failed_items)}",
        f"- Reference-Answer Grounding Flags: {len(summary.grounding_failed_items)}",
        f"- Case-Insensitive 4-Gram Overlap Violations: {len(summary.overlap_failed_items)}",
        (
            f"- Noisy Evidence Items (>3 chunks): {len(summary.noisy_evidence_items)} "
            f"({', '.join(summary.noisy_evidence_items) or 'none'})"
        ),
        f"- Version Items Proof Violations: {len(summary.version_proof_failed_items)}",
        (
            f"- Page Spread: {summary.distinct_pages} distinct pages "
            f"(Max items per page: {summary.max_items_per_page})"
        ),
        "",
        "## Page Spread Distribution",
        "| Document Path | Item Count |",
        "|---|---|",
    ]

    for p, c in sorted(summary.page_counts.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"| `{p}` | {c} |")

    lines.extend(
        [
            "",
            "## Per-Item Audit Findings (Answerable Items)",
            "",
        ]
    )

    for it in item_audits:
        lines.append(f"### {it.item_id} [{it.category.upper()}]")
        lines.append(f"**Question:** {it.question}")
        lines.append("")

        # Evidence resolution
        lines.append("**Evidence Resolution:**")
        for ev in it.evidence_resolution:
            status = "RESOLVED" if ev.resolved else "UNRESOLVED"
            lines.append(f"- `[{status}]` `{ev.doc_path}#{ev.anchor}` -> chunks: `{ev.chunk_ids}`")

        # must_mention
        lines.append("")
        if it.must_mention_failures:
            lines.append(
                f"**must_mention (Evidence-Only):** FAILED: Missing {it.must_mention_failures}"
            )
        else:
            lines.append(
                "**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)"
            )

        # Grounding
        lines.append("")
        if it.grounding_failures:
            lines.append(f"**Reference-Answer Grounding:** FLAGGED TOKENS: {it.grounding_failures}")
            lines.append(f"  - Extracted tokens: `{it.extracted_tokens}`")
        else:
            n_tokens = len(it.extracted_tokens)
            lines.append(f"**Reference-Answer Grounding:** CLEAN ({n_tokens} code tokens verified)")

        # Overlap
        lines.append("")
        if it.overlaps_4gram:
            lines.append(f"**4-Gram Overlap:** FAILED: `{it.overlaps_4gram}`")
        else:
            lines.append("**4-Gram Overlap:** PASSED (Zero shared 4-grams)")

        # Noise
        lines.append("")
        if it.is_noisy_evidence:
            n_chunks = len(it.resolved_chunk_ids)
            lines.append(f"**Evidence Noise:** HIGH ({n_chunks} chunks: `{it.resolved_chunk_ids}`)")
        else:
            lines.append(f"**Evidence Noise:** OK ({len(it.resolved_chunk_ids)} chunks)")

        # Version
        if it.category == "version":
            lines.append("")
            status = "PASSED" if it.version_proof_ok else "FAILED"
            lines.append(f"**Version Proof Status:** `[{status}]` {it.version_proof_details}")

        lines.append("")

    return "\n".join(lines)
