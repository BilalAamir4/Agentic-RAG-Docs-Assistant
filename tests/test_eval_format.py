"""ragdocs.eval.format gives what web/src/lib/format.ts gives (cases from format.test.ts)."""

from ragdocs.eval.format import (
    fmt_calls,
    fmt_mean,
    fmt_ms_as_s,
    fmt_percent,
    fmt_rate,
    fmt_tokens,
    to_fixed,
)


def test_rate() -> None:
    assert fmt_rate(38, 42) == "90.5% (38/42)"
    assert fmt_rate(0, 8) == "0.0% (0/8)"
    assert fmt_rate(8, 8) == "100.0% (8/8)"
    assert fmt_rate(34.0, 42) == "81.0% (34/42)"


def test_percent_edges() -> None:
    assert fmt_percent(0) == "0.0%"
    assert fmt_percent(1) == "100.0%"
    assert fmt_percent(0.995) == "99.5%"
    assert fmt_percent(0.9999) == "100.0%"


def test_mean_calls_tokens_seconds() -> None:
    assert fmt_mean(0.9218917, 39) == "0.92 (n=39)"
    assert fmt_mean(0, 3) == "0.00 (n=3)"
    assert fmt_mean(1, 3) == "1.00 (n=3)"
    assert fmt_calls(2.32) == "2.3"
    assert fmt_calls(1) == "1.0"
    assert fmt_tokens(2333.56) == "2,334"
    assert fmt_tokens(999.4) == "999"
    assert fmt_tokens(1234567) == "1,234,567"
    assert fmt_tokens(0) == "0"
    assert fmt_ms_as_s(2207.5) == "2.2 s"
    assert fmt_ms_as_s(0) == "0.0 s"
    assert fmt_ms_as_s(49) == "0.0 s"


def test_none_is_not_available() -> None:
    assert fmt_rate(None, 0) == "n/a"
    assert fmt_rate(3, 0) == "n/a"
    assert fmt_mean(None, 0) == "n/a"
    assert fmt_calls(None) == "n/a"
    assert fmt_tokens(None) == "n/a"
    assert fmt_ms_as_s(None) == "n/a"


def test_ties_round_up_like_javascript() -> None:
    """Exact binary ties: JavaScript rounds up, Python's format rounds to even."""
    assert to_fixed(0.125, 2) == "0.13"
    assert fmt_ms_as_s(2250) == "2.3 s"
    assert fmt_tokens(2.5) == "3"
    assert fmt_tokens(0.5) == "1"
