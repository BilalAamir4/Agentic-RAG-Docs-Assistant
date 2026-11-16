"""CLI script to build dense and sparse retrieval indexes."""

import argparse
import sys
import time
from pathlib import Path

from ragdocs.eval.budget_recorder import install_budget_recorder
from ragdocs.index.build import build_index


def main() -> int:
    """Run index build CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--chunks-path",
        type=Path,
        default=None,
        help="Path to input chunks.jsonl file",
    )
    parser.add_argument(
        "--index-dir",
        type=Path,
        default=None,
        help="Target directory for generated index files",
    )
    args = parser.parse_args()

    install_budget_recorder()
    start_time = time.perf_counter()
    print("Building retrieval indexes...")
    result = build_index(
        chunks_path=args.chunks_path,
        index_dir=args.index_dir,
        show_progress=True,
    )
    elapsed = time.perf_counter() - start_time

    print("\n=== Index Build Report ===")
    print(f"Chunks indexed: {result['n_chunks']}")
    print(f"API calls made: {result['api_calls']}")
    print(f"Wall time: {elapsed:.2f} s")
    print("Generated files:")
    for name, sha in result["files"].items():
        file_path = result["manifest_path"].parent / name
        size_kb = file_path.stat().st_size / 1024
        print(f"  - {name} ({size_kb:.1f} KB): sha256={sha}")
    print(f"Manifest written to: {result['manifest_path']}")
    print("==========================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
