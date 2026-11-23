"""Text formatters that match web/src/lib/format.ts exactly (M15, offline).

The README results block and the web page must show the same string for the same value.
JavaScript's toFixed and Math.round round exact ties up (0.125.toFixed(2) is "0.13",
Math.round(2.5) is 3) while Python's format and round round ties to even, so the
rounding here goes through Decimal to reproduce the JavaScript results. A missing value
(None) gives "n/a".
"""

from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal

NOT_AVAILABLE = "n/a"
MS_PER_S = 1000
PERCENT = 100


def to_fixed(value: float, digits: int) -> str:
    """JavaScript Number.prototype.toFixed for a finite number."""
    quantum = Decimal(1).scaleb(-digits)
    text = f"{Decimal(value).quantize(quantum, rounding=ROUND_HALF_UP):f}"
    return text[1:] if text.startswith("-") and float(text) == 0 else text


def fmt_percent(fraction: float) -> str:
    """A 0 to 1 fraction as a percent with one decimal, for example "90.5%"."""
    return f"{to_fixed(fraction * PERCENT, 1)}%"


def fmt_rate(count: float | None, n: int) -> str:
    """Rate as "90.5% (38/42)"; "n/a" when count is None or n is 0."""
    if count is None or not n:
        return NOT_AVAILABLE
    shown = int(count) if float(count).is_integer() else count
    return f"{fmt_percent(count / n)} ({shown}/{n})"


def fmt_mean(value: float | None, n: int) -> str:
    """Mean as "0.87 (n=40)" with two decimals; "n/a" when value is None."""
    if value is None:
        return NOT_AVAILABLE
    return f"{to_fixed(value, 2)} (n={n})"


def fmt_calls(value: float | None) -> str:
    """Mean LLM calls with one decimal."""
    return NOT_AVAILABLE if value is None else to_fixed(value, 1)


def fmt_tokens(value: float | None) -> str:
    """Tokens rounded half up, with comma thousands separators."""
    if value is None:
        return NOT_AVAILABLE
    rounded = (Decimal(value) + Decimal("0.5")).to_integral_value(rounding=ROUND_FLOOR)
    return f"{int(rounded):,}"


def fmt_ms_as_s(value: float | None) -> str:
    """Milliseconds as seconds with one decimal, "2.2 s"."""
    return NOT_AVAILABLE if value is None else f"{to_fixed(value / MS_PER_S, 1)} s"
