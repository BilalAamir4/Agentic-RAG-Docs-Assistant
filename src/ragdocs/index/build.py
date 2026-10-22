"""Offline index builder generating dense embeddings and sparse BM25 token structures."""

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from diskcache import Cache
from tqdm import tqdm

from ragdocs.config import Settings, get_settings
from ragdocs.index.bm25_index import tokenize
from ragdocs.io_utils import read_jsonl, write_jsonl
from ragdocs.providers.embeddings import GeminiEmbedder
from ragdocs.schemas import Chunk

BATCH_SIZE = 100
TASK_TYPE_DOCUMENT = "RETRIEVAL_DOCUMENT"


def _sha256_file(path: Path) -> str:
    """Calculate the SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def _cache_key(model: str, dim: int, task_type: str, text: str) -> str:
    """Compute sha1 hash key for caching embeddings."""
    raw = f"{model}:{dim}:{task_type}:{text}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def build_index(
    settings: Settings | None = None,
    chunks_path: Path | None = None,
    index_dir: Path | None = None,
    show_progress: bool = True,
) -> dict[str, Any]:
    """Build vectors.f16.npy, chunk_meta.jsonl, bm25.json, and manifest.json."""
    settings = settings or get_settings()
    chunks_file = chunks_path or (settings.data_dir / "processed" / "chunks.jsonl")
    target_dir = index_dir or settings.index_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    if not chunks_file.is_file():
        raise FileNotFoundError(f"Input chunks file not found: {chunks_file}")

    raw_chunks = read_jsonl(chunks_file)
    chunks = [Chunk.model_validate(c) for c in raw_chunks]
    n_chunks = len(chunks)

    model_id = settings.embedding_model or "gemini-embedding-001"
    dim = settings.embedding_dim

    cache_dir = settings.cache_dir / "embeddings"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache = Cache(str(cache_dir))

    embedder: GeminiEmbedder | None = None
    api_calls = 0

    # 1. Determine which chunks need API calls
    keys = [_cache_key(model_id, dim, TASK_TYPE_DOCUMENT, c.embed_text) for c in chunks]
    missing_indices = [idx for idx, key in enumerate(keys) if key not in cache]

    if missing_indices:
        embedder = GeminiEmbedder(settings=settings)
        pbar = tqdm(
            total=len(missing_indices),
            desc="Embedding chunks",
            disable=not show_progress,
        )
        for i in range(0, len(missing_indices), BATCH_SIZE):
            batch_indices = missing_indices[i : i + BATCH_SIZE]
            batch_texts = [chunks[idx].embed_text for idx in batch_indices]
            batch_vectors = embedder.embed_documents(batch_texts)

            for idx, vec in zip(batch_indices, batch_vectors, strict=True):
                cache[keys[idx]] = vec.tolist()

            pbar.update(len(batch_indices))
            if i + BATCH_SIZE < len(missing_indices):
                time.sleep(25)
        pbar.close()
        api_calls = embedder.api_calls

    # 2. Assemble vector matrix
    all_vectors = np.empty((n_chunks, dim), dtype=np.float32)
    for idx, key in enumerate(keys):
        all_vectors[idx] = np.array(cache[key], dtype=np.float32)

    cache.close()

    # Save float16 vectors
    vectors_path = target_dir / "vectors.f16.npy"
    vectors_f16 = all_vectors.astype(np.float16)
    np.save(vectors_path, vectors_f16)

    # 3. Save chunk_meta.jsonl
    meta_path = target_dir / "chunk_meta.jsonl"
    write_jsonl(meta_path, [c.model_dump() for c in chunks])

    # 4. Tokenize and save bm25.json
    pbar_bm25 = tqdm(chunks, desc="Tokenizing BM25", disable=not show_progress)
    tokens_list = [tokenize(c.embed_text) for c in pbar_bm25]
    pbar_bm25.close()

    bm25_data = {
        "tokenizer_version": 1,
        "tokens": tokens_list,
    }
    bm25_path = target_dir / "bm25.json"
    with open(bm25_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(bm25_data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # 5. Build manifest.json
    chunks_sha256 = _sha256_file(chunks_file)
    source_commit = chunks[0].source_commit if chunks else ""
    manifest = {
        "built_on": datetime.now(UTC).isoformat(),
        "source_commit": source_commit,
        "chunks_sha256": chunks_sha256,
        "n_chunks": n_chunks,
        "embedding_model": model_id,
        "embedding_dim": dim,
        "files": {
            "vectors.f16.npy": _sha256_file(vectors_path),
            "chunk_meta.jsonl": _sha256_file(meta_path),
            "bm25.json": _sha256_file(bm25_path),
        },
    }
    manifest_path = target_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")

    return {
        "n_chunks": n_chunks,
        "api_calls": api_calls,
        "vectors_path": vectors_path,
        "meta_path": meta_path,
        "bm25_path": bm25_path,
        "manifest_path": manifest_path,
        "files": manifest["files"],
    }
