"""Tests verifying strict offline/online import boundaries for ragdocs.api.app."""

import json
import subprocess
import sys


def test_import_boundaries_api_app() -> None:
    """Ensure importing ragdocs.api.app does not import ingest, eval, or index.build modules."""
    script = (
        "import json, sys\n"
        "import ragdocs.api.app\n"
        "print(json.dumps(sorted(list(sys.modules.keys()))))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
    )

    imported_modules: list[str] = json.loads(result.stdout)
    forbidden_prefixes = (
        "ragdocs.ingest",
        "ragdocs.eval",
        "ragdocs.index.build",
    )

    for mod in imported_modules:
        for prefix in forbidden_prefixes:
            assert not mod.startswith(prefix), (
                f"Boundary violation: importing ragdocs.api.app imported '{mod}'"
            )
