"""CLI to audit evaluation dataset against chunks and output AUDIT.md.

Usage:
    .venv/Scripts/python scripts/audit_eval.py [--eval-path ...]
"""

import argparse
import json
import sys
from pathlib import Path

from ragdocs.eval.audit import generate_audit_markdown, run_eval_audit
from ragdocs.io_utils import read_jsonl
from ragdocs.schemas import EvalItem

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVAL_PATH = REPO_ROOT / "data" / "eval" / "eval_set.jsonl"
DEFAULT_CHUNKS_PATH = REPO_ROOT / "data" / "processed" / "chunks.jsonl"
DEFAULT_AUDIT_OUT = REPO_ROOT / "data" / "eval" / "AUDIT.md"


def run_audit_cli(
    eval_path: Path,
    chunks_path: Path,
    out_path: Path,
) -> int:
    """Execute audit and write AUDIT.md report."""
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

    item_audits, summary = run_eval_audit(items, chunks)
    report_md = generate_audit_markdown(item_audits, summary)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, mode="w", encoding="utf-8", newline="\n") as f:
        f.write(report_md)

    print(f"Audit completed: written to {out_path}")
    print(
        f"Summary: {summary.answerable_items} answerable items | "
        f"Unresolved evidence: {len(summary.unresolved_items)} | "
        f"must_mention failures: {len(summary.must_mention_failed_items)} | "
        f"Grounding flags: {len(summary.grounding_failed_items)} | "
        f"4-gram overlaps: {len(summary.overlap_failed_items)} | "
        f"Noisy evidence: {len(summary.noisy_evidence_items)} | "
        f"Version proof failures: {len(summary.version_proof_failed_items)}"
    )

    # Return nonzero if any hard failure exists
    # (unresolved evidence, must_mention, overlap, version)
    hard_failures = (
        len(summary.unresolved_items)
        + len(summary.must_mention_failed_items)
        + len(summary.overlap_failed_items)
        + len(summary.version_proof_failed_items)
    )
    return 1 if hard_failures > 0 else 0


def main() -> int:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Audit evaluation dataset.")
    parser.add_argument("--eval-path", default=str(DEFAULT_EVAL_PATH))
    parser.add_argument("--chunks-path", default=str(DEFAULT_CHUNKS_PATH))
    parser.add_argument("--out-path", default=str(DEFAULT_AUDIT_OUT))

    args = parser.parse_args()
    return run_audit_cli(
        eval_path=Path(args.eval_path),
        chunks_path=Path(args.chunks_path),
        out_path=Path(args.out_path),
    )


if __name__ == "__main__":
    sys.exit(main())
