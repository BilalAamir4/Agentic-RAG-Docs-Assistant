"""Print each model's daily-window usage and remaining requests and tokens (D7).

Usage:
    .venv\\Scripts\\python scripts\\budget.py [--need MODEL=TOKENS[:REQUESTS] ...]

Reads cache/budget.json (written by the BudgetRecorder for every live call) and the
limits in Settings. Groq models use a rolling 24-hour window; Gemini models use the
calendar day in America/Los_Angeles. "free" is limit - used; "free@0.9" is
limit x throttle_safety - used, which is what the eval and judge runners enforce.
With --need, exits 1 if any listed need does not fit in free@0.9.

Inputs: cache/budget.json, Settings. Output: a table on stdout; exit code 0 or 1.
"""

import argparse
import sys
from datetime import UTC

from ragdocs.config import get_settings
from ragdocs.eval.throttle import RollingBudget, all_budgets, default_store


def parse_need(text: str) -> tuple[str, int, int]:
    """Parse MODEL=TOKENS[:REQUESTS] into (model, tokens, requests)."""
    model, _, amount = text.rpartition("=")
    if not model:
        raise argparse.ArgumentTypeError(f"expected MODEL=TOKENS[:REQUESTS], got {text!r}")
    tokens, _, requests = amount.partition(":")
    return model, int(tokens), int(requests or 0)


def describe(budget: RollingBudget) -> dict[str, object]:
    """Return one table row for a budget."""
    requests, tokens = budget.daily_used()
    req_cap, tok_cap = budget.daily_caps()
    tpd = budget.tokens_per_day
    return {
        "model": budget.model,
        "window": budget.daily_window,
        "requests": f"{requests}/{budget.requests_per_day}",
        "req free": budget.requests_per_day - requests,
        "req free@0.9": int(req_cap - requests),
        "tokens": f"{tokens:,}/{tpd:,}" if tpd else f"{tokens:,}/-",
        "tok free": f"{tpd - tokens:,}" if tpd else "-",
        "tok free@0.9": f"{int(tok_cap - tokens):,}" if tok_cap else "-",
    }


def fits(budget: RollingBudget, tokens: int, requests: int) -> bool:
    """True when tokens and requests fit in the budget's daily caps now."""
    used_req, used_tok = budget.daily_used()
    req_cap, tok_cap = budget.daily_caps()
    return used_req + requests <= req_cap and (tok_cap is None or used_tok + tokens <= tok_cap)


def print_table(rows: list[dict[str, object]]) -> None:
    """Print rows as aligned columns."""
    cols = list(rows[0])
    widths = {c: max(len(c), *(len(str(r[c])) for r in rows)) for c in cols}
    print("  ".join(c.ljust(widths[c]) for c in cols))
    for r in rows:
        print("  ".join(str(r[c]).ljust(widths[c]) for c in cols))


def main() -> int:
    """Print the table and check --need entries."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--need", type=parse_need, action="append", default=[])
    args = parser.parse_args()
    settings = get_settings()
    budgets = all_budgets(settings, default_store(settings))
    print_table([describe(b) for b in budgets.values()])
    status = 0
    for model, tokens, requests in args.need:
        budget = budgets.get(model)
        if budget is None:
            print(f"NEED {model}: unknown model (known: {', '.join(budgets)})")
            status = 1
        elif fits(budget, tokens, requests):
            print(f"NEED {model}: {tokens:,} tokens, {requests} requests: fits")
        else:
            at = budget.resets_at(tokens, requests).astimezone(UTC).isoformat(timespec="minutes")
            print(
                f"NEED {model}: {tokens:,} tokens, {requests} requests: DOES NOT FIT; fits at {at}"
            )
            status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
