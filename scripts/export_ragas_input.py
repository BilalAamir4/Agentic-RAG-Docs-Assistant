"""Write <run>/ragas_input.jsonl, the handoff file for the isolated RAGAS scorer (M09, D19).

Usage:
    .venv\\Scripts\\python scripts\\export_ragas_input.py --run-dir DIR

Inputs: <run>/per_question.jsonl. Output: <run>/ragas_input.jsonl (written when
missing; an identical existing file is kept; a different one is refused).
"""

import argparse
import sys
from pathlib import Path

from ragdocs.eval.ragas_export import RAGAS_METRICS, export_ragas_input


def main() -> int:
    """Export the handoff file and print eligibility counts."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    path, rows = export_ragas_input(args.run_dir)
    counts = ", ".join(f"{m} {sum(r['eligible'][m] for r in rows)}" for m in RAGAS_METRICS)
    print(f"{path.as_posix()}: {len(rows)} rows; eligible: {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
