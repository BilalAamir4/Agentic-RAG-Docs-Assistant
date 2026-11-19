"""Sync the LangSmith dataset and upload a run as an experiment (M09, D18). No LLM calls.

Usage:
    py tasks.py ls-dataset
    py tasks.py experiment --run-dir DIR [--replace]

Inputs: data/eval/eval_set.jsonl (hash and git tag checked, D15), the run folder's
stored files, LANGSMITH_API_KEY via Settings.
Outputs: dataset ragdocs-eval-set-v1 in LangSmith (created once, then verified); an
experiment named after the run folder (<run>-r<N> with --replace); the run folder's
append-only langsmith_experiment.json.
"""

import argparse
import sys
from pathlib import Path

from ragdocs.config import get_settings
from ragdocs.eval.langsmith_sync import make_client, sync_dataset, upload_experiment
from ragdocs.eval.runner import check_eval_set, load_eval_items


def main() -> int:
    """Run the ls-dataset or experiment subcommand."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ls-dataset")
    exp = sub.add_parser("experiment")
    exp.add_argument("--run-dir", type=Path, required=True)
    exp.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    sha = check_eval_set(settings)
    client = make_client(settings)
    dataset, created = sync_dataset(
        client, settings.langsmith_dataset_name, load_eval_items(settings), sha
    )
    state = "created" if created else "verified (same 50 ids and sha256)"
    print(f"Dataset {settings.langsmith_dataset_name} {state}: {dataset.id}")
    if args.command == "experiment":
        entry = upload_experiment(client, args.run_dir, dataset, replace=args.replace)
        print(f"Experiment {entry['name']} ({entry['examples']} examples): {entry['url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
