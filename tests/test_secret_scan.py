"""Tests for tools/secret_scan.py using a temporary git repository."""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("secret_scan", ROOT / "tools" / "secret_scan.py")
assert spec and spec.loader
scan = importlib.util.module_from_spec(spec)
sys.modules["secret_scan"] = scan
spec.loader.exec_module(scan)

ENV_VALUE = "zz-fake-env-value-98765"
# Every fake secret below is built at run time from parts, so no literal in this file
# matches a scanner pattern (the scanner also scans this file).
FAKE_GROQ = "gsk" + "_" + "A" * 24
KEY = "_K" + "EY"
TOKEN = "_TO" + "KEN"


def git(repo: Path, *args: str) -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, env=env)


def commit(repo: Path, files: dict[str, str | bytes], message: str) -> None:
    for name, content in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8", newline="\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", message)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / ".env").write_text(f"SOME_API{KEY}={ENV_VALUE}\nSHORT_SALT=abc\n", encoding="utf-8")
    commit(tmp_path, {"README.md": "base\n", ".gitignore": ".env\n"}, "base")
    git(tmp_path, "tag", "base")
    return tmp_path


def run(repo: Path, capsys: pytest.CaptureFixture[str], *extra: str) -> tuple[int, str]:
    code = scan.main(["--repo", str(repo), "--range", "base..HEAD", *extra])
    return code, capsys.readouterr().out


def test_clean_range_exits_zero(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A range with harmless changes has no findings."""
    commit(repo, {"a.txt": "hello\n"}, "harmless")
    code, out = run(repo, capsys)
    assert code == 0
    assert "findings: 0" in out


def test_fake_groq_key_found(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A gsk_ key in an added line is reported by path, line and pattern, not by value."""
    commit(repo, {"cfg/x.txt": f"first\nkey {FAKE_GROQ}\n"}, "adds key")
    code, out = run(repo, capsys)
    assert code == 1
    assert "cfg/x.txt 2 groq-key" in out
    assert FAKE_GROQ not in out


def test_env_value_found_without_printing_it(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The exact value of an .env secret is found; only the variable name is printed."""
    commit(repo, {"notes.md": f"the value is {ENV_VALUE} here\n"}, "leaks env value")
    code, out = run(repo, capsys)
    assert code == 1
    assert f"notes.md 1 env:SOME_API{KEY}" in out
    assert ENV_VALUE not in out


def test_assignment_pattern(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A non-empty assignment to a *_TOKEN name is reported; an empty one is not."""
    commit(repo, {"e.txt": f"MY{TOKEN}=\nOTHER{TOKEN}=realvalue\n"}, "assigns")
    code, out = run(repo, capsys)
    assert code == 1
    assert f"e.txt 2 assignment:OTHER{TOKEN}" in out
    assert "e.txt 1" not in out


def test_oversized_blob_listed(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A blob over --max-blob-mb is listed."""
    commit(repo, {"big.bin": os.urandom(3000)}, "big file")
    code, out = run(repo, capsys, "--max-blob-mb", "0.001")
    assert code == 1
    assert "big.bin 0 blob" in out


def test_tag_message_scanned(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """An annotated tag in the range with a key in its message is reported."""
    commit(repo, {"a.txt": "x\n"}, "c")
    git(repo, "tag", "-a", "v1", "-m", f"release {FAKE_GROQ}")
    code, out = run(repo, capsys)
    assert code == 1
    assert "tag:v1" in out and FAKE_GROQ not in out


def test_tracked_env_file_flagged(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A tracked .env, or a file under cache/, is flagged; .env.example is allowed."""
    commit(repo, {".env.example": f"A{KEY}=\n", "cache/x.json": "{}\n"}, "tracked cache")
    code, out = run(repo, capsys)
    assert code == 1
    assert "cache/x.json" in out
    assert ".env.example" not in out
