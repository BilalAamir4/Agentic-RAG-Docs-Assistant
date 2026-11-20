"""Mapping between corpus doc paths and public docs.langchain.com URLs (M10).

Runtime-safe: imports only the standard library, ragdocs.config, ragdocs.io_utils and
ragdocs.schemas, never ragdocs.ingest or ragdocs.eval. ragdocs.ingest builds every
chunk URL with doc_path_to_url and chunk_url, so url_to_doc_ref is their inverse.

URL scheme (moved unchanged from ingest/parse.py and ingest/chunk.py in M10):
    page URL  = DOCS_BASE_URL + "/" + doc_path without its extension (.mdx or .md)
    chunk URL = page URL + "#" + anchor, or the page URL when the anchor is ""
"""

from collections.abc import Collection
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from ragdocs.config import get_settings
from ragdocs.io_utils import read_jsonl
from ragdocs.schemas import Evidence

# Public base URL of the ingested docs root (was scripts/ingest.py DEFAULT_BASE_URL).
DOCS_BASE_URL = "https://docs.langchain.com/oss/python/langgraph"
CHUNK_META_FILE = "chunk_meta.jsonl"
# Extensions tried, in order, when resolving a URL path back to a doc_path.
DOC_EXTENSIONS = (".mdx", ".md")


def doc_path_to_url(doc_path: str, base_url: str = DOCS_BASE_URL) -> str:
    """Return the public page URL of a repository-relative doc path (posix form)."""
    doc_stem = doc_path.rsplit(".", 1)[0]
    return f"{base_url.rstrip('/')}/{doc_stem}"


def chunk_url(page_url: str, anchor: str) -> str:
    """Return the chunk URL: the page URL plus '#anchor', or the page URL for no anchor."""
    return f"{page_url}#{anchor}" if anchor else page_url


def doc_ref_to_url(ref: Evidence, base_url: str = DOCS_BASE_URL) -> str:
    """Return the chunk URL of an Evidence (doc_path, anchor) reference."""
    return chunk_url(doc_path_to_url(ref.doc_path, base_url), ref.anchor)


def is_docs_host(url: str, domain: str) -> bool:
    """True when the URL's host is domain or a subdomain of it (case-insensitive)."""
    host = (urlsplit(url).hostname or "").lower()
    domain = domain.lower()
    return bool(host) and (host == domain or host.endswith("." + domain))


@lru_cache
def known_doc_paths(index_dir: Path | None = None) -> frozenset[str]:
    """Doc paths present in <index_dir>/chunk_meta.jsonl (default Settings.index_dir)."""
    path = Path(index_dir or get_settings().index_dir) / CHUNK_META_FILE
    return frozenset(row["doc_path"] for row in read_jsonl(path))


def url_to_doc_ref(
    url: str,
    doc_paths: Collection[str] | None = None,
    base_url: str = DOCS_BASE_URL,
) -> Evidence | None:
    """Return the (doc_path, anchor) of a docs URL, or None when it does not map.

    The anchor is the URL fragment ("" when there is none); the query string is
    ignored. None is returned for a host other than Settings.docs_domain, a path
    outside base_url, or a page not in doc_paths (default: the index's doc paths).
    """
    parts = urlsplit(url.strip())
    base = urlsplit(base_url)
    host = (parts.hostname or "").lower()
    if host != get_settings().docs_domain.lower() or host != (base.hostname or "").lower():
        return None
    prefix = base.path.rstrip("/") + "/"
    path = parts.path.rstrip("/")
    if not path.startswith(prefix) or len(path) == len(prefix):
        return None
    stem = path[len(prefix) :]
    known = known_doc_paths() if doc_paths is None else doc_paths
    for ext in DOC_EXTENSIONS:
        if stem + ext in known:
            return Evidence(doc_path=stem + ext, anchor=parts.fragment)
    return None
