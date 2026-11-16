"""Run offline retrieval evaluation across dense, BM25, hybrid, and hybrid_rerank modes.

Purpose:
    Evaluates retrieval accuracy across 42 answerable evaluation questions using
    Hit@1, Hit@5, MRR, and Evidence Recall@5 on frozen index data/index/.
    Caches query embeddings and reranking responses with diskcache to guarantee
    zero API consumption on reruns.

Inputs:
    - data/index/ (dense and sparse index files)
    - data/eval/eval_set.jsonl (50 items, 42 answerable)
    - .env (COHERE_API_KEY, GOOGLE_API_KEY)

Outputs:
    - results/runs/retrieval-YYYYMMDD/config.json
    - results/runs/retrieval-YYYYMMDD/per_question.jsonl
    - results/runs/retrieval-YYYYMMDD/table.md
"""

import argparse
import hashlib
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from diskcache import Cache
from tqdm import tqdm

from ragdocs.config import Settings, get_settings
from ragdocs.eval.budget_recorder import install_budget_recorder
from ragdocs.eval.metrics import evidence_recall_at_k, hit_at_k, mrr
from ragdocs.index.loader import get_index
from ragdocs.io_utils import read_jsonl, write_jsonl
from ragdocs.providers.embeddings import GeminiEmbedder
from ragdocs.providers.reranker import CohereReranker, Reranker
from ragdocs.retrieval.retriever import HybridRetriever, RetrievalMode
from ragdocs.schemas import EvalItem, RetrievedChunk

MODES: list[RetrievalMode] = ["dense", "bm25", "hybrid", "hybrid_rerank"]


class CachedQueryEmbedder:
    """Cached wrapper around GeminiEmbedder using diskcache."""

    def __init__(self, embedder: GeminiEmbedder, cache_dir: Path) -> None:
        self.embedder = embedder
        self.cache = Cache(str(cache_dir))
        self.model = embedder.model
        self.dim = embedder.dim
        self.api_calls: int = 0

    def embed_query(self, query: str) -> np.ndarray:
        """Return cached embedding or call API and store in cache."""
        raw_key = f"query:{self.model}:{self.dim}:{query}"
        cache_key = hashlib.sha1(raw_key.encode("utf-8")).hexdigest()
        if cache_key in self.cache:
            return np.array(self.cache[cache_key], dtype=np.float32)

        vec = self.embedder.embed_query(query)
        self.cache[cache_key] = vec.tolist()
        self.api_calls += 1
        return vec


class CachedReranker:
    """Cached wrapper around Reranker with rate limiting for uncached calls."""

    def __init__(
        self,
        reranker: Reranker,
        cache_dir: Path,
        min_interval_sec: float = 6.2,
    ) -> None:
        self.reranker = reranker
        self.cache = Cache(str(cache_dir))
        self.min_interval_sec = min_interval_sec
        self.api_calls: int = 0
        self._last_call_time: float = 0.0

    def rerank(self, query: str, texts: list[str], top_n: int) -> list[tuple[int, float]]:
        """Return cached rerank results or call API with throttling and cache result."""
        model = getattr(self.reranker, "model", "noop")
        texts_hash = hashlib.sha1("||".join(texts).encode("utf-8")).hexdigest()
        raw_key = f"rerank:{model}:{query}:{texts_hash}:{top_n}"
        cache_key = hashlib.sha1(raw_key.encode("utf-8")).hexdigest()

        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            return [(int(idx), float(score)) for idx, score in cached_data]

        elapsed = time.time() - self._last_call_time
        if elapsed < self.min_interval_sec:
            time.sleep(self.min_interval_sec - elapsed)

        results = self.reranker.rerank(query=query, texts=texts, top_n=top_n)
        self._last_call_time = time.time()
        self.cache[cache_key] = results
        self.api_calls += 1
        return results


def _sha256_file(path: Path) -> str:
    """Calculate SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def _get_git_commit() -> str:
    """Return current git commit hash or 'unknown'."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "unknown"


def format_rate(rate: float, count: float, total: int) -> str:
    """Format rate and count as 'rate (count/total)'."""
    if abs(count - round(count)) < 1e-4:
        return f"{rate:.3f} ({int(round(count))}/{total})"
    return f"{rate:.3f} ({count:.1f}/{total})"


def run_retrieval_eval(
    settings: Settings | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Execute retrieval evaluation across all modes, write artifacts, and return summary."""
    settings = settings or get_settings()
    index = get_index()
    raw_embedder = GeminiEmbedder(settings)
    raw_reranker = CohereReranker(settings)

    cached_embedder = CachedQueryEmbedder(
        raw_embedder,
        settings.cache_dir / "embeddings",
    )
    cached_reranker = CachedReranker(
        raw_reranker,
        settings.cache_dir / "rerank",
        min_interval_sec=6.2,
    )

    retriever = HybridRetriever(
        index=index,
        embedder=cached_embedder,
        reranker=cached_reranker,
        settings=settings,
    )

    eval_raw = read_jsonl(settings.eval_path)
    eval_items = [EvalItem.model_validate(item) for item in eval_raw]
    answerable = [item for item in eval_items if item.category != "unanswerable"]

    per_question_records: list[dict[str, Any]] = []

    # Accumulators for overall metrics
    # mode -> list of metric values
    metrics_by_mode: dict[str, dict[str, list[float]]] = {
        mode: {"hit@1": [], "hit@5": [], "mrr": [], "evidence_recall@5": []} for mode in MODES
    }
    candidate_hits_20: list[float] = []

    # Category accumulators: category -> mode -> metric -> list of values
    categories = ["single", "multi", "version"]
    metrics_by_cat: dict[str, dict[str, dict[str, list[float]]]] = {
        cat: {
            mode: {"hit@1": [], "hit@5": [], "mrr": [], "evidence_recall@5": []} for mode in MODES
        }
        for cat in categories
    }
    cat_counts: dict[str, int] = {cat: 0 for cat in categories}

    print(f"Evaluating {len(answerable)} answerable questions across {len(MODES)} modes...")
    for item in tqdm(answerable, desc="Evaluating retrieval"):
        cat_counts[item.category] += 1
        q_record: dict[str, Any] = {
            "id": item.id,
            "question": item.question,
            "category": item.category,
            "evidence": [{"doc_path": e.doc_path, "anchor": e.anchor} for e in item.evidence],
            "modes": {},
        }

        # Candidates diagnostic
        candidates = retriever.retrieve_candidates(item.question)
        cand_hit_20 = hit_at_k(candidates, item.evidence, k=20)
        candidate_hits_20.append(cand_hit_20)
        q_record["candidate_hit_at_20"] = cand_hit_20

        # Run each mode
        for mode in MODES:
            retrieved: list[RetrievedChunk] = retriever.retrieve(item.question, mode=mode)
            h1 = hit_at_k(retrieved, item.evidence, k=1)
            h5 = hit_at_k(retrieved, item.evidence, k=5)
            m = mrr(retrieved, item.evidence)
            er5 = evidence_recall_at_k(retrieved, item.evidence, k=5)

            metrics_by_mode[mode]["hit@1"].append(h1)
            metrics_by_mode[mode]["hit@5"].append(h5)
            metrics_by_mode[mode]["mrr"].append(m)
            metrics_by_mode[mode]["evidence_recall@5"].append(er5)

            metrics_by_cat[item.category][mode]["hit@1"].append(h1)
            metrics_by_cat[item.category][mode]["hit@5"].append(h5)
            metrics_by_cat[item.category][mode]["mrr"].append(m)
            metrics_by_cat[item.category][mode]["evidence_recall@5"].append(er5)

            q_record["modes"][mode] = {
                "hit_at_1": h1,
                "hit_at_5": h5,
                "mrr": m,
                "evidence_recall_at_5": er5,
                "retrieved": [
                    {
                        "chunk_id": rc.chunk.chunk_id,
                        "doc_path": rc.chunk.doc_path,
                        "anchor": rc.chunk.anchor,
                        "title": rc.chunk.title,
                        "heading_path": rc.chunk.heading_path,
                        "score": round(rc.score, 6),
                        "rank": rc.rank,
                    }
                    for rc in retrieved
                ],
            }

        per_question_records.append(q_record)

    total_n = len(answerable)

    # Build run directory
    today_str = datetime.now(UTC).strftime("%Y%m%d")
    run_dir = output_dir or (settings.results_dir / "runs" / f"retrieval-{today_str}")
    run_dir.mkdir(parents=True, exist_ok=True)

    # Write per_question.jsonl
    write_jsonl(run_dir / "per_question.jsonl", per_question_records)

    # Build Table 1 (Overall)
    overall_rows: list[str] = [
        "| Mode | Hit@1 | Hit@5 | MRR | Evidence Recall@5 |",
        "|---|---|---|---|---|",
    ]
    for mode in MODES:
        h1_vals = metrics_by_mode[mode]["hit@1"]
        h5_vals = metrics_by_mode[mode]["hit@5"]
        mrr_vals = metrics_by_mode[mode]["mrr"]
        er5_vals = metrics_by_mode[mode]["evidence_recall@5"]

        h1_str = format_rate(sum(h1_vals) / total_n, sum(h1_vals), total_n)
        h5_str = format_rate(sum(h5_vals) / total_n, sum(h5_vals), total_n)
        mrr_str = format_rate(sum(mrr_vals) / total_n, sum(mrr_vals), total_n)
        er5_str = format_rate(sum(er5_vals) / total_n, sum(er5_vals), total_n)

        overall_rows.append(f"| `{mode}` | {h1_str} | {h5_str} | {mrr_str} | {er5_str} |")

    cand_hit20_rate = sum(candidate_hits_20) / total_n
    cand_hit20_count = sum(candidate_hits_20)
    cand_str = format_rate(cand_hit20_rate, cand_hit20_count, total_n)

    # Build Table 2 (Breakdown by Category)
    cat_rows: list[str] = [
        "| Category | Mode | Hit@1 | Hit@5 | MRR | Evidence Recall@5 |",
        "|---|---|---|---|---|---|",
    ]
    for cat in categories:
        n_cat = cat_counts[cat]
        for mode in MODES:
            h1_vals = metrics_by_cat[cat][mode]["hit@1"]
            h5_vals = metrics_by_cat[cat][mode]["hit@5"]
            mrr_vals = metrics_by_cat[cat][mode]["mrr"]
            er5_vals = metrics_by_cat[cat][mode]["evidence_recall@5"]

            h1_str = format_rate(sum(h1_vals) / n_cat, sum(h1_vals), n_cat)
            h5_str = format_rate(sum(h5_vals) / n_cat, sum(h5_vals), n_cat)
            mrr_str = format_rate(sum(mrr_vals) / n_cat, sum(mrr_vals), n_cat)
            er5_str = format_rate(sum(er5_vals) / n_cat, sum(er5_vals), n_cat)

            cat_rows.append(
                f"| {cat} (N={n_cat}) | `{mode}` | {h1_str} | {h5_str} | {mrr_str} | {er5_str} |"
            )

    table_md_content = (
        "### Overall Retrieval Performance (N=42 Answerable Questions)\n\n"
        + "\n".join(overall_rows)
        + f"\n\n*Diagnostic Candidate Pool Recall: `retrieve_candidates` Hit@20 = {cand_str}*\n\n"
        + "### Retrieval Performance Broken Down by Category\n\n"
        + "\n".join(cat_rows)
        + "\n"
    )

    with open(run_dir / "table.md", "w", encoding="utf-8", newline="\n") as f:
        f.write(table_md_content)

    # Write config.json
    manifest_path = settings.index_dir / "manifest.json"
    manifest_hash = _sha256_file(manifest_path) if manifest_path.is_file() else "unknown"
    git_commit = _get_git_commit()

    config_data: dict[str, Any] = {
        "date": today_str,
        "git_commit": git_commit,
        "index_manifest_hash": manifest_hash,
        "model_ids": {
            "embedding_model": settings.embedding_model,
            "rerank_model": settings.rerank_model,
        },
        "settings": {
            "embedding_dim": settings.embedding_dim,
            "dense_k": settings.dense_k,
            "bm25_k": settings.bm25_k,
            "rrf_k": settings.rrf_k,
            "fused_k": settings.fused_k,
            "rerank_top_n": settings.rerank_top_n,
            "final_k": settings.final_k,
            "use_reranker": settings.use_reranker,
        },
        "api_calls_made": {
            "query_embeddings": cached_embedder.api_calls,
            "rerank_requests": cached_reranker.api_calls,
        },
    }

    with open(run_dir / "config.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(config_data, f, indent=2)

    # Find failures (questions where NO mode retrieved within top 5)
    unretrieved_top5: list[dict[str, Any]] = []
    for item in per_question_records:
        if all(item["modes"][mode]["hit_at_5"] == 0.0 for mode in MODES):
            # Grab top 3 retrieved headings from hybrid_rerank (or hybrid)
            headings: list[str] = []
            for rc in item["modes"]["hybrid_rerank"]["retrieved"][:3]:
                path_str = " > ".join(rc["heading_path"])
                headings.append(f"{rc['title']} > {path_str} ({rc['doc_path']}#{rc['anchor']})")
            unretrieved_top5.append(
                {
                    "id": item["id"],
                    "question": item["question"],
                    "category": item["category"],
                    "evidence": item["evidence"],
                    "top_3_headings": headings,
                }
            )

    hybrid_hit5_count = int(round(sum(metrics_by_mode["hybrid"]["hit@5"])))
    rerank_hit5_count = int(round(sum(metrics_by_mode["hybrid_rerank"]["hit@5"])))
    d6_gain = rerank_hit5_count - hybrid_hit5_count

    print("\n--- Retrieval Evaluation Summary ---")
    print(table_md_content)
    print(
        f"API calls made: embeddings={cached_embedder.api_calls}, "
        f"rerank={cached_reranker.api_calls}"
    )
    print(
        f"D6 Gate: hybrid Hit@5 = {hybrid_hit5_count}/42, "
        f"hybrid_rerank Hit@5 = {rerank_hit5_count}/42"
    )
    print(f"D6 Gain = {d6_gain} questions")
    print(f"Unretrieved questions across all modes (Hit@5 == 0): {len(unretrieved_top5)}")

    return {
        "run_dir": str(run_dir),
        "d6_gain": d6_gain,
        "hybrid_hit5_count": hybrid_hit5_count,
        "rerank_hit5_count": rerank_hit5_count,
        "unretrieved_top5": unretrieved_top5,
        "api_calls": {
            "embeddings": cached_embedder.api_calls,
            "rerank": cached_reranker.api_calls,
        },
    }


def main() -> None:
    """CLI entrypoint for offline retrieval evaluation."""
    parser = argparse.ArgumentParser(description="Evaluate retrieval pipeline configurations.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Custom output directory")
    args = parser.parse_args()

    install_budget_recorder()
    run_retrieval_eval(output_dir=args.output_dir)


if __name__ == "__main__":
    main()
