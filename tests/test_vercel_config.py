"""vercel.json: header rules, and the functions and rewrites unchanged since M13 (04b903a)."""

import json
from pathlib import Path
from typing import Any

from ragdocs.api.local import CSP

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG: dict[str, Any] = json.loads((REPO_ROOT / "vercel.json").read_text(encoding="utf-8"))

# Content of vercel.json at 04b903a.
FUNCTIONS = {
    "api/index.py": {
        "maxDuration": 60,
        "includeFiles": "{src/**,data/index/**,requirements.txt}",
    }
}
REWRITES = [{"source": "/api/(.*)", "destination": "/api/index"}]

HEADERS = [
    {
        "source": "/(.*)",
        "headers": [
            {"key": "Content-Security-Policy", "value": CSP},
            {"key": "X-Content-Type-Options", "value": "nosniff"},
            {"key": "Referrer-Policy", "value": "strict-origin-when-cross-origin"},
            {"key": "Permissions-Policy", "value": "camera=(), microphone=(), geolocation=()"},
        ],
    },
    {
        "source": "/assets/(.*)",
        "headers": [{"key": "Cache-Control", "value": "public, max-age=31536000, immutable"}],
    },
    {"source": "/", "headers": [{"key": "Cache-Control", "value": "no-cache"}]},
    {"source": "/index.html", "headers": [{"key": "Cache-Control", "value": "no-cache"}]},
    {
        "source": "/results.json",
        "headers": [{"key": "Cache-Control", "value": "public, max-age=300"}],
    },
]


def test_header_rules_are_exact() -> None:
    """The header rules equal the M14 spec, with the CSP taken from local.py."""
    assert CONFIG["headers"] == HEADERS


def test_functions_and_rewrites_unchanged() -> None:
    """functions and rewrites are what they were at 04b903a."""
    assert CONFIG["functions"] == FUNCTIONS
    assert CONFIG["rewrites"] == REWRITES


def test_no_cache_control_rule_matches_api() -> None:
    """No Cache-Control rule can match /api/ (the function sets its own)."""
    for rule in CONFIG["headers"]:
        keys = {h["key"] for h in rule["headers"]}
        if "Cache-Control" in keys:
            assert not rule["source"].startswith("/api")
            assert rule["source"] != "/(.*)"


def test_no_two_rules_set_the_same_header_on_one_path() -> None:
    """Cache-Control rules are disjoint, so header precedence between rules never applies."""
    sources = [r["source"] for r in CONFIG["headers"] if r["headers"][0]["key"] == "Cache-Control"]
    assert len(sources) == len(set(sources))
    catch_all = next(r for r in CONFIG["headers"] if r["source"] == "/(.*)")
    assert "Cache-Control" not in {h["key"] for h in catch_all["headers"]}


def test_only_hashed_assets_get_immutable_cache() -> None:
    """Every file under public/assets/ has a content hash in its name."""
    assets = [p for p in (REPO_ROOT / "public" / "assets").iterdir() if p.is_file()]
    assert assets
    for path in assets:
        assert path.stem.rsplit("-", 1)[-1].isalnum() and "-" in path.stem, path.name
