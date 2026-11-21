"""The corrective graph drawn from build_graph with fake deps equals docs/graphs/corrective.mmd.

Added in M11 S2 before graph.py changed, so the self_rag work cannot alter the
corrective graph's shape (byte for byte, including the trailing newline).
"""

from agentic_fakes import FakeRetriever, Harness, chunks, grades

from ragdocs.config import REPO_ROOT
from ragdocs.pipelines.agentic.graph import build_graph


def test_corrective_mermaid_from_fake_deps_matches_committed_file_byte_for_byte() -> None:
    deps = Harness(FakeRetriever(chunks(1)), grader=[grades(True)]).deps
    drawn = build_graph("corrective", deps).get_graph().draw_mermaid()
    committed = (REPO_ROOT / "docs" / "graphs" / "corrective.mmd").read_bytes()
    assert (drawn.rstrip("\n") + "\n").encode("utf-8") == committed
