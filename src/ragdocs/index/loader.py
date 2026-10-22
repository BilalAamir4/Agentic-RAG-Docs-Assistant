"""Runtime index loader with integrity validation and process-level caching."""

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from ragdocs.config import get_settings
from ragdocs.index.bm25_index import BM25Index
from ragdocs.index.vector_index import VectorIndex


@dataclass(frozen=True)
class LoadedIndex:
    """Container holding loaded dense and sparse indexes along with manifest data."""

    vector_index: VectorIndex
    bm25_index: BM25Index
    manifest: dict[str, Any]


def _sha256_file(path: Path) -> str:
    """Calculate the SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def load_index(index_dir: Path | str | None = None) -> LoadedIndex:
    """Load and verify dense and sparse indexes from index_dir against manifest.json."""
    if index_dir is None:
        index_dir = get_settings().index_dir
    p = Path(index_dir)
    manifest_path = p / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Index manifest not found at {manifest_path}")

    with open(manifest_path, encoding="utf-8") as f:
        manifest: dict[str, Any] = json.load(f)

    files_dict: dict[str, str] = manifest.get("files", {})
    for filename, expected_hash in files_dict.items():
        file_path = p / filename
        if not file_path.is_file():
            raise FileNotFoundError(f"Required index file missing: {file_path}")
        actual_hash = _sha256_file(file_path)
        if actual_hash != expected_hash:
            raise ValueError(
                f"Index checksum mismatch for {filename}: "
                f"expected {expected_hash}, got {actual_hash}"
            )

    vector_index = VectorIndex.load(p)
    bm25_index = BM25Index.load(p / "bm25.json")

    n_chunks = manifest.get("n_chunks")
    n_vec = len(vector_index.vectors)
    n_chunks_meta = len(vector_index.chunks)
    n_bm25 = len(bm25_index.tokens)

    if not (n_vec == n_chunks_meta == n_bm25 == n_chunks):
        raise ValueError(
            f"Index row count mismatch: manifest={n_chunks}, vectors={n_vec}, "
            f"chunk_meta={n_chunks_meta}, bm25={n_bm25}"
        )

    return LoadedIndex(vector_index=vector_index, bm25_index=bm25_index, manifest=manifest)


@lru_cache(maxsize=1)
def get_index() -> LoadedIndex:
    """Retrieve and cache the loaded index for the process lifetime."""
    return load_index(get_settings().index_dir)
