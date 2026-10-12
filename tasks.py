"""Cross-platform task runner for ragdocs.

Commands:
  setup           Create virtual environment, upgrade pip, install dependencies and package
  lint            Run ruff check and ruff format --check
  format          Run ruff format and ruff check --fix
  test            Run unit tests with pytest (-m "not live")
  test-live       Run live tests with pytest (-m live)
  tree            Print repository tree skipping caches and gitignored folders
  hash            Print sha256 checksum and path for specified files
  ingest          Run documentation ingestion pipeline (added in M02)
  index           Build dense and sparse indexes (added in M04)
  eval            Run pipeline evaluation (added in M07)
  validate-eval   Validate evaluation dataset format (added in M03)
  dev             Run local development server (added in M10)
  bundle-check    Check deployment bundle size (added in M01)
  smoke           Run smoke tests against deployed service (added in M12)
"""

import argparse
import fnmatch
import hashlib
import subprocess
import sys
import venv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

if sys.platform == "win32":
    try:
        if sys.stdout.encoding != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr.encoding != "utf-8":
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def get_venv_python() -> Path:
    """Return the path to the virtualenv python executable."""
    if sys.platform == "win32":
        return REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    return REPO_ROOT / ".venv" / "bin" / "python"


def ensure_venv_exists() -> Path:
    """Ensure the virtualenv exists and return the python executable path."""
    venv_python = get_venv_python()
    if not venv_python.exists():
        print(
            f"Error: virtual environment not found at {venv_python.parent.parent}", file=sys.stderr
        )
        print("Run: py tasks.py setup (or python tasks.py setup on Linux) first.", file=sys.stderr)
        sys.exit(1)
    return venv_python


def run_command(cmd: list[str]) -> int:
    """Run a subprocess command and propagate exit code."""
    result = subprocess.run(cmd, cwd=REPO_ROOT)
    return result.returncode


def cmd_setup(args: argparse.Namespace, extra_args: list[str]) -> int:
    """Set up the environment."""
    if sys.version_info[:2] != (3, 12):
        print("Run: py -3.12 tasks.py setup", file=sys.stderr)
        sys.exit(1)

    venv_dir = REPO_ROOT / ".venv"
    print(f"Creating virtual environment in {venv_dir}...")
    venv.create(venv_dir, with_pip=True)

    venv_python = get_venv_python()
    if not venv_python.exists():
        print(
            f"Error: Python executable not found at {venv_python} after venv creation.",
            file=sys.stderr,
        )
        return 1

    print("Upgrading pip...")
    rc = run_command([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"])
    if rc != 0:
        return rc

    req_dev = REPO_ROOT / "requirements-dev.txt"
    if req_dev.exists():
        print(f"Installing dependencies from {req_dev.name}...")
        rc = run_command([str(venv_python), "-m", "pip", "install", "-r", str(req_dev)])
        if rc != 0:
            return rc

    print("Installing package in editable mode...")
    rc = run_command([str(venv_python), "-m", "pip", "install", "-e", "."])
    return rc


def cmd_lint(args: argparse.Namespace, extra_args: list[str]) -> int:
    """Run ruff check and ruff format --check."""
    py = ensure_venv_exists()
    print("Running ruff check...")
    rc = run_command([str(py), "-m", "ruff", "check", "."] + extra_args)
    if rc != 0:
        return rc
    print("Running ruff format --check...")
    return run_command([str(py), "-m", "ruff", "format", "--check", "."] + extra_args)


def cmd_format(args: argparse.Namespace, extra_args: list[str]) -> int:
    """Run ruff format and ruff check --fix."""
    py = ensure_venv_exists()
    print("Running ruff format...")
    rc = run_command([str(py), "-m", "ruff", "format", "."] + extra_args)
    if rc != 0:
        return rc
    print("Running ruff check --fix...")
    return run_command([str(py), "-m", "ruff", "check", "--fix", "."] + extra_args)


def cmd_test(args: argparse.Namespace, extra_args: list[str]) -> int:
    """Run non-live unit tests with pytest."""
    py = ensure_venv_exists()
    cmd = [str(py), "-m", "pytest", "-m", "not live"] + extra_args
    return run_command(cmd)


def cmd_test_live(args: argparse.Namespace, extra_args: list[str]) -> int:
    """Run live tests with pytest."""
    py = ensure_venv_exists()
    cmd = [str(py), "-m", "pytest", "-m", "live"] + extra_args
    return run_command(cmd)


def should_skip_path(path: Path) -> bool:
    """Determine whether path should be skipped in repository tree."""
    name = path.name
    skip_names = {".git", ".venv", "__pycache__", ".ruff_cache", ".pytest_cache", "cache"}
    if name in skip_names:
        return True
    if fnmatch.fnmatch(name, "*.egg-info"):
        return True
    try:
        rel = path.relative_to(REPO_ROOT)
        if rel.as_posix() == "data/raw":
            return True
    except ValueError:
        pass
    return False


def cmd_tree(args: argparse.Namespace, extra_args: list[str]) -> int:
    """Print the repository tree (directories first, sorted)."""

    def walk_dir(directory: Path, prefix: str = "") -> None:
        entries = [e for e in directory.iterdir() if not should_skip_path(e)]
        dirs = sorted([e for e in entries if e.is_dir()], key=lambda p: p.name.lower())
        files = sorted([e for e in entries if not e.is_dir()], key=lambda p: p.name.lower())
        ordered = dirs + files

        for i, entry in enumerate(ordered):
            is_last = i == len(ordered) - 1
            connector = "└── " if is_last else "├── "
            sub_prefix = "    " if is_last else "│   "
            display_name = f"{entry.name}/" if entry.is_dir() else entry.name
            print(f"{prefix}{connector}{display_name}")
            if entry.is_dir():
                walk_dir(entry, prefix + sub_prefix)

    print(".")
    walk_dir(REPO_ROOT)
    return 0


def cmd_hash(args: argparse.Namespace, extra_args: list[str]) -> int:
    """Print sha256 checksum and path for specified files."""
    paths = args.paths + extra_args
    if not paths:
        print("Usage: py tasks.py hash PATH [PATH ...]", file=sys.stderr)
        return 1

    for path_str in paths:
        p = Path(path_str)
        if not p.is_file():
            print(f"Error: file not found: {path_str}", file=sys.stderr)
            return 1
        h = hashlib.sha256()
        with open(p, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        print(f"{h.hexdigest()}  {p.as_posix()}")
    return 0


def cmd_ingest(args: argparse.Namespace, extra_args: list[str]) -> int:
    print("Not implemented yet: added in module M02", file=sys.stderr)
    return 1


def cmd_index(args: argparse.Namespace, extra_args: list[str]) -> int:
    print("Not implemented yet: added in module M04", file=sys.stderr)
    return 1


def cmd_eval(args: argparse.Namespace, extra_args: list[str]) -> int:
    print("Not implemented yet: added in module M07", file=sys.stderr)
    return 1


def cmd_validate_eval(args: argparse.Namespace, extra_args: list[str]) -> int:
    print("Not implemented yet: added in module M03", file=sys.stderr)
    return 1


def cmd_dev(args: argparse.Namespace, extra_args: list[str]) -> int:
    py = ensure_venv_exists()
    cmd = [
        str(py),
        "-m",
        "uvicorn",
        "ragdocs.api.app:app",
        "--reload",
        "--port",
        "8000",
    ] + extra_args
    return run_command(cmd)


def cmd_bundle_check(args: argparse.Namespace, extra_args: list[str]) -> int:
    py = ensure_venv_exists()
    script = REPO_ROOT / "tools" / "bundle_size.py"
    cmd = [str(py), str(script), "--limit-mb", "400"] + extra_args
    return run_command(cmd)


def cmd_smoke(args: argparse.Namespace, extra_args: list[str]) -> int:
    print("Not implemented yet: added in module M12", file=sys.stderr)
    return 1


def main() -> int:
    argv = sys.argv[1:]
    extra_args = []
    if "--" in argv:
        split_idx = argv.index("--")
        extra_args = argv[split_idx + 1 :]
        argv = argv[:split_idx]

    parser = argparse.ArgumentParser(
        prog="tasks.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    subparsers.add_parser("setup", help="Set up virtualenv and install dependencies")
    subparsers.add_parser("lint", help="Run ruff check and format check")
    subparsers.add_parser("format", help="Run ruff format and fix lint issues")
    subparsers.add_parser("test", help="Run unit tests")
    subparsers.add_parser("test-live", help="Run live API tests")
    subparsers.add_parser("tree", help="Print repository tree")

    hash_parser = subparsers.add_parser("hash", help="Compute SHA-256 for files")
    hash_parser.add_argument("paths", nargs="*", help="File paths to hash")

    subparsers.add_parser("ingest", help="Ingest documentation")
    subparsers.add_parser("index", help="Build indexes")

    eval_parser = subparsers.add_parser("eval", help="Run pipeline evaluation")
    eval_parser.add_argument("--pipeline", required=False, help="Pipeline name")

    val_eval_parser = subparsers.add_parser("validate-eval", help="Validate evaluation set")
    val_eval_parser.add_argument(
        "--require-verified", action="store_true", help="Require verified flag"
    )

    subparsers.add_parser("dev", help="Run dev server")
    subparsers.add_parser("bundle-check", help="Check bundle size")

    smoke_parser = subparsers.add_parser("smoke", help="Run smoke tests")
    smoke_parser.add_argument("--url", required=False, help="Target URL")

    if not argv:
        parser.print_help()
        return 0

    args = parser.parse_args(argv)

    handlers = {
        "setup": cmd_setup,
        "lint": cmd_lint,
        "format": cmd_format,
        "test": cmd_test,
        "test-live": cmd_test_live,
        "tree": cmd_tree,
        "hash": cmd_hash,
        "ingest": cmd_ingest,
        "index": cmd_index,
        "eval": cmd_eval,
        "validate-eval": cmd_validate_eval,
        "dev": cmd_dev,
        "bundle-check": cmd_bundle_check,
        "smoke": cmd_smoke,
    }

    handler = handlers.get(args.command)
    if not handler:
        parser.print_help()
        return 1

    return handler(args, extra_args)


if __name__ == "__main__":
    sys.exit(main())
