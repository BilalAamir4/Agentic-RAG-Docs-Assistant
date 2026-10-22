"""BM25 sparse search index and custom code/text tokenizer."""

import json
import re
from pathlib import Path
from typing import Self

from rank_bm25 import BM25Okapi

ENGLISH_STOPWORDS: frozenset[str] = frozenset(
    [
        "a",
        "about",
        "all",
        "an",
        "and",
        "any",
        "are",
        "as",
        "at",
        "be",
        "been",
        "being",
        "but",
        "by",
        "can",
        "do",
        "does",
        "each",
        "for",
        "from",
        "has",
        "have",
        "he",
        "her",
        "his",
        "how",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "no",
        "not",
        "of",
        "on",
        "or",
        "so",
        "that",
        "the",
        "their",
        "then",
        "there",
        "this",
        "to",
        "was",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "will",
        "with",
    ]
)


def tokenize(text: str) -> list[str]:
    """Tokenize text with snake_case and camelCase splitting, filtering stopwords and length 1."""
    camel_parts: list[str] = []
    original_words = re.findall(r"[A-Za-z0-9_]+", text)
    for word in original_words:
        s1 = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", word)
        s2 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s1)
        if " " in s2:
            for part in s2.split():
                clean_part = part.strip("_").lower()
                if clean_part:
                    camel_parts.append(clean_part)

    raw_tokens = re.findall(r"[a-z0-9_]+", text.lower())
    tokens: list[str] = []
    for token in raw_tokens:
        tokens.append(token)
        if "_" in token:
            for sub_part in token.split("_"):
                if sub_part:
                    tokens.append(sub_part)

    tokens.extend(camel_parts)
    return [t for t in tokens if len(t) > 1 and t not in ENGLISH_STOPWORDS]


class BM25Index:
    """In-memory BM25 index over pre-tokenized documents."""

    def __init__(self, bm25: BM25Okapi, tokens: list[list[str]]) -> None:
        self.bm25 = bm25
        self.tokens = tokens

    @classmethod
    def load(cls, path: Path | str) -> Self:
        """Load stored tokens from JSON file and initialize BM25Okapi."""
        p = Path(path)
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        tokens: list[list[str]] = data["tokens"]
        bm25 = BM25Okapi(tokens)
        return cls(bm25=bm25, tokens=tokens)

    def search(self, query: str, k: int) -> list[tuple[int, float]]:
        """Search index and return (row, score) pairs sorted descending, excluding zero scores."""
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        scores = self.bm25.get_scores(query_tokens)
        scored_rows = [(idx, float(score)) for idx, score in enumerate(scores) if score > 0.0]
        scored_rows.sort(key=lambda item: item[1], reverse=True)
        return scored_rows[:k]
