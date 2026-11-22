"""Scan the commits and tags a push would send for secrets, oversized files and stray files.

Purpose: run by hand before `git push` (not in CI). Finds key patterns and secret-looking
assignments in added lines, the exact values of secret variables from the local .env, tag
messages that contain either, blobs larger than a limit, and tracked files that must not
be tracked.
Inputs: --range REV_RANGE (default origin/main..HEAD); --max-blob-mb N (default 50);
--repo DIR (default the current directory); --env-file PATH (default <repo>/.env).
Output: one line per finding, "<commit or tag> <path> <line> <pattern or variable name>",
then a summary line (objects and total size in the range). It never prints a matched value
and never prints the value of an .env variable. Variables whose name ends in _KEY, _TOKEN,
_SECRET or _SALT are read in-process; values shorter than MIN_VALUE_CHARS are not searched
(their names are listed as "skipped").
Exit code: 0 when there are no findings, 1 otherwise.
Usage: .venv/Scripts/python tools/secret_scan.py --range origin/main..HEAD
Standard library only; never imports ragdocs.
"""

import argparse
import re
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

MIN_VALUE_CHARS = 8
DEFAULT_RANGE = "origin/main..HEAD"
DEFAULT_MAX_BLOB_MB = 50.0
BYTES_PER_MB = 1024 * 1024
SECRET_SUFFIXES = ("_KEY", "_TOKEN", "_SECRET", "_SALT")

KEY_PATTERNS: dict[str, re.Pattern[str]] = {
    "groq-key": re.compile(r"gsk_[A-Za-z0-9]{20,}"),
    "google-key": re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
    "tavily-key": re.compile(r"tvly-[^\s'\"`]{20,}"),
    "langsmith-key": re.compile(r"lsv2_(?:pt|sk)_[A-Za-z0-9_]+"),
    "private-key-header": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}
ASSIGNMENT = re.compile(r"\b([A-Z][A-Z0-9_]*(?:_KEY|_TOKEN|_SECRET|_SALT))\s*=(?!=)\s*(\S.*)$")
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)")
FORBIDDEN_DIRS = ("cache", ".venv", "node_modules")


@dataclass(frozen=True)
class Finding:
    """One finding; `what` names a pattern, variable or rule, never a value."""

    where: str
    path: str
    line: int
    what: str


def git(repo: Path, *args: str) -> str:
    """Run git in repo and return stdout (UTF-8)."""
    out = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        check=True,
        encoding="utf-8",
        errors="replace",
    )
    return out.stdout


def read_env_secrets(env_file: Path) -> tuple[dict[str, str], list[str]]:
    """Return ({name: value} to search for, [names skipped as too short]) from a .env file."""
    secrets: dict[str, str] = {}
    skipped: list[str] = []
    if not env_file.is_file():
        return secrets, skipped
    for raw in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip().strip("'\"")
        if not name.endswith(SECRET_SUFFIXES) or not value:
            continue
        if len(value) < MIN_VALUE_CHARS:
            skipped.append(name)
        else:
            secrets[name] = value
    return secrets, skipped


def scan_line(text: str, env_secrets: dict[str, str]) -> list[str]:
    """Return the pattern or variable names that match one line (never values)."""
    hits = [name for name, pattern in KEY_PATTERNS.items() if pattern.search(text)]
    match = ASSIGNMENT.search(text)
    if match and match.group(2).strip().strip("'\"` ,;"):
        hits.append(f"assignment:{match.group(1)}")
    hits += [f"env:{name}" for name, value in env_secrets.items() if value in text]
    return hits


def added_lines(repo: Path, rev_range: str) -> Iterator[tuple[str, str, int, str]]:
    """Yield (commit, path, new line number, text) for every added line in the range."""
    cmd = ["git", "log", "-p", "--no-color", "--no-ext-diff", "--format=commit %H", rev_range]
    proc = subprocess.Popen(
        cmd, cwd=repo, stdout=subprocess.PIPE, encoding="utf-8", errors="replace"
    )
    assert proc.stdout is not None
    commit, path, number = "", "", 0
    for line in proc.stdout:
        line = line.rstrip("\n")
        if line.startswith("commit ") and len(line) == 47:
            commit = line[7:]
        elif line.startswith("diff --git"):
            path = ""
        elif line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else ""
        elif m := HUNK.match(line):
            number = int(m.group(1))
        elif line.startswith("+") and path:
            yield commit, path, number, line[1:]
            number += 1
        elif line.startswith(" ") and path:
            number += 1
    if proc.wait() != 0:
        raise RuntimeError(f"git log failed for range {rev_range}")


def scan_commits(repo: Path, rev_range: str, env_secrets: dict[str, str]) -> list[Finding]:
    """Scan the added lines of every commit in the range."""
    found = []
    for commit, path, number, text in added_lines(repo, rev_range):
        found += [Finding(commit[:12], path, number, hit) for hit in scan_line(text, env_secrets)]
    return found


def scan_tags(repo: Path, rev_range: str, env_secrets: dict[str, str]) -> list[Finding]:
    """Scan the messages of annotated tags that point at a commit in the range."""
    in_range = set(git(repo, "rev-list", rev_range).split())
    refs = git(
        repo, "for-each-ref", "refs/tags", "--format=%(refname:short) %(objecttype) %(*objectname)"
    )
    found = []
    for row in refs.splitlines():
        parts = row.split()
        if len(parts) != 3 or parts[1] != "tag" or parts[2] not in in_range:
            continue
        for number, text in enumerate(git(repo, "cat-file", "tag", parts[0]).splitlines(), 1):
            found += [
                Finding(f"tag:{parts[0]}", "(tag message)", number, h)
                for h in scan_line(text, env_secrets)
            ]
    return found


def range_objects(repo: Path, rev_range: str) -> list[tuple[str, int, str]]:
    """Return (blob sha, size in bytes, path) for every blob the range adds."""
    listing = git(repo, "rev-list", "--objects", rev_range)
    names = {}
    for row in listing.splitlines():
        sha, _, path = row.partition(" ")
        names[sha] = path
    if not names:
        return []
    batch = subprocess.run(
        ["git", "cat-file", "--batch-check=%(objecttype) %(objectname) %(objectsize)"],
        cwd=repo,
        input="\n".join(names) + "\n",
        capture_output=True,
        check=True,
        encoding="utf-8",
    ).stdout
    objects = []
    for row in batch.splitlines():
        kind, sha, size = row.split()
        if kind == "blob":
            objects.append((sha, int(size), names[sha]))
    return objects


def scan_blobs(objects: list[tuple[str, int, str]], max_mb: float) -> list[Finding]:
    """List blobs larger than max_mb."""
    return [
        Finding(sha[:12], path, 0, f"blob {size / BYTES_PER_MB:.1f} MB over {max_mb:g} MB")
        for sha, size, path in objects
        if size > max_mb * BYTES_PER_MB
    ]


def scan_tracked(repo: Path) -> list[Finding]:
    """Flag tracked .env files and files under cache/, .venv/ or node_modules/."""
    found = []
    for path in git(repo, "ls-files").splitlines():
        parts = path.split("/")
        name = parts[-1]
        if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
            found.append(Finding("tracked", path, 0, "env file is tracked"))
        elif any(d in parts[:-1] for d in FORBIDDEN_DIRS):
            found.append(Finding("tracked", path, 0, "forbidden directory is tracked"))
    return found


def run_scan(repo: Path, rev_range: str, env_file: Path, max_mb: float) -> int:
    """Run every scan, print the findings and a summary; return the exit code."""
    secrets, skipped = read_env_secrets(env_file)
    objects = range_objects(repo, rev_range)
    findings = (
        scan_commits(repo, rev_range, secrets)
        + scan_tags(repo, rev_range, secrets)
        + scan_blobs(objects, max_mb)
        + scan_tracked(repo)
    )
    for f in findings:
        print(f"{f.where} {f.path} {f.line} {f.what}")
    total = sum(size for _, size, _ in objects)
    print(f"range {rev_range}: {len(objects)} blobs, {total / BYTES_PER_MB:.2f} MB")
    names = ", ".join(skipped) or "none"
    print(
        f"env variables searched: {len(secrets)}; skipped (under {MIN_VALUE_CHARS} chars): {names}"
    )
    print(f"findings: {len(findings)}")
    return 1 if findings else 0


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run the scan."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--range", default=DEFAULT_RANGE, dest="rev_range")
    parser.add_argument("--max-blob-mb", type=float, default=DEFAULT_MAX_BLOB_MB)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--env-file", type=Path, default=None)
    args = parser.parse_args(argv)
    env_file = args.env_file or args.repo / ".env"
    return run_scan(args.repo, args.rev_range, env_file, args.max_blob_mb)


if __name__ == "__main__":
    sys.exit(main())
