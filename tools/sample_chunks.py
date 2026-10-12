"""Sample and display random chunks from a chunks.jsonl file.

Purpose:
    Inspect sampled documentation chunks deterministically using a random seed.

Inputs:
    --chunks-path: Path to the chunks.jsonl file (default: data/processed/chunks.jsonl)
    --seed: Integer random seed for reproducible sampling (default: 7)
    -n: Number of chunks to sample (default: 5)

Outputs:
    Prints sampled chunk title, heading_path, url, n_tokens, and the first 400 characters
    of text to standard output.
"""

import argparse
import json
import random
import sys
from pathlib import Path


def main() -> int:
    """Parse arguments and sample chunks."""
    parser = argparse.ArgumentParser(description="Sample documentation chunks.")
    parser.add_argument(
        "--chunks-path",
        default="data/processed/chunks.jsonl",
        help="Path to chunks.jsonl file",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=7,
        help="Random seed for sampling",
    )
    parser.add_argument(
        "-n",
        type=int,
        default=5,
        help="Number of chunks to sample",
    )

    args = parser.parse_args()

    chunks_file = Path(args.chunks_path)
    if not chunks_file.is_file():
        print(f"Error: chunks file not found at {chunks_file}", file=sys.stderr)
        return 1

    chunks: list[dict] = []
    with open(chunks_file, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                chunks.append(json.loads(stripped))

    if not chunks:
        print("Error: chunks file is empty", file=sys.stderr)
        return 1

    rng = random.Random(args.seed)
    sample_size = min(args.n, len(chunks))
    sampled = rng.sample(chunks, sample_size)

    for i, c in enumerate(sampled, 1):
        print(f"=== Sample {i}/{sample_size} ===")
        print(f"Title:        {c.get('title')}")
        print(f"Heading path: {c.get('heading_path')}")
        print(f"URL:          {c.get('url')}")
        print(f"Tokens:       {c.get('n_tokens')}")
        first_400 = (c.get("text") or "")[:400]
        print(f"Text (first 400 chars):\n{first_400}")
        print("-" * 50)

    return 0


if __name__ == "__main__":
    sys.exit(main())
