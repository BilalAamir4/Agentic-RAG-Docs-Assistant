"""Bundle size calculation utility for Linux wheel deployment packages.

Purpose:
  Downloads manylinux2014_x86_64 prebuilt wheels for runtime requirements,
  simulates the deployment bundle layout with application source and index,
  calculates uncompressed size, and validates against the size threshold.

Inputs:
  - requirements.txt at repository root
  - src/ directory at repository root
  - data/index/ directory at repository root
  - --limit-mb CLI argument (default: 400.0)

Outputs:
  - Prints total bundle size in MB
  - Prints table of the 15 largest installed packages
  - Exit 0: Total size is within limit
  - Exit 1: Total size exceeds --limit-mb
  - Exit 2: One or more requirements lack Linux prebuilt binary wheels
"""

import argparse
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _onexc_remove_readonly(func, path, exc_info):
    """Clear write protection on Windows read-only files during rmtree cleanup."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def _extract_missing_wheel_package(output: str) -> str | None:
    """Extract package name from pip error message when wheel is missing."""
    match = re.search(
        r"Could not find a version that satisfies the requirement\s+([a-zA-Z0-9_\-\.]+)",
        output,
    )
    if match:
        return match.group(1)
    match = re.search(
        r"No matching distribution found for\s+([a-zA-Z0-9_\-\.]+)",
        output,
    )
    if match:
        return match.group(1)
    return None


def calculate_bundle_size(limit_mb: float) -> int:
    """Measure Linux-wheel deployment bundle size in a temporary directory."""
    req_file = REPO_ROOT / "requirements.txt"
    src_dir = REPO_ROOT / "src"
    index_dir = REPO_ROOT / "data" / "index"

    if not req_file.is_file():
        print(f"Error: requirements.txt not found at {req_file}", file=sys.stderr)
        return 1

    tmp_dir = Path(tempfile.mkdtemp(prefix="ragdocs-bundle-"))
    site_dir = tmp_dir / "site"
    site_dir.mkdir(parents=True, exist_ok=True)

    try:
        pip_cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--target",
            str(site_dir),
            "--platform",
            "manylinux2014_x86_64",
            "--platform",
            "manylinux_2_28_x86_64",
            "--python-version",
            "3.12",
            "--implementation",
            "cp",
            "--only-binary=:all:",
            "-r",
            str(req_file),
        ]

        result = subprocess.run(
            pip_cmd,
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )

        if result.returncode != 0:
            combined_output = f"{result.stdout}\n{result.stderr}"
            missing_pkg = _extract_missing_wheel_package(combined_output)
            pkg_name = missing_pkg if missing_pkg else "unknown package"
            print(
                f"Error: No Linux wheel available for requirement: {pkg_name}",
                file=sys.stderr,
            )
            print(result.stderr, file=sys.stderr)
            return 2

        # Copy src/ and data/index/
        if src_dir.is_dir():
            shutil.copytree(src_dir, tmp_dir / "src")
        if index_dir.is_dir():
            shutil.copytree(index_dir, tmp_dir / "data" / "index")

        # Measure package sizes in site/
        pkg_sizes: list[tuple[str, float]] = []
        for entry in site_dir.iterdir():
            if entry.is_dir():
                bytes_sum = sum(f.stat().st_size for f in entry.rglob("*") if f.is_file())
            else:
                bytes_sum = entry.stat().st_size
            pkg_sizes.append((entry.name, bytes_sum / (1024 * 1024)))

        # Total size of the bundle
        total_bytes = sum(f.stat().st_size for f in tmp_dir.rglob("*") if f.is_file())
        total_mb = total_bytes / (1024 * 1024)

        print(f"Total bundle size: {total_mb:.2f} MB (limit: {limit_mb:.2f} MB)")
        print("\n15 largest installed items:")
        sorted_pkgs = sorted(pkg_sizes, key=lambda x: x[1], reverse=True)[:15]
        for name, size_mb in sorted_pkgs:
            print(f"  - {name:<35} {size_mb:6.2f} MB")

        if total_mb > limit_mb:
            print(
                f"\nError: Bundle size {total_mb:.2f} MB exceeds limit {limit_mb:.2f} MB",
                file=sys.stderr,
            )
            return 1

        return 0

    finally:
        shutil.rmtree(tmp_dir, onexc=_onexc_remove_readonly)


def main() -> int:
    """Parse CLI options and run bundle size verification."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit-mb",
        type=float,
        default=400.0,
        help="Maximum allowed bundle size in megabytes (default: 400.0)",
    )
    args = parser.parse_args()
    return calculate_bundle_size(limit_mb=args.limit_mb)


if __name__ == "__main__":
    sys.exit(main())
