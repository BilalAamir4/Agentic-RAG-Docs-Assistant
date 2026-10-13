"""CLI script to generate data/eval/REVIEW.md from eval_set.jsonl and chunks.jsonl.

Usage:
    .venv/Scripts/python scripts/make_review_sheet.py
"""

import argparse
import json
import sys
from pathlib import Path

from ragdocs.eval.review import generate_review_markdown
from ragdocs.io_utils import read_jsonl, write_text
from ragdocs.schemas import EvalItem

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVAL_PATH = REPO_ROOT / "data" / "eval" / "eval_set.jsonl"
DEFAULT_CHUNKS_PATH = REPO_ROOT / "data" / "processed" / "chunks.jsonl"
DEFAULT_OUT_PATH = REPO_ROOT / "data" / "eval" / "REVIEW.md"


def make_review_sheet(
    eval_path: Path,
    chunks_path: Path,
    out_path: Path,
) -> int:
    """Generate review markdown and save to out_path."""
    if not eval_path.exists():
        print(f"Error: eval file not found at {eval_path}", file=sys.stderr)
        return 1

    if not chunks_path.exists():
        print(f"Error: chunks file not found at {chunks_path}", file=sys.stderr)
        return 1

    with open(eval_path, encoding="utf-8-sig") as f:
        items = [EvalItem.model_validate(json.loads(line)) for line in f if line.strip()]

    chunks = read_jsonl(chunks_path)
    md_content = generate_review_markdown(items, chunks)
    write_text(out_path, md_content)
    print(f"Successfully generated review sheet with {len(items)} items at {out_path}")
    return 0


def main() -> int:
    """Parse arguments and generate review sheet."""
    parser = argparse.ArgumentParser(
        description="Generate human review sheet for evaluation dataset."
    )
    parser.add_argument(
        "--eval-path", default=str(DEFAULT_EVAL_PATH), help="Path to eval_set.jsonl"
    )
    parser.add_argument(
        "--chunks-path", default=str(DEFAULT_CHUNKS_PATH), help="Path to chunks.jsonl"
    )
    parser.add_argument(
        "--out-path", default=str(DEFAULT_OUT_PATH), help="Output path for REVIEW.md"
    )

    args = parser.parse_args()
    return make_review_sheet(
        eval_path=Path(args.eval_path),
        chunks_path=Path(args.chunks_path),
        out_path=Path(args.out_path),
    )


if __name__ == "__main__":
    sys.exit(main())
