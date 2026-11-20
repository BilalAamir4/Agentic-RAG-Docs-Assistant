"""Prompts for the corrective RAG grader and query rewriter (M10).

The answer prompt is shared with the baseline and lives in ragdocs.generation.prompts.
"""

GRADE_SYSTEM_PROMPT = "You judge whether documentation excerpts are relevant to a developer's question about LangGraph (Python). An excerpt is relevant if it contains information that would help answer the question, even partially. It is not relevant if it only shares keywords with the question or covers a different feature. Grade every excerpt independently. Return one grade per excerpt number, each with a reason of at most 15 words."  # noqa: E501

GRADE_USER_TEMPLATE = "Question: {question}\n\nExcerpts:\n{context}"

REWRITE_SYSTEM_PROMPT = "You rewrite a developer's question into a search query for the LangGraph Python documentation. The previous search returned no relevant excerpts. Write one query of at most 20 words that names the LangGraph concepts, classes or functions the answer most likely involves, using the documentation's own terminology. Do not answer the question."  # noqa: E501

REWRITE_USER_TEMPLATE = "Question: {question}\nPrevious query: {query}\nHeadings returned by the previous search, all judged not relevant:\n{headings}"  # noqa: E501
