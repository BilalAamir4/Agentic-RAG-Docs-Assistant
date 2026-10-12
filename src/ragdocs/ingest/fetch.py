"""Fetch and shallow-clone the documentation source repository at a pinned commit."""

import subprocess
from pathlib import Path


def fetch_repo(repo_url: str, commit: str, dest_dir: Path) -> Path:
    """Clone repository into dest_dir with a shallow fetch of exact commit SHA.

    If the folder already exists and is checked out at that commit SHA, this is a no-op.
    Passes -c core.longpaths=true to every git command for Windows path compatibility.
    """
    dest_path = Path(dest_dir).resolve()
    git_dir = dest_path / ".git"

    if git_dir.exists():
        # Check current HEAD commit
        res = subprocess.run(
            ["git", "-c", "core.longpaths=true", "rev-parse", "HEAD"],
            cwd=dest_path,
            capture_output=True,
            text=True,
        )
        if res.returncode == 0 and res.stdout.strip().startswith(commit[:12]):
            return dest_path

    dest_path.mkdir(parents=True, exist_ok=True)

    def run_git(cmd_args: list[str]) -> None:
        cmd = ["git", "-c", "core.longpaths=true"] + cmd_args
        res = subprocess.run(cmd, cwd=dest_path, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(
                f"Git command failed: {' '.join(cmd)}\nStderr: {res.stderr}\nStdout: {res.stdout}"
            )

    if not git_dir.exists():
        run_git(["init"])
        run_git(["remote", "add", "origin", repo_url])
    else:
        # Remote may already exist; verify or set url
        run_git(["remote", "set-url", "origin", repo_url])

    run_git(["fetch", "--depth", "1", "origin", commit])
    run_git(["checkout", "FETCH_HEAD"])

    return dest_path
