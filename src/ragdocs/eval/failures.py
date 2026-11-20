"""Failed-attempt kinds for eval runs (M11 S1; offline, used by runner and report).

Each failed attempt has a kind (ragdocs.providers.errors.ErrorKind). New runs store it in
FailedAttempt.kind, from the error event's data["error_kind"] (agentic pipelines) or from
the message (baseline). Older stored attempts have no kind and are classified from the
message with classify_message; a message that does not identify a kind on its own is
"unclassified".

A kind that a stored message cannot show can be set by an evidence-backed override in
<results_dir>/<Settings.error_reclassifications_file>. The report applies overrides
after message classification and footnotes every summary that uses one. A missing file
means no overrides. Run folders are never rewritten.
"""

from collections.abc import Sequence
from pathlib import Path

from ragdocs.config import Settings
from ragdocs.io_utils import read_json
from ragdocs.providers.errors import ERROR_KINDS, ErrorKind, classify_message
from ragdocs.schemas import ErrorReclassification, FailedAttempt

# ItemScores field and summary key per kind.
KIND_FIELDS: dict[str, str] = {
    "structured_output": "structured_output_failures",
    "rate_limit": "rate_limited_attempts",
    "transient": "transient_call_errors",
    "permanent": "permanent_call_errors",
    "unclassified": "unclassified_call_errors",
}


def attempt_kind(attempt: FailedAttempt, rate_limit_prefixes: Sequence[str]) -> ErrorKind:
    """The stored kind when valid, else the kind classified from the message."""
    if attempt.kind in ERROR_KINDS:
        return attempt.kind  # type: ignore[return-value]
    return classify_message(attempt.message, rate_limit_prefixes)


def count_kinds(kinds: Sequence[str]) -> dict[str, int]:
    """{ItemScores field: count} for every kind (zeros included)."""
    return {field: sum(1 for k in kinds if k == kind) for kind, field in KIND_FIELDS.items()}


def overrides_path(settings: Settings) -> Path:
    """Location of the override file."""
    return Path(settings.results_dir) / settings.error_reclassifications_file


def load_overrides(path: Path) -> list[ErrorReclassification]:
    """Overrides from the file at path; [] when it does not exist."""
    if not path.is_file():
        return []
    return [ErrorReclassification.model_validate(o) for o in read_json(path)["overrides"]]


def overrides_for_run(
    overrides: Sequence[ErrorReclassification], run_dir: Path
) -> list[ErrorReclassification]:
    """Overrides whose run folder name equals run_dir's name."""
    return [o for o in overrides if Path(o.run).name == Path(run_dir).name]


def _matches(override: ErrorReclassification, item_id: str, attempt: FailedAttempt) -> bool:
    return override.item == item_id and (override.utc is None or override.utc == attempt.utc)


def item_kinds(
    item_id: str,
    attempts: Sequence[FailedAttempt],
    rate_limit_prefixes: Sequence[str],
    overrides: Sequence[ErrorReclassification] = (),
) -> tuple[list[str], list[ErrorReclassification]]:
    """Kind of each failed attempt of one item, and the overrides that were applied."""
    kinds: list[str] = []
    applied: list[ErrorReclassification] = []
    for attempt in attempts:
        kind: str = attempt_kind(attempt, rate_limit_prefixes)
        match = next((o for o in overrides if _matches(o, item_id, attempt)), None)
        if match is not None:
            kind = match.kind
            applied.append(match)
        kinds.append(kind)
    return kinds, applied
