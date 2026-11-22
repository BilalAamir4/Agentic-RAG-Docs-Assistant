"""Tests for the committed frontend assets in public/ and web/public/ (M13).

Build-dependent tests fail (not skip) when public/ has not been built.
"""

import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType

from ragdocs.eval.report import summarize

REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLIC = REPO_ROOT / "public"
WEB_RESULTS = REPO_ROOT / "web" / "public" / "results.json"
EXAMPLES = REPO_ROOT / "web" / "src" / "data" / "examples.json"
EVAL_SET = REPO_ROOT / "data" / "eval" / "eval_set.jsonl"
BUILD_HINT = "public/ is not built: run py tasks.py web-build"
KEYS = [
    "correct",
    "correct_or_partial",
    "citation_support",
    "abstention_correct",
    "hallucinated",
    "first_retrieval_hit_at_5",
    "context_hit_at_5",
    "ragas_faithfulness",
    "ragas_response_relevancy",
    "ragas_context_precision",
    "ragas_context_recall",
    "mean_llm_calls",
    "mean_tokens",
    "p50_latency_ms",
]
LABELS = ["Baseline RAG", "Corrective RAG", "Self-RAG"]


def _exporter() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "export_results", REPO_ROOT / "scripts" / "export_results.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _require_build() -> None:
    assert (PUBLIC / "index.html").is_file(), BUILD_HINT
    assert (PUBLIC / "assets").is_dir(), BUILD_HINT


def test_results_json_schema_and_order() -> None:
    data = json.loads(WEB_RESULTS.read_text(encoding="utf-8"))
    assert list(data) == ["generated_on", "n_questions", "eval_set_sha256", "pipelines"]
    assert data["n_questions"] == 50
    assert [p["label"] for p in data["pipelines"]] == LABELS
    for p in data["pipelines"]:
        assert list(p) == ["name", "label", "run_dir", "metrics"]
        assert list(p["metrics"]) == KEYS
        for m in p["metrics"].values():
            assert list(m) == ["label", "value", "count", "n", "kind", "unit"]
            assert m["kind"] in ("rate", "mean", "number")
            assert isinstance(m["n"], int)
            if m["kind"] == "rate":
                assert isinstance(m["count"], int)
                assert 0 <= m["value"] <= 1
                assert m["unit"] is None
            else:
                assert m["count"] is None


def test_results_json_matches_summarize_now() -> None:
    data = json.loads(WEB_RESULTS.read_text(encoding="utf-8"))
    exporter = _exporter()
    spec_by_key = {s[0]: s for s in exporter.METRICS}
    for p in data["pipelines"]:
        overall = summarize(REPO_ROOT / p["run_dir"])["overall"]
        for key, metric in p["metrics"].items():
            expected = exporter.metric_entry(overall, spec_by_key[key])
            assert metric == expected, (p["name"], key)


def _eval_items() -> list[dict]:
    lines = EVAL_SET.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_examples_match_eval_set() -> None:
    examples = json.loads(EXAMPLES.read_text(encoding="utf-8"))
    items = {i["id"]: i for i in _eval_items()}
    assert [e["category"] for e in examples] == ["single", "multi", "version", "unanswerable"]
    assert [e["label"] for e in examples] == [
        "Single page",
        "Multi-page",
        "Version change",
        "Not in the docs",
    ]
    for e in examples:
        assert e["id"] in items
        assert items[e["id"]]["question"] == e["question"]
        assert items[e["id"]]["category"] == e["category"]
        lowest = min(i["id"] for i in items.values() if i["category"] == e["category"])
        assert e["id"] == lowest


def test_built_results_identical_to_source() -> None:
    _require_build()
    assert (PUBLIC / "results.json").read_bytes() == WEB_RESULTS.read_bytes()


def test_index_html_is_clean() -> None:
    _require_build()
    html = (PUBLIC / "index.html").read_text(encoding="utf-8")
    assert "<title>LangGraph Docs Assistant</title>" in html
    assert not re.search(r"<style", html, re.I)
    assert not re.search(r"\sstyle\s*=", html, re.I)
    for body in re.findall(r"<script\b[^>]*>(.*?)</script>", html, re.I | re.S):
        assert body.strip() == "", "inline script body"
    for src in re.findall(r"<script\b[^>]*\bsrc=\"([^\"]+)\"", html, re.I):
        assert re.fullmatch(r"/assets/[^/]+\.js", src), src
    for href in re.findall(r"<link\b[^>]*rel=\"stylesheet\"[^>]*href=\"([^\"]+)\"", html, re.I):
        assert re.fullmatch(r"/assets/[^/]+\.css", href), href
    assert not re.search(r"<(script|link)\b[^>]*(src|href)=\"https?://", html, re.I)


def test_css_has_no_fonts_or_remote_urls() -> None:
    _require_build()
    css_files = list((PUBLIC / "assets").glob("*.css"))
    assert css_files, BUILD_HINT
    for css in css_files:
        text = css.read_text(encoding="utf-8")
        for banned in ("@font-face", "url(http", "@import"):
            assert banned not in text, f"{css.name} contains {banned}"
