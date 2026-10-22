"""CLI to check unanswerable items for search term absence in chunks.jsonl.

Usage:
    .venv/Scripts/python scripts/check_unanswerable.py
"""

import argparse
import json
import sys
from pathlib import Path

from ragdocs.eval.absence import (
    check_all_unanswerable_absence,
    load_absence_adjudications,
    load_absence_terms,
)
from ragdocs.io_utils import read_jsonl
from ragdocs.schemas import EvalItem

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVAL_PATH = REPO_ROOT / "data" / "eval" / "eval_set.jsonl"
DEFAULT_CHUNKS_PATH = REPO_ROOT / "data" / "processed" / "chunks.jsonl"
DEFAULT_TERMS_PATH = REPO_ROOT / "data" / "eval" / "absence_terms.json"
DEFAULT_ADJUDICATION_PATH = REPO_ROOT / "data" / "eval" / "absence_adjudication.json"


def format_absence_report(
    items: list[EvalItem],
    result,
) -> str:
    """Format human-readable CLI report of keyword absence and adjudication."""
    lines: list[str] = ["=== Unanswerable Absence Verification Report ==="]
    unanswerable_items = [it for it in items if it.category == "unanswerable"]

    for item in unanswerable_items:
        lines.append(f"\nItem: {item.id} - {item.question}")
        hits_map = result.item_hits.get(item.id, {})
        if not hits_map and item.id in result.errors:
            lines.append("  [ERROR] Missing search terms or check failure")
            continue

        for term, term_hits in hits_map.items():
            count = len(term_hits)
            uncleared = [h for h in term_hits if not h.cleared]
            if count == 0:
                lines.append(f"  Term '{term}': 0 hits [CLEAN]")
            elif not uncleared:
                lines.append(f"  Term '{term}': {count} hit(s) [ALL CLEARED AS IRRELEVANT]")
                for h in term_hits:
                    lines.append(f"    - {h.chunk_id} ({h.doc_path}#{h.anchor}) [CLEARED]")
                    lines.append(f"      Reason: {h.reason}")
            else:
                lines.append(f"  Term '{term}': {count} hit(s) [{len(uncleared)} UNCLEARED]")
                for h in term_hits:
                    status = "[CLEARED]" if h.cleared else "[UNCLEARED]"
                    lines.append(f"    - {status} {h.chunk_id} ({h.doc_path}#{h.anchor})")
                    if h.cleared:
                        lines.append(f"      Reason: {h.reason}")
                    else:
                        lines.append(f"      Snippet: {h.snippet}")

    lines.append("\n" + "=" * 49)
    if result.passed:
        lines.append("Overall Result: PASSED (All unanswerable terms have zero uncleared hits)")
    else:
        lines.append(f"Overall Result: FAILED ({len(result.errors)} uncleared hit(s) or error(s))")
        for err in result.errors:
            lines.append(f"  * {err}")

    return "\n".join(lines)


def run_absence_check(
    eval_path: Path,
    chunks_path: Path,
    terms_path: Path,
    adjudication_path: Path,
) -> int:
    """Run absence check pipeline and print output."""
    if not eval_path.exists():
        print(f"Error: eval file not found at {eval_path}", file=sys.stderr)
        return 1

    if not chunks_path.exists():
        print(f"Error: chunks file not found at {chunks_path}", file=sys.stderr)
        return 1

    items: list[EvalItem] = []
    with open(eval_path, encoding="utf-8-sig") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                items.append(EvalItem.model_validate(json.loads(stripped)))

    chunks = read_jsonl(chunks_path)
    terms_map = load_absence_terms(terms_path)
    adjudications_map = load_absence_adjudications(adjudication_path)

    result = check_all_unanswerable_absence(
        items=items,
        chunks=chunks,
        absence_terms_map=terms_map,
        adjudications_map=adjudications_map,
    )

    print(format_absence_report(items, result))
    return 0 if result.passed else 1


def main() -> int:
    """Parse CLI arguments and run check."""
    parser = argparse.ArgumentParser(description="Check unanswerable item absence.")
    parser.add_argument("--eval-path", default=str(DEFAULT_EVAL_PATH))
    parser.add_argument("--chunks-path", default=str(DEFAULT_CHUNKS_PATH))
    parser.add_argument("--absence-terms-path", default=str(DEFAULT_TERMS_PATH))
    parser.add_argument("--adjudication-path", default=str(DEFAULT_ADJUDICATION_PATH))

    args = parser.parse_args()
    return run_absence_check(
        eval_path=Path(args.eval_path),
        chunks_path=Path(args.chunks_path),
        terms_path=Path(args.absence_terms_path),
        adjudication_path=Path(args.adjudication_path),
    )


if __name__ == "__main__":
    sys.exit(main())
