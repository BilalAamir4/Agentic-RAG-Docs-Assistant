"""Export the agentic graphs as Mermaid files under docs/graphs/ (offline, no API calls).

Usage:
    .venv\\Scripts\\python scripts\\export_graphs.py

Inputs: the graph definitions in ragdocs.pipelines.agentic.graph.
Outputs: docs/graphs/corrective.mmd (M11 adds self_rag).
"""

from ragdocs.config import REPO_ROOT
from ragdocs.io_utils import write_text
from ragdocs.pipelines.agentic.graph import export_mermaid

GRAPHS_DIR = REPO_ROOT / "docs" / "graphs"
EXPORTED_MODES = ("corrective",)


def main() -> None:
    """Write one .mmd file per implemented agentic mode."""
    for mode in EXPORTED_MODES:
        path = GRAPHS_DIR / f"{mode}.mmd"
        write_text(path, export_mermaid(mode))
        print(f"Wrote {path.relative_to(REPO_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
