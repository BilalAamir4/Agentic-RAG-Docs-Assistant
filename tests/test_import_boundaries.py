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


def test_import_boundaries_llm_module() -> None:
    """Ensure ragdocs.providers.llm does not import langchain_google_genai at module level."""
    script = (
        "import json, sys\n"
        "import ragdocs.providers.llm\n"
        "print(json.dumps(sorted(list(sys.modules.keys()))))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
    )

    imported_modules: list[str] = json.loads(result.stdout)
    assert "langchain_google_genai" not in imported_modules, (
        "Boundary violation: importing ragdocs.providers.llm imported "
        "langchain_google_genai at module level"
    )
