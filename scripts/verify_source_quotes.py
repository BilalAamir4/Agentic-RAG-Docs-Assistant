"""CLI script to verify source quotes verbatim against live page snapshots.

Usage:
    .venv/Scripts/python scripts/verify_source_quotes.py
"""

import json
import sys
from pathlib import Path

from ragdocs.eval.verify_sources import verify_all_source_quotes
from ragdocs.schemas import EvalItem

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVAL_PATH = REPO_ROOT / "data" / "eval" / "eval_set.jsonl"
DEFAULT_QUOTES_PATH = REPO_ROOT / "data" / "eval" / "source_quotes.json"
DEFAULT_SNAPSHOTS_DIR = REPO_ROOT / "data" / "eval" / "source_snapshots"


def main() -> int:
    """Run source quotes verification and report results."""
    if not DEFAULT_EVAL_PATH.exists():
        print(f"Error: eval file not found at {DEFAULT_EVAL_PATH}", file=sys.stderr)
        return 1

    items: list[EvalItem] = []
    with open(DEFAULT_EVAL_PATH, encoding="utf-8-sig") as f:
        for line in f:
            line_str = line.strip()
            if line_str:
                items.append(EvalItem.model_validate(json.loads(line_str)))

    all_passed, results = verify_all_source_quotes(
        items=items,
        quotes_path=DEFAULT_QUOTES_PATH,
        snapshots_dir=DEFAULT_SNAPSHOTS_DIR,
    )

    non_docs_count = sum(1 for it in items if it.source != "docs")
    print("=== Source Quote Verification Report ===")
    print(f"Found {non_docs_count} item(s) with external user sources.")

    for res in results:
        if res.passed:
            print(f"[PASS] {res.item_id}: source quote verified verbatim")
        else:
            print(f"[FAIL] {res.item_id}:")
            for err in res.errors:
                print(f"  - {err}")

    print("=" * 40)
    if all_passed:
        print("Overall Result: PASSED (all source quotes match snapshots verbatim)")
        return 0
    else:
        print("Overall Result: FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
