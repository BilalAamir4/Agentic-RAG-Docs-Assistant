"""Standalone retrieval sanity check over built index files.

Purpose:
  Verify that dense (vector) and sparse (BM25) indexes provide high retrieval accuracy
  on a deterministic sample of 100 documentation chunks.

Inputs:
  - data/index/bm25.json
  - data/index/chunk_meta.jsonl
  - data/index/vectors.f16.npy
  - GOOGLE_API_KEY from environment or .env file

Outputs:
  - Prints BM25 top-1 retrieval share (expected > 0.85)
  - Prints dense vector top-10 retrieval share (expected > 0.60)
  - Reports sample statistics and any failure cases
"""

import json
import os
import random
import sys
import time
from collections import Counter
from pathlib import Path

import httpx
import numpy as np
from rank_bm25 import BM25Okapi

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_google_api_key() -> str:
    """Read GOOGLE_API_KEY from environment or .env file using plain string handling."""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if api_key:
        return api_key

    env_path = REPO_ROOT / ".env"
    if env_path.is_file():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("GOOGLE_API_KEY="):
                    val = stripped.split("=", 1)[1].strip()
                    if val.startswith(('"', "'")) and val.endswith(('"', "'")):
                        val = val[1:-1]
                    if val:
                        return val

    raise RuntimeError("GOOGLE_API_KEY not found in environment or .env file")


def run_sanity_checks() -> int:
    """Execute sparse and dense retrieval sanity checks over 100 sampled chunks."""
    index_dir = REPO_ROOT / "data" / "index"
    bm25_path = index_dir / "bm25.json"
    meta_path = index_dir / "chunk_meta.jsonl"
    vectors_path = index_dir / "vectors.f16.npy"

    if not (bm25_path.is_file() and meta_path.is_file() and vectors_path.is_file()):
        print(f"Error: Missing index files in {index_dir}", file=sys.stderr)
        return 1

    # Load BM25 tokens
    with open(bm25_path, encoding="utf-8") as f:
        bm25_data = json.load(f)
    all_tokens: list[list[str]] = bm25_data["tokens"]

    # Load chunk metadata
    chunks: list[dict] = []
    with open(meta_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                chunks.append(json.loads(line))

    # Load vectors as float32
    vectors = np.load(vectors_path).astype(np.float32)

    n_chunks = len(chunks)
    assert len(all_tokens) == n_chunks == len(vectors), "Row counts mismatch across index files"

    # Sample 100 chunks with seed 13
    rng = random.Random(13)
    sample_indices = rng.sample(range(n_chunks), 100)

    print("=== Running Index Retrieval Sanity Checks ===")
    print(f"Corpus size: {n_chunks} chunks | Sampled: 100 chunks (seed=13)\n")

    # 1. BM25 Sanity Check
    print("1. BM25 Sparse Check (Query: 5 rarest tokens by document frequency)...")
    doc_freq = Counter()
    for doc in all_tokens:
        for t in set(doc):
            doc_freq[t] += 1

    bm25 = BM25Okapi(all_tokens)
    bm25_top1_count = 0
    bm25_failures = []

    for idx in sample_indices:
        doc_toks = list(dict.fromkeys(all_tokens[idx]))
        if not doc_toks:
            continue
        rarest_5 = sorted(doc_toks, key=lambda t: (doc_freq[t], t))[:5]
        scores = bm25.get_scores(rarest_5)
        top_idx = int(np.argmax(scores))
        if top_idx == idx:
            bm25_top1_count += 1
        else:
            bm25_failures.append((idx, rarest_5, top_idx))

    bm25_share = bm25_top1_count / 100.0
    print(f"   BM25 Top-1 share: {bm25_share:.2f} ({bm25_top1_count}/100)")
    if bm25_share < 0.85:
        print(f"   WARNING: BM25 top-1 share below 0.85. First failures: {bm25_failures[:5]}")

    # 2. Dense Sanity Check
    print("\n2. Dense Vector Check (Query: title + heading_path)...")
    api_key = get_google_api_key()
    queries = []
    for idx in sample_indices:
        c = chunks[idx]
        q_text = (c["title"] + " " + " ".join(c["heading_path"])).strip()
        queries.append(q_text)

    # Batch embed queries via REST API with httpx
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-embedding-001:batchEmbedContents?key={api_key}"
    )

    query_vectors_cache = REPO_ROOT / "cache" / "sanity_query_vectors.npy"
    query_vectors: list[np.ndarray] = []

    if query_vectors_cache.is_file():
        print("   Using cached query vectors from cache/sanity_query_vectors.npy")
        query_vectors = [v for v in np.load(query_vectors_cache)]
    else:
        batch_size = 50
        for i in range(0, len(queries), batch_size):
            batch = queries[i : i + batch_size]
            payload = {
                "requests": [
                    {
                        "model": "models/gemini-embedding-001",
                        "content": {"parts": [{"text": q}]},
                        "taskType": "RETRIEVAL_QUERY",
                        "outputDimensionality": 768,
                    }
                    for q in batch
                ]
            }
            resp_success = False
            last_resp = None
            for _attempt in range(6):
                resp = httpx.post(url, json=payload, timeout=60.0)
                last_resp = resp
                if resp.status_code == 200:
                    resp_success = True
                    break
                if resp.status_code == 429:
                    time.sleep(20)
                else:
                    raise RuntimeError(f"Embedding API error {resp.status_code}: {resp.text}")

            if not resp_success:
                raise RuntimeError(
                    f"Embedding API call failed: {last_resp.text if last_resp else 'No response'}"
                )

            data = last_resp.json()
            for emb in data.get("embeddings", []):
                vec = np.array(emb["values"], dtype=np.float32)
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec = vec / norm
                query_vectors.append(vec)

        query_vectors_cache.parent.mkdir(parents=True, exist_ok=True)
        np.save(query_vectors_cache, np.array(query_vectors, dtype=np.float32))

    dense_top10_count = 0
    dense_failures = []
    for i, target_idx in enumerate(sample_indices):
        q_vec = query_vectors[i]
        scores = np.dot(vectors, q_vec)
        top10_idx = np.argsort(scores)[::-1][:10].tolist()
        if target_idx in top10_idx:
            dense_top10_count += 1
        else:
            dense_failures.append(
                (target_idx, chunks[target_idx]["title"], chunks[target_idx]["heading_path"])
            )

    dense_share = dense_top10_count / 100.0
    print(f"   Dense Top-10 share: {dense_share:.2f} ({dense_top10_count}/100)")
    if dense_share < 0.60:
        print(f"   WARNING: Dense top-10 share below 0.60. First failures: {dense_failures[:5]}")

    print("\n=== Sanity Check Summary ===")
    print(f"BM25 Top-1 Share:  {bm25_share:.2f} (Target > 0.85)")
    print(f"Dense Top-10 Share: {dense_share:.2f} (Target > 0.60)")
    print("============================")

    if bm25_share < 0.85 or dense_share < 0.60:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(run_sanity_checks())
