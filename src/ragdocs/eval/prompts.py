"""Prompts for the offline evaluation judge (M08).

JUDGE_PROMPT is versioned by Settings.judge_prompt_version. Any change needs a version
bump and a re-judge (judge_v<N>.jsonl), see docs/DECISIONS.md D9.
"""

from ragdocs.schemas import JUDGE_RATIONALE_MAX_WORDS

JUDGE_PROMPT = f"""You grade answers produced by a documentation assistant for LangGraph (Python). You are given the question, a reference answer written by a human expert, a list of identifiers the answer is expected to mention (a soft signal only), the assistant's answer, and every documentation excerpt the assistant saw. Each excerpt is numbered in the order the assistant saw it and marked CITED if the assistant cited it, or NOT CITED otherwise.

Before scoring, work through these steps:
1. List the answer's key claims.
2. Check each claim against the reference answer.
3. Check each claim against the CITED excerpts.
Then score.

correctness (0, 1 or 2):
- 2 = agrees with the reference answer on every key fact and uses the right API names;
- 1 = partly correct or incomplete, but nothing contradicts the reference;
- 0 = wrong, contradicts the reference, or uses an outdated or invented API.

citation_support (0 or 1):
- 1 = every cited excerpt supports at least one claim in the answer AND no central claim lacks a cited excerpt;
- 0 otherwise.

Judge correctness against the reference answer, not against your own knowledge of LangGraph. A missing must_mention identifier is a hint that the answer may be incomplete, not an automatic penalty. Judge citation_support using only the CITED excerpts; NOT CITED excerpts never count as support.

Return only the structured fields: correctness, citation_support, and rationale (at most {JUDGE_RATIONALE_MAX_WORDS} words, naming the claims that decided the scores)."""  # noqa: E501

JUDGE_USER_TEMPLATE = """Question:
{question}

Reference answer:
{reference_answer}

must_mention (soft signal):
{must_mention}

Assistant answer:
{answer}

Excerpts the assistant saw, in order:
{excerpts}"""

JUDGE_EXCERPT_TEMPLATE = "[{n}] {flag} {header} ({url})\n{text}"
