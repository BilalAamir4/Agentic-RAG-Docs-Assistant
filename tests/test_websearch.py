"""Tests for ragdocs.providers.websearch.TavilySearch with a fake client (no network)."""

import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from eval_fakes import make_settings
from tavily import InvalidAPIKeyError, UsageLimitExceededError

from ragdocs.providers.websearch import TavilySearch, WebSearchAuthError, WebSearchError

FAKE_KEY = "tvly-SECRET-test-key-123"


class HTTPStatusError(OSError):
    """Stand-in for requests.HTTPError (an OSError subclass with .response)."""

    def __init__(self, status: int) -> None:
        super().__init__(f"{status} Server Error")
        self.response = SimpleNamespace(status_code=status)


class FakeTavily:
    """Records search calls; raises the queued errors first, then returns results."""

    def __init__(self, results: list[dict[str, Any]], errors: list[Exception] | None = None):
        self.results = results
        self.errors = list(errors or [])
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def search(self, query: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append((query, kwargs))
        if self.errors:
            raise self.errors.pop(0)
        return {"query": query, "results": self.results}


def _result(url: str) -> dict[str, Any]:
    return {"url": url, "title": "T", "content": "C", "score": 0.9, "raw_content": None}


def _search(
    tmp_path: Path, fake: FakeTavily, **overrides: Any
) -> tuple[TavilySearch, list[float], list[str]]:
    settings = make_settings(tmp_path, tavily_api_key=FAKE_KEY, **overrides)
    sleeps: list[float] = []
    keys: list[str] = []

    def factory(key: str) -> FakeTavily:
        keys.append(key)
        return fake

    return TavilySearch(settings, client_factory=factory, sleep=sleeps.append), sleeps, keys


def test_passes_domain_max_results_and_depth(tmp_path: Path) -> None:
    fake = FakeTavily([_result("https://docs.langchain.com/oss/python/langgraph/x")])
    ws, _, keys = _search(tmp_path, fake, web_max_results=4)
    out = ws.search("q")
    assert keys == [FAKE_KEY]
    assert fake.calls == [
        (
            "q",
            {"include_domains": ["docs.langchain.com"], "max_results": 4, "search_depth": "basic"},
        )
    ]
    assert out == [
        {"url": "https://docs.langchain.com/oss/python/langgraph/x", "title": "T", "content": "C"}
    ]


@pytest.mark.parametrize("first", [UsageLimitExceededError("slow down"), HTTPStatusError(503)])
def test_retries_429_and_5xx_then_succeeds(tmp_path: Path, first: Exception) -> None:
    fake = FakeTavily(
        [_result("https://docs.langchain.com/a")], errors=[first, HTTPStatusError(500)]
    )
    ws, sleeps, _ = _search(tmp_path, fake)
    assert len(ws.search("q")) == 1
    assert len(fake.calls) == 3 and sleeps == [1.0, 2.0]


def test_gives_up_after_three_attempts(tmp_path: Path) -> None:
    fake = FakeTavily([], errors=[UsageLimitExceededError("x")] * 3)
    ws, sleeps, _ = _search(tmp_path, fake)
    with pytest.raises(WebSearchError, match="after 3 attempt"):
        ws.search("q")
    assert sleeps == [1.0, 2.0]


def test_does_not_retry_4xx(tmp_path: Path) -> None:
    fake = FakeTavily([], errors=[HTTPStatusError(404)])
    ws, sleeps, _ = _search(tmp_path, fake)
    with pytest.raises(WebSearchError):
        ws.search("q")
    assert len(fake.calls) == 1 and sleeps == []


def test_auth_error_names_env_var_without_key(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    fake = FakeTavily([], errors=[InvalidAPIKeyError(f"bad key {FAKE_KEY}")])
    ws, sleeps, _ = _search(tmp_path, fake)
    caplog.set_level(logging.DEBUG)
    with pytest.raises(WebSearchAuthError) as info:
        ws.search("q")
    assert "TAVILY_API_KEY" in str(info.value)
    assert FAKE_KEY not in str(info.value) and info.value.__cause__ is None
    assert FAKE_KEY not in caplog.text and sleeps == []


def test_missing_key_fails_at_construction(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, tavily_api_key=None)
    with pytest.raises(RuntimeError, match="TAVILY_API_KEY"):
        TavilySearch(settings, client_factory=lambda key: FakeTavily([]))


def test_drops_off_domain_results(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    urls = [
        "https://docs.langchain.com/oss/python/langgraph/a",
        "https://evil.example.com/docs.langchain.com",
        "https://sub.docs.langchain.com/b",
    ]
    ws, _, _ = _search(tmp_path, FakeTavily([_result(u) for u in urls]))
    caplog.set_level(logging.WARNING)
    outcome = ws.search_with_diagnostics("q")
    assert [r.url for r in outcome.results] == [urls[0], urls[2]]
    assert outcome.dropped_off_domain == [urls[1]] and outcome.raw_urls == urls
    assert "Dropped 1 off-domain" in caplog.text
    assert [r["url"] for r in ws.search("q")] == [urls[0], urls[2]]
