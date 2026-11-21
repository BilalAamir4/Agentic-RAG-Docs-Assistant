"""Prompts for the corrective RAG grader and rewriter (M10) and the self-RAG nodes (M11).

The answer prompt is shared with the baseline and lives in ragdocs.generation.prompts.
"""

GRADE_SYSTEM_PROMPT = "You judge whether documentation excerpts are relevant to a developer's question about LangGraph (Python). An excerpt is relevant if it contains information that would help answer the question, even partially. It is not relevant if it only shares keywords with the question or covers a different feature. Grade every excerpt independently. Return one grade per excerpt number, each with a reason of at most 15 words."  # noqa: E501

GRADE_USER_TEMPLATE = "Question: {question}\n\nExcerpts:\n{context}"

REWRITE_SYSTEM_PROMPT = "You rewrite a developer's question into a search query for the LangGraph Python documentation. The previous search returned no relevant excerpts. Write one query of at most 20 words that names the LangGraph concepts, classes or functions the answer most likely involves, using the documentation's own terminology. Do not answer the question."  # noqa: E501

REWRITE_USER_TEMPLATE = "Question: {question}\nPrevious query: {query}\nHeadings returned by the previous search, all judged not relevant:\n{headings}"  # noqa: E501

# Self-RAG (M11). Exact text given in the M11 S2 module prompt; do not tune on results.
DECIDE_SYSTEM_PROMPT = "You route questions for a LangGraph (Python) documentation assistant. Set needs_docs to true if the question asks about LangGraph, LangChain, building agents or graphs, or any programming task that LangGraph documentation could address. Set needs_docs to false only for greetings, small talk, or requests clearly unrelated to software development. When unsure, set needs_docs to true."  # noqa: E501

DECIDE_USER_TEMPLATE = "Question: {question}"

VERIFY_SYSTEM_PROMPT = "You check an answer produced by a documentation assistant. You are given the question, the numbered documentation excerpts the assistant used, and its answer. Set grounded to true only if every factual claim in the answer is supported by the excerpts. List each unsupported claim in unsupported_claims, quoting at most 20 words of it. Set answers_question to true if the answer directly addresses what the question asks, even briefly."  # noqa: E501

VERIFY_USER_TEMPLATE = "Question: {question}\n\nExcerpts:\n{context}\n\nAnswer:\n{answer}"

REGENERATE_FEEDBACK_TEMPLATE = "Your previous answer contained claims that the excerpts do not support:\n{claims}\nWrite the answer again following all the rules, using only claims the excerpts support. If nothing supported remains, abstain."  # noqa: E501

OUT_OF_SCOPE_TEXT = "I can only answer questions about the LangGraph Python documentation."
