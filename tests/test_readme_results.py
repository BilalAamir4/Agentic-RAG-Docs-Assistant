"""README results block: render, --check behaviour, numbers and verdict wording (M15)."""

import importlib.util
from pathlib import Path

import pytest

from ragdocs.config import REPO_ROOT, get_settings
from ragdocs.eval.compare import NO_DIFFERENCE, count_verdict
from ragdocs.eval.format import fmt_calls, fmt_mean, fmt_ms_as_s, fmt_rate, fmt_tokens
from ragdocs.eval.readme_results import (
    BLOCK_END,
    BLOCK_START,
    MAIN_ROWS,
    ResultsInputs,
    build_block,
    check_readme,
    default_inputs,
    extract_block,
    replace_block,
    run,
)
from ragdocs.eval.report import summarize


@pytest.fixture(scope="module")
def inputs() -> ResultsInputs:
    return default_inputs()


@pytest.fixture(scope="module")
def block(inputs: ResultsInputs) -> str:
    return build_block(inputs)


def test_count_verdict_at_two_and_three() -> None:
    assert count_verdict(10, 12, 3) == NO_DIFFERENCE
    assert count_verdict(12, 10, 3) == NO_DIFFERENCE
    assert count_verdict(10, 13, 3) == "measurable (+3)"
    assert count_verdict(13, 10, 3) == "measurable (-3)"
    assert count_verdict(5, 5, 3) == NO_DIFFERENCE


def test_block_is_deterministic_and_lf_only(inputs: ResultsInputs, block: str) -> None:
    assert build_block(inputs) == block
    assert "\r" not in block
    assert block.endswith("\n") and not block.endswith("\n\n")


def test_write_then_check_passes(tmp_path: Path, inputs: ResultsInputs, block: str) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("# Title\n\nIntro.\n", encoding="utf-8", newline="\n")
    assert run(readme, inputs, check=False, out=lambda m: None) == 0
    text = readme.read_bytes().decode("utf-8")
    assert text.startswith("# Title\n\nIntro.\n\n## Results\n\n" + BLOCK_START)
    assert extract_block(text) == block
    assert run(readme, inputs, check=True, out=lambda m: None) == 0


def test_check_fails_on_edited_number(tmp_path: Path, inputs: ResultsInputs, block: str) -> None:
    readme = tmp_path / "README.md"
    readme.write_bytes(replace_block("", block).replace("90.5% (38/42)", "90.5% (39/42)").encode())
    messages: list[str] = []
    assert run(readme, inputs, check=True, out=messages.append) == 1
    assert "-" in messages[0] and "39/42" in messages[0] and "38/42" in messages[0]


def test_check_passes_with_crlf(tmp_path: Path, inputs: ResultsInputs, block: str) -> None:
    readme = tmp_path / "README.md"
    readme.write_bytes(replace_block("# T\n", block).replace("\n", "\r\n").encode())
    assert run(readme, inputs, check=True, out=lambda m: None) == 0


def test_check_fails_without_markers(tmp_path: Path, inputs: ResultsInputs, block: str) -> None:
    assert check_readme("# Title\n", block) is not None
    readme = tmp_path / "README.md"
    readme.write_text("# Title\n", encoding="utf-8", newline="\n")
    messages: list[str] = []
    assert run(readme, inputs, check=True, out=messages.append) == 1
    assert "markers" in messages[0]
    assert run(tmp_path / "missing.md", inputs, check=True, out=lambda m: None) == 1


def test_write_replaces_only_the_block(inputs: ResultsInputs, block: str) -> None:
    text = f"before\n{BLOCK_START}\nold\n{BLOCK_END}\nafter\n"
    new = replace_block(text, block)
    assert new.startswith("before\n") and new.endswith(f"{BLOCK_END}\nafter\n")
    assert "old" not in new and extract_block(new) == block


def _expected(summary_value: object, kind: str) -> str:
    """The cell for a summarize() value, built independently of the generator's _cell."""
    if kind == "rate":
        v = summary_value
        return fmt_rate(v["count"], v["n"])  # type: ignore[index]
    if kind == "mean":
        v = summary_value
        return fmt_mean(v["mean"], v["n"])  # type: ignore[index]
    value = summary_value["mean"] if isinstance(summary_value, dict) else summary_value
    return {"calls": fmt_calls, "tokens": fmt_tokens, "seconds": fmt_ms_as_s}[kind](value)


def test_every_row_equals_summarize_for_each_pipeline(inputs: ResultsInputs, block: str) -> None:
    main = block.split("### Is the difference real?")[0]
    for column, name in enumerate(("baseline", "corrective", "self_rag")):
        overall = summarize(inputs.run_dirs[name])["overall"]
        for label, field, kind in MAIN_ROWS:
            line = next(ln for ln in main.splitlines() if ln.startswith(f"| {label} |"))
            cells = [c.strip() for c in line.strip("|").split("|")]
            assert cells[1 + column] == _expected(overall[field], kind), (name, label)


def test_rows_use_the_fields_export_results_uses() -> None:
    spec = importlib.util.spec_from_file_location(
        "export_results", REPO_ROOT / "scripts" / "export_results.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    exported = {m[4]: m[2] for m in module.METRICS}
    readme = {field: kind for _, field, kind in MAIN_ROWS}
    shared = set(exported) & set(readme)
    assert shared == set(exported)  # the README shows all 14 web metrics
    for field in shared:
        web_kind, kind = exported[field], readme[field]
        assert (web_kind == "rate") == (kind == "rate") and (web_kind == "mean") == (kind == "mean")
    assert set(readme) - set(exported) == {"false_abstention", "used_web", "latency_ms_p95"}


def test_committed_runs_match_known_figures(block: str) -> None:
    assert "| Correct answers | 90.5% (38/42) | 88.1% (37/42) | 85.7% (36/42) |" in block
    assert "| Mean tokens per question | 2,334 | 4,577 | 6,847 |" in block
    assert "D6 reranker gate" in block and "gain of 1 question" in block
    assert get_settings().compare_noise_margin == 3
