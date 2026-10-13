"""Generate human review sheet for the evaluation dataset."""

from typing import Any

from ragdocs.schemas import Chunk, EvalItem


def generate_review_markdown(
    items: list[EvalItem],
    chunks: list[Chunk] | list[dict[str, Any]],
) -> str:
    """Generate Markdown review document for evaluation items."""
    # Build chunk lookup by (doc_path, anchor)
    chunk_map: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for c in chunks:
        doc_path = c.doc_path if isinstance(c, Chunk) else c["doc_path"]
        anchor = c.anchor if isinstance(c, Chunk) else c["anchor"]
        chunk_dict = c.model_dump() if isinstance(c, Chunk) else c
        chunk_map.setdefault((doc_path, anchor), []).append(chunk_dict)

    lines: list[str] = [
        "# Evaluation Dataset Human Review Sheet",
        "",
        "Instructions for reviewer:",
        "1. Check that each answer is factual, concise, and supported by documentation.",
        "2. Check that question does not copy phrasing from evidence chunks.",
        "3. For version questions, check that modern and outdated patterns are accurate.",
        "4. For unanswerable questions, verify that keyword searches confirm absence.",
        "5. Once reviewed and corrected, mark `[x] verified` and record any notes.",
        "",
        "---",
        "",
    ]

    for item in items:
        lines.append(f"## [{item.id}] {item.question}")
        lines.append("")
        lines.append(f"- **Category:** `{item.category}`")
        lines.append(f"- **Source:** {item.source}")
        if item.must_mention:
            must_str = ", ".join(f"`{m}`" for m in item.must_mention)
            lines.append(f"- **Must mention:** {must_str}")
        else:
            lines.append("- **Must mention:** *(None)*")

        if item.reference_answer:
            lines.append(f"- **Reference Answer:** {item.reference_answer}")
        else:
            lines.append("- **Reference Answer:** *(None - Unanswerable)*")

        if item.category == "unanswerable":
            lines.append("")
            lines.append("### Unanswerability Evidence (Keyword Searches)")
            lines.append(item.notes if item.notes else "*(No searches recorded)*")
            lines.append("")
        else:
            if item.notes:
                lines.append(f"- **Notes:** {item.notes}")
            lines.append("")
            lines.append("### Evidence Chunks")
            lines.append("")
            for ev in item.evidence:
                ev_chunks = chunk_map.get((ev.doc_path, ev.anchor), [])
                if not ev_chunks:
                    lines.append(f"*(Missing chunk for `{ev.doc_path}#{ev.anchor}`)*\n")
                    continue
                for c in ev_chunks:
                    lines.append(f"#### Chunk `{c['chunk_id']}` ({c.get('url', '')})")
                    lines.append(f"**Doc Path:** `{c['doc_path']}` | **Anchor:** `{c['anchor']}`")
                    lines.append("")
                    lines.append("```text")
                    lines.append(c["text"])
                    lines.append("```")
                    lines.append("")

        lines.append("[ ] verified")
        lines.append("Reviewer note:")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)
