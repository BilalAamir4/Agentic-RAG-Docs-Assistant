"""CLI script to run the documentation ingestion pipeline.

Usage:
    .venv/Scripts/python scripts/ingest.py [--repo-url URL] [--commit SHA]
"""

import argparse
import datetime
import json
import sys
from pathlib import Path

import numpy as np

from ragdocs.ingest.chunk import chunk_document
from ragdocs.ingest.fetch import fetch_repo
from ragdocs.ingest.parse import list_in_scope_files, parse_file
from ragdocs.io_utils import write_jsonl, write_text
from ragdocs.schemas import Chunk

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_REPO_URL = "https://github.com/langchain-ai/docs"
DEFAULT_COMMIT = "a6e223d2f67558caa20589a03443e918b582943b"
DEFAULT_DOCS_ROOT = "src/oss/langgraph"
DEFAULT_BASE_URL = "https://docs.langchain.com/oss/python/langgraph"


def run_ingest(
    repo_url: str,
    commit: str,
    docs_root: str,
    out_dir: Path,
    base_url: str = DEFAULT_BASE_URL,
) -> None:
    """Run full ingestion pipeline and output chunks.jsonl, source.json, and stats.md."""
    raw_dir = REPO_ROOT / "data" / "raw" / "docs-repo"
    print(f"Fetching {repo_url} at commit {commit}...")
    repo_path = fetch_repo(repo_url, commit, raw_dir)

    full_docs_root = repo_path / docs_root
    if not full_docs_root.exists():
        raise FileNotFoundError(f"Docs root directory not found: {full_docs_root}")

    print(f"Discovering files in {full_docs_root}...")
    files = list_in_scope_files(full_docs_root)
    print(f"Found {len(files)} in-scope documentation files.")

    all_chunks: list[Chunk] = []
    for f in sorted(files, key=lambda p: p.as_posix()):
        parsed_doc = parse_file(f, full_docs_root, base_url)
        doc_chunks = chunk_document(parsed_doc, source_commit=commit)
        all_chunks.extend(doc_chunks)

    # Sort chunks by (doc_path, position in page)
    # They are already emitted in document order, but we ensure stable sorting
    out_dir_path = Path(out_dir).resolve()
    out_dir_path.mkdir(parents=True, exist_ok=True)

    # Write chunks.jsonl
    chunks_path = out_dir_path / "chunks.jsonl"
    chunk_dicts = [chunk.model_dump() for chunk in all_chunks]
    write_jsonl(chunks_path, chunk_dicts)
    print(f"Wrote {len(all_chunks)} chunks to {chunks_path}")

    # Write source.json
    today_iso = datetime.date.today().isoformat()
    source_metadata = {
        "repo_url": repo_url,
        "commit": commit,
        "docs_root": docs_root,
        "base_url": base_url,
        "fetched_at": today_iso,
        "n_pages": len(files),
        "n_chunks": len(all_chunks),
    }
    source_path = out_dir_path / "source.json"
    write_text(source_path, json.dumps(source_metadata, indent=2) + "\n")
    print(f"Wrote metadata to {source_path}")

    # Compute statistics for stats.md
    tokens = [c.n_tokens for c in all_chunks]
    p10 = float(np.percentile(tokens, 10))
    p50 = float(np.percentile(tokens, 50))
    p90 = float(np.percentile(tokens, 90))
    max_tokens = max(tokens) if tokens else 0
    chunks_with_code = [c for c in all_chunks if c.has_code]
    chunks_over_450 = [c for c in all_chunks if c.n_tokens > 450]

    stats_lines = [
        "# Corpus Statistics",
        "",
        f"- **Page count**: {len(files)}",
        f"- **Chunk count**: {len(all_chunks)}",
        f"- **Chunks with code**: {len(chunks_with_code)}",
        "",
        "## Token Percentiles (Approximate)",
        "",
        f"- **p10**: {p10:.1f}",
        f"- **p50**: {p50:.1f}",
        f"- **p90**: {p90:.1f}",
        f"- **max**: {max_tokens}",
        "",
        f"## Chunks Over 450 Tokens ({len(chunks_over_450)} total)",
        "",
        "| Chunk ID | Tokens | Code | Doc Path | Anchor |",
        "|---|---|---|---|---|",
    ]
    for c in chunks_over_450:
        stats_lines.append(
            f"| `{c.chunk_id}` | {c.n_tokens} | {c.has_code} | `{c.doc_path}` | `{c.anchor}` |"
        )
    stats_lines.append("")

    stats_path = out_dir_path / "stats.md"
    write_text(stats_path, "\n".join(stats_lines))
    print(f"Wrote corpus statistics to {stats_path}")


def main() -> int:
    """Parse CLI arguments and run ingestion."""
    parser = argparse.ArgumentParser(description="Ingest LangGraph documentation.")
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL, help="Git repository URL")
    parser.add_argument("--commit", default=DEFAULT_COMMIT, help="Pinned commit SHA")
    parser.add_argument(
        "--docs-root",
        default=DEFAULT_DOCS_ROOT,
        help="Documentation root inside repo",
    )
    parser.add_argument(
        "--out-dir",
        default=str(REPO_ROOT / "data" / "processed"),
        help="Output directory for processed files",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Public base URL for docs")

    args = parser.parse_args()
    run_ingest(
        repo_url=args.repo_url,
        commit=args.commit,
        docs_root=args.docs_root,
        out_dir=Path(args.out_dir),
        base_url=args.base_url,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
