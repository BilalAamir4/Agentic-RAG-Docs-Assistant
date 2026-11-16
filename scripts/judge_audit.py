"""Write or score the 10-item hand audit of the judge (M08, D9).

Usage:
    py tasks.py judge-audit --run-dir DIR [--score] [--force]

Inputs: the run folder (effective verdicts from the highest judge_v<N>.jsonl).
Outputs: results/judge_audit.md (10 judged items, seed Settings.eval_audit_seed,
strata Settings.eval_audit_strata, empty human columns). Never overwrites filled human
labels unless --force. --score prints correctness and citation_support agreement as
count/10 and lists disagreements.
"""

import argparse
import sys
from pathlib import Path

from ragdocs.config import get_settings
from ragdocs.eval.judge_audit import score_audit, write_audit


def main() -> int:
    """Parse arguments and write or score the audit."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-dir", type=Path, required=True, help="Run folder")
    parser.add_argument("--score", action="store_true", help="Score filled human columns")
    parser.add_argument("--force", action="store_true", help="Overwrite filled labels")
    args = parser.parse_args()
    settings = get_settings()
    audit_path = settings.results_dir / "judge_audit.md"
    if not args.score:
        ids = write_audit(
            args.run_dir,
            audit_path,
            settings.eval_audit_seed,
            settings.eval_audit_strata,
            force=args.force,
        )
        print(f"Wrote {audit_path.as_posix()} with items: {', '.join(ids)}")
        return 0
    result = score_audit(args.run_dir, audit_path)
    if result.unlabelled:
        print(f"Unlabelled items: {', '.join(result.unlabelled)}", file=sys.stderr)
        return 1
    print(f"correctness agreement: {result.correctness_agree}/{result.n}")
    print(f"citation_support agreement: {result.citation_agree}/{result.n}")
    for line in result.disagreements:
        print(f"  disagreement {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
