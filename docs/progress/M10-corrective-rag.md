M10: Corrective RAG
Status: Partial (S2 of 3 done: corrective graph and pipeline)
Date: 2026-11-20

Goal
M10 is split into three sessions. S1 (this file's scope so far): verify every API fact S2 needs, move the URL-to-doc mapping into src/ragdocs/docs_urls.py, add the Tavily provider, add the corrective Settings, report first_retrieval_hit@5 (D22) in report, compare and the LangSmith experiment, and re-upload the baseline experiment. S2: LangGraph state, prompts, nodes, graph, AgenticPipeline, graph tests, smoke traces. S3: full evaluation of the corrective pipeline. No S2 or S3 work was done.

Module prompt: "M10 (1/3): groundwork for corrective RAG", given by the human on 2026-11-20.

Step 0: state check (2026-11-20, before any code)
- a) git status: one untracked folder, docs/audit/ (status-audit-2026-11-09.md); no tracked changes. Stopped and asked; human: leave docs/audit/ untracked, stage only this session's files by path, show git status before committing. HEAD 5d205ef "M09: add baseline experiment screenshot"; `git merge-base --is-ancestor v1-baseline HEAD` true.
- b) From M09-ragas-experiments.md:
  - Baseline run folder: results/runs/baseline-20261116-1050.
  - RAGAS path: isolated (.venv-ragas, tools/ragas_score.py), D19 path A. Not src/ragdocs/eval/ragas_score.py.
  - Effective judge_prompt_version: 2 (summary.json judge.effective_prompt_version 2, source judge_v2.jsonl). The run's config.json records 1, the setting at generation time; readers take the highest judge_v<N>.jsonl.
  - experiment --replace: implemented (scripts/langsmith_sync.py, langsmith_sync.next_experiment_name gives <run>-r<N>).
  - Baseline experiment before this session: baseline-20261116-1050-r1 (id 587a3e7e-0328-432d-b0d6-a9dbc8d7c990), current.
- c) requirements.txt line 10 `langgraph==1.2.14`, line 14 `tavily-python==0.8.5`. Installed in .venv (importlib.metadata): langgraph 1.2.14, tavily-python 0.8.5 (also langchain-core 1.6.10, langsmith 0.14.7).
- d) Settings.docs_domain = "docs.langchain.com" (config.py). max_query_rewrites already existed with default 1 (config.py, under "Application limits"; used only in tests/test_config.py line 48), the same as requested, so it was left as is. web_max_results and min_relevant_chunks did not exist. Settings had no tavily_api_key field.
- e) `py tasks.py lint`: "All checks passed!", "126 files already formatted". `py tasks.py test`: "170 passed, 1 deselected in 18.08s".

Step 1: verified facts (installed sources under .venv/Lib/site-packages)

LangGraph 1.2.14
- 1a StateGraph API
  - `from langgraph.graph import StateGraph, START, END` (graph/__init__.py). START = "__start__", END = "__end__" (constants.py lines 28, 30).
  - add_node(node, action=None, *, defer, metadata, input_schema, retry_policy, cache_policy, error_handler, destinations, timeout, trace_policy) (graph/state.py line 667). add_node("name", fn) is the usual form.
  - add_edge(start_key: str | list[str], end_key: str) (state.py line 928).
  - add_conditional_edges(source, path, path_map=None) (state.py line 982). path returns a key or list of keys. path_map is a dict {returned value: node name} or a list of node names (list becomes an identity dict, graph/_branch.py lines 95 to 101). Without path_map, a Literal return annotation is used for the graph drawing (_branch.py line 114). Otherwise the drawing assumes any node.
  - compile(checkpointer=None, *, cache, store, interrupt_before, interrupt_after, debug, name, transformers) (state.py line 1177). It has no config parameter. The compiled graph's default name is "LangGraph" (state.py line 1368).
- 1b Reducers: with `docs: Annotated[list[str], operator.add]` in a TypedDict, each node's partial update is combined with the current value by the reducer. Keys without a reducer are overwritten (last value). Probe: input docs ["init"]; node a returned ["x"], node b ["y", "z"]; final state ['init', 'x', 'y', 'z'].
- 1c stream(..., stream_mode="updates"): yields one dict per node step, `{node_name: update}`. The update is exactly what the node returned, before the reducer merge (pregel/_io.py line 118 map_output_updates). Probe: `[{'a': {'docs': ['x'], 'n': 1}}, {'b': {'docs': ['y', 'z']}}]`. Conditional-edge functions produce no stream item.
- 1d Config: callbacks, run_name, metadata and recursion_limit go in the RunnableConfig passed to invoke() or stream() (not to compile()). Nodes inherit both:
  - Probe callbacks: on_chain_start fired for the graph (root run, name = run_name) and for each node and the routing function as children.
  - Inside a node, config["metadata"] held the user metadata plus langgraph_step, langgraph_node, langgraph_triggers, langgraph_path, langgraph_checkpoint_ns, and config["callbacks"] was set.
  - A node that declares a `config: RunnableConfig` parameter receives it.
  - Hitting recursion_limit raises langgraph.errors.GraphRecursionError (errors.py line 67, a subclass of RecursionError), raised at pregel/main.py line 3078: "Recursion limit of 3 reached without hitting a stop condition. You can increase the limit by setting the `recursion_limit` config key."
  - The default limit is 10007, from env LANGGRAPH_DEFAULT_RECURSION_LIMIT (_internal/_config.py line 32), not 25. recursion_limit < 1 raises ValueError (main.py line 2642).
- 1e Run names: the graph's root run takes config run_name when set ("graph" in the probe), else the compiled name "LangGraph". Each node run is named after its node name ("a", "b"). A conditional-edge function runs as a child chain named after the function ("route"), with metadata langgraph_node = its source node. D22 trace naming (parent run = pipeline name, LangGraph run inside it = "graph", retrieval = "hybrid_retrieve") is therefore set with run_name="graph" in the graph's config.
- 1f Mermaid: `graph.get_graph().draw_mermaid()` (langchain_core/runnables/graph.py line 577; get_graph at pregel/main.py line 909) returns a Mermaid string offline. The probe ran with socket.connect patched to fail, and conditional edges were drawn dashed with path_map labels. draw_mermaid_png() (graph.py line 632) defaults to draw_method=MermaidDrawMethod.API (network, mermaid.ink) and must not be used offline.

tavily-python 0.8.5 and Tavily docs
- 1g Client and search
  - `from tavily import TavilyClient`; TavilyClient(api_key=None, ...) (tavily.py line 44). With no key (argument or env) it runs in keyless mode (tavily.py line 74, header X-Tavily-Access-Mode: keyless). TavilySearch therefore refuses to start without TAVILY_API_KEY.
  - search(query, search_depth=None, topic, ..., max_results=None, include_domains=None, exclude_domains, include_domains_mode=None, include_answer, include_raw_content, include_images, timeout=60, ...) -> dict (tavily.py line 248). It POSTs to https://api.tavily.com/search and drops None parameters.
  - Docs (https://docs.tavily.com/documentation/api-reference/endpoint/search, read 2026-11-20):
    - include_domains: list, at most 300 domains. Subdomain behaviour is not documented.
    - include_domains_mode: "restrict" (default) or "prefer". "prefer" lets other domains through.
    - max_results: 0 to 20, default 10.
    - search_depth: basic (default, 1 credit), advanced (2 credits), fast, ultra-fast.
  - Response: top level query, results, answer, images, response_time, request_id, usage. Each result has url, title, content (a snippet), score (float), plus raw_content (only with include_raw_content), favicon, published_date, images and id.
  - Exceptions (_handle_error_response, tavily.py line 116):
    - 429: UsageLimitExceededError
    - 401: InvalidAPIKeyError
    - 403, 432 (plan limit), 433 (pay-as-you-go limit): ForbiddenError. Import it from tavily.errors; tavily/__init__.py does not export it.
    - 400: BadRequestError
    - anything else, including 5xx: requests.HTTPError via response.raise_for_status() (an OSError subclass, with .response.status_code)
    - request timeout: tavily.errors.TimeoutError
  - The docs list 500 as the only 5xx.

This repo
- 1h Baseline retrieval TraceEvent (type "retrieval", node "retrieve", message "Retrieved candidate excerpts"):
  - data = {"mode": "hybrid", "chunks": [...]}. Each chunk has exactly rank, title, heading_path, url, score. chunk_id is NOT present; url is present.
  - All 50 baseline items have one retrieval event with 5 chunks whose URLs equal the 5 context URLs in order.
  - Event order per item: node_start, retrieval, node_start, node_end (data dropped_citations, uncited), answer (data = PipelineResult dump).
- 1i Data models
  - data/index/chunk_meta.jsonl (553 rows): anchor, chunk_id, doc_path, embed_text, has_code, heading_path, n_tokens, source_commit, text, title, url. chunk_id is unique. 174 rows share a (doc_path, anchor) with another row. Extensions: 548 .mdx, 5 .md.
  - Evidence (schemas.py): doc_path: str (required, backslashes normalised to /), anchor: str (required).
  - RetrievedChunk: chunk: Chunk, score: float, rank: int, retriever: str (all required).
  - Chunk: chunk_id, doc_path, url, title, heading_path: list[str], anchor, text, embed_text, n_tokens: int, has_code: bool, source_commit (all required).
  - PipelineResult: question, pipeline, answer: Answer, contexts: list[RetrievedChunk], trace: list[TraceEvent], llm_calls: int, latency_ms: int, used_web: bool = False.
  - TraceEvent: type in node_start, node_end, decision, retrieval, answer, error; node, message, data: dict = {}, t_ms: int.
- 1j URL mapping before S1: there was no mapping function.
  - doc_path to page URL was inline in ingest/parse.py parse_file (lines 98 to 99: stem without extension under base_url).
  - The anchor was appended inline in ingest/chunk.py chunk_document (line 235).
  - The base URL was scripts/ingest.py DEFAULT_BASE_URL "https://docs.langchain.com/oss/python/langgraph".
  - No URL to doc_path function existed.
  - Callers: scripts/ingest.py (parse_file, chunk_document); tests/test_chunk.py (parse_file with a literal base URL). Nothing else referenced public_url or the base URL (repo search over src, scripts, tests, api, tools).
- 1k format_context(chunks) (generation/answer.py line 61) gives, per chunk, "[n] {title} > {heading_path joined by ' > '} ({url})" on one line, or "[n] {title} ({url})" with no heading path, then the chunk text on the following lines. Blocks are joined by one blank line; n starts at 1. It accepts RetrievedChunk or Chunk.
- 1l Report and LangSmith
  - langsmith_sync.item_feedback builds the feedback dict (keys correctness, citation_support, abstention_correct, hallucinated, context_hit_at_5, context_evidence_recall_at_5, must_mention_coverage, llm_calls, latency_ms, tokens, plus the RAGAS keys). None values are dropped.
  - report.summarize builds overall and per_category from _metrics -> _answer_metrics (a dict of named fields). SUMMARY_ROWS lists (label, key, kind) for summary.md and compare (via rows_for). A new field is one dict entry plus one row.

What was built
- src/ragdocs/docs_urls.py (new, runtime-safe):
  - DOCS_BASE_URL (moved from scripts/ingest.py), doc_path_to_url (from parse_file), chunk_url (from chunk_document).
  - doc_ref_to_url, is_docs_host, known_doc_paths (from chunk_meta.jsonl, cached).
  - url_to_doc_ref(url) -> Evidence | None. The anchor is the fragment ("" when none) and the query is ignored. Returns None for another host, a path outside the base URL, or a page not in the index.
- src/ragdocs/ingest/parse.py, src/ragdocs/ingest/chunk.py, scripts/ingest.py: use docs_urls; the inline copies were removed.
- src/ragdocs/config.py:
  - tavily_api_key (SecretStr | None)
  - web_max_results = 3, min_relevant_chunks = 1
  - web_search_max_attempts = 3, web_search_backoff_s = 1.0
  - max_query_rewrites unchanged (already 1)
- .env.example: comments for WEB_MAX_RESULTS, MIN_RELEVANT_CHUNKS, MAX_QUERY_REWRITES.
- src/ragdocs/schemas.py: WebResult (url, title, content) and WebSearchOutcome (query, results, raw_urls, dropped_off_domain).
- src/ragdocs/providers/websearch.py (new, runtime-safe): TavilySearch(settings, client_factory, sleep).
  - search(query) -> list of {url, title, content}; search_with_diagnostics(query) -> WebSearchOutcome.
  - Retries 429 and 5xx for 3 attempts total (sleeps 1 s, 2 s).
  - WebSearchAuthError on 401 names TAVILY_API_KEY. WebSearchError covers other failures. Messages carry only the exception type and status, never server text or the key; the original exception is suppressed (`from None`).
  - A missing key raises RuntimeError naming TAVILY_API_KEY (Settings.require).
  - The off-domain filter logs a warning with the count and URLs.
- src/ragdocs/eval/report.py: chunk_refs, first_retrieval_refs, first_retrieval_hit_at_5, CONTEXTS_ARE_FIRST_RETRIEVAL = {"baseline"}, the summary field "first_retrieval_hit@5" (overall and per category), and a SUMMARY_ROWS row placed directly above context_hit@5.
- src/ragdocs/eval/langsmith_sync.py: feedback key first_retrieval_hit_at_5 (answerable items) after context_hit_at_5.
- tests/test_docs_urls.py (new, 10), tests/test_websearch.py (new, 8), tests/test_first_retrieval.py (new, 9), tests/test_import_boundaries.py (+2), tests/test_langsmith_sync.py (expected key set +first_retrieval_hit_at_5).
- docs/DECISIONS.md: M10 S1 updates under D8 (Tavily implementation, probe) and D22 (computation, baseline rule).
- results/summary.md: regenerated by `py tasks.py compare` (5 added rows, nothing else changed).
- results/runs/baseline-20261116-1050/langsmith_experiment.json: r2 appended by `experiment --replace`.

How to run
- `py tasks.py compare results/runs/<run> [...]` shows both hit@5 rows.
- `py tasks.py experiment --run-dir results/runs/<run> [--replace]` uploads with first_retrieval_hit_at_5.
- In code: `TavilySearch(get_settings()).search("query")`; `url_to_doc_ref(url)`.

Verification
- Ingest check: `py tasks.py ingest` read the pinned local snapshot.
  - scripts/ingest.py calls fetch_repo, which returns before any git fetch when data/raw/docs-repo/.git is at the commit. `git -C data/raw/docs-repo rev-parse HEAD` = a6e223d2f67558caa20589a03443e918b582943b = DEFAULT_COMMIT.
  - Output: "Found 41 in-scope documentation files.", "Wrote 553 chunks".
  - `py tasks.py hash data/processed/chunks.jsonl`: "f3614b3f74d9f5ff1a4213937132e9928e7b1904992fbee36092be3bbe046bc5" (unchanged). stats.md was byte-identical.
  - source.json changed only in fetched_at (2026-10-12 to 2026-11-20). It was restored with `git checkout -- data/processed/source.json`, because nothing was fetched.
- Baseline first_retrieval_hit@5 vs context_hit@5:
  - Equal on all 42 answerable items (test). The URL-only path, which ignores the baseline rule, also gives equal values on all 42.
  - summarize: overall 34/42 both, single 22/28, multi 7/8, version 5/6.
- `py tasks.py compare results/runs/baseline-20261116-1050`:
  - "| first-retrieval hit@5 (like-for-like retrieval) | 0.810 (34/42) |"
  - "| context_hit@5 (on contexts given to the generator) | 0.810 (34/42) |"
- Tavily domain probe (live, 3 searches, basic depth, 3 credits; Tavily is outside the D7 budget tool, which covers Groq and Gemini only). URLs before the filter:
  - "How do I add a checkpointer to a LangGraph graph?": https://docs.langchain.com/oss/python/langgraph/persistence, .../langgraph/add-memory, .../langgraph/use-time-travel
  - "StateGraph add_conditional_edges example": https://docs.langchain.com/oss/python/langgraph/graph-api, .../langgraph/use-graph-api, .../langgraph/workflows-agents
  - "langgraph interrupt human in the loop": https://docs.langchain.com/oss/python/langgraph/interrupts, https://docs.langchain.com/oss/python/langchain/human-in-the-loop, https://docs.langchain.com/oss/python/deepagents/human-in-the-loop
  - Result: PASS, 9/9 hosts are docs.langchain.com, 0 dropped. 7/9 map to a corpus doc (anchor ""); the langchain and deepagents pages map to None. Each first result's content was 988 to 1,128 characters.
- LangSmith experiment re-upload: `py tasks.py experiment --run-dir results/runs/baseline-20261116-1050 --replace`
  - "Dataset ragdocs-eval-set-v1 verified (same 50 ids and sha256)"
  - Experiment baseline-20261116-1050-r2 (id ebe73692-136c-4fe9-b310-2484bdc29620), 50 examples, now current; r1 and the first upload stay as non-current log entries.
  - URL: https://smith.langchain.com/o/dc790a75-743f-467d-a940-18bb085de125/datasets/6f229f5d-8cff-45b9-840f-3ec576feb329/compare?selectedSessions=ebe73692-136c-4fe9-b310-2484bdc29620
  - API stats (read_project include_stats): right after upload the counts were still filling in (n 31 for most keys, tokens 37 of 50). Re-read a few minutes later: 15 keys (14 from r1 plus the new one).
    - first_retrieval_hit_at_5: n 42, mean 0.810
    - context_hit_at_5: n 42, mean 0.810
    - correctness: n 42, mean 1.833 (same as r1)
    - tokens: n 50
  - Human confirmation in LangSmith: "confirmed" (2026-11-20), first_retrieval_hit_at_5 appears on the experiment.
- Tests: before 170 passed, 1 deselected. After this session's code: 199 passed, 1 deselected (29 new: 10 + 8 + 9 + 2). The baseline snapshot test (tests/test_baseline_snapshot.py) passes unchanged.
- Final verification (2026-11-20, before commit):
  - `py tasks.py lint`: "All checks passed!", "132 files already formatted".
  - `py tasks.py test`: "199 passed, 1 deselected in 11.18s" (170 + 29 new).
  - `py tasks.py bundle-check`: "Total bundle size: 229.85 MB (limit: 400.00 MB)", exit 0.
  - chunks.jsonl hash unchanged.
  - One test fix was needed after the live re-upload. test_baseline_experiment_payload_carries_first_retrieval_hit had hardcoded the replacement name "-r2", but the real upload added a third log entry, so a copy of the run folder now gives "-r3". The test now derives the expected name from the copied log. The committed run folder is never written by tests.

Decisions made
- The baseline's first_retrieval_hit@5 is computed from its contexts (prompt rule for an event without chunk_id), keyed on pipeline name "baseline". Recorded in D22.
- url_to_doc_ref resolves the extension from the index's doc paths, because 5 chunks come from .md pages and the URL drops the extension.
- WebSearchOutcome lives in ragdocs.schemas (AGENTS.md: pydantic models for data crossing module boundaries). search() still returns plain dicts, as the prompt specifies.
- include_domains_mode is not sent; the server default is "restrict" (D8 update).

Deviations from the prompt
- Settings gained tavily_api_key, web_search_max_attempts (3) and web_search_backoff_s (1.0), beyond the three named fields. Reasons: AGENTS.md requires secrets to be read only through get_settings() (Settings had no Tavily key field), and tunable numbers to live in Settings.
- report.py's first_retrieval_hit_at_5 needs chunk_meta.jsonl. It reads it through Settings.index_dir only when a non-baseline retrieval event has a chunk_id.
- tests/test_langsmith_sync.py: the existing exact key-set assertion gained first_retrieval_hit_at_5. That change is required by the new feedback key.
- `py tasks.py ingest` rewrites data/processed/source.json with a new fetched_at date (2026-10-12 to 2026-11-20) even when nothing is fetched. The prompt expected only chunks.jsonl to be checked. source.json was restored with `git checkout -- data/processed/source.json`, so it is not part of this commit.
- docs_urls imports ragdocs.io_utils (stdlib only) besides config and schemas, per the AGENTS.md rule to read JSONL through io_utils.

Known issues and limitations
- Tavily URLs have no #anchor, so a web result maps to (doc_path, "") and matches only evidence whose anchor is "". Web results therefore rarely count as a context hit. first_retrieval_hit@5 is unaffected (it uses the first retrieval only).
- TavilySearch uses the client's default request timeout (60 s).

Open questions for the human
- None open. Resolved: docs/audit/ stays untracked (human, 2026-11-20).

Proposed follow-ups (out of scope)
- A Settings field for the Tavily request timeout if serverless latency needs it (M12/M14).
- Track Tavily credits in the budget tool if usage grows beyond eval runs.

Prerequisites for the next module (S2)
- See "Handoff to S2".

Handoff to S2
Facts S2 can use without re-verifying (sources above):
- LangGraph 1.2.14:
  - `StateGraph(State)`; `add_node("name", fn)`; `add_edge(START, "a")`; `add_conditional_edges("src", route_fn, {"value": "node", "end": END})` (path_map as a dict or a list of node names).
  - `compile(name=...)` takes no config. The default graph name is "LangGraph".
  - State: TypedDict; `Annotated[list[X], operator.add]` appends partial updates; other keys overwrite.
  - `graph.stream(inputs, config, stream_mode="updates")` yields `{node_name: <the node's returned dict, before reducers>}`, one per node step. Routing functions yield nothing.
  - Pass `{"callbacks": [...], "run_name": "graph", "metadata": {...}, "recursion_limit": N}` to invoke() or stream(). Nodes inherit callbacks and metadata, and a node can take `config: RunnableConfig`.
  - Recursion limit: GraphRecursionError (from langgraph.errors; subclass of RecursionError). The default limit is 10007, so set recursion_limit explicitly.
  - LangSmith names: root = run_name, nodes = node names, routing functions = the function name.
  - Mermaid offline: `graph.get_graph().draw_mermaid()`. Never draw_mermaid_png() (network by default).
- Tavily:
  - TavilySearch(settings).search(q) -> [{url, title, content}]; search_with_diagnostics(q) -> WebSearchOutcome(results, raw_urls, dropped_off_domain).
  - Raises WebSearchAuthError or WebSearchError, and RuntimeError when the key is missing.
  - Raw result fields: url, title, content (snippet, about 1,000 characters), score, plus raw_content, favicon and id when requested.
  - Web URLs are page-level (no anchor). Some are outside the LangGraph corpus (url_to_doc_ref returns None).
- Baseline retrieval event chunk fields: rank, title, heading_path, url, score (no chunk_id).
  - S2's first retrieval event must include chunk_id and url per chunk, so that first_retrieval_hit@5 resolves by chunk_id.
  - Web results use chunk ids prefixed "web-", which fall back to the URL.
  - The pipeline name must not be "baseline" (that name selects the contexts rule).
- Models: RetrievedChunk(chunk, score, rank, retriever); Chunk(chunk_id, doc_path, url, title, heading_path, anchor, text, embed_text, n_tokens, has_code, source_commit); Evidence(doc_path, anchor); PipelineResult(..., used_web=False).
- format_context(chunks): "[n] {title} > {heading > path} ({url})\n{text}" blocks joined by a blank line; n from 1. Usable for grading prompts with RetrievedChunk or Chunk.
- Settings:
  - web_max_results = 3, min_relevant_chunks = 1, max_query_rewrites = 1
  - web_search_max_attempts = 3, web_search_backoff_s = 1.0
  - tavily_api_key, docs_domain = "docs.langchain.com"
  - Grader calls use structured_output_method "json_schema" and structured_output_strict True (D23).
- docs_urls: url_to_doc_ref(url) -> Evidence | None; doc_ref_to_url(Evidence) -> url; is_docs_host(url, domain).
- Rerunning ingest: `py tasks.py ingest` rewrites data/processed/source.json with today's fetched_at even when nothing is fetched (scripts/ingest.py writes datetime.date.today()). Any later session that reruns ingest must restore it with `git checkout -- data/processed/source.json` before committing, and must check `py tasks.py hash data/processed/chunks.jsonl` = f3614b3f74d9f5ff1a4213937132e9928e7b1904992fbee36092be3bbe046bc5.
- Surprises:
  - tavily-python silently goes keyless without a key (handled).
  - LangGraph's default recursion limit is 10007, not 25.
  - ForbiddenError is not exported from the tavily package.
  - The existing src/ragdocs/pipelines/agentic/__init__.py (from M00) is the only file in that folder. S1 did not touch it.

---

S2: corrective graph and pipeline (2026-11-20)

Module prompt: "M10 (2/3): corrective graph and pipeline", given by the human on 2026-11-20.

S2 Step 0: state check
- a) HEAD f82849a "M10 (1/3): groundwork for corrective RAG"; git status: only docs/audit/ untracked.
- b) `py tasks.py lint`: "All checks passed!", "132 files already formatted". `py tasks.py test`: "199 passed, 1 deselected in 8.88s".
- c) TraceEvent (src/ragdocs/schemas.py): type, node, message, data (dict, default {}), t_ms (int). type is one of node_start, node_end, decision, retrieval, answer, error. "decision" was already allowed, so no change was needed.
- d) Baseline pattern:
  - registry builds the generator with build_structured_llm(get_chat_model("generator"), method=Settings.structured_output_method, strict=Settings.structured_output_strict), which is with_structured_output(AnswerDraft, method="json_schema", strict=True).
  - generate_answer(question, chunks, llm) builds [SystemMessage(ANSWER_SYSTEM_PROMPT), HumanMessage(ANSWER_USER_TEMPLATE)] with format_context and calls validate_answer.
  - ABSTAIN_TEXT is in generation/prompts.py. Answer(text, citations, abstained) is in schemas.py.
  - The grader and rewriter use the same binding: graph.bind_structured(get_chat_model("grader"), schema, settings).

S2 facts verified this session (not in the S1 handoff)
- langchain_core.exceptions.OutputParserException (.venv/Lib/site-packages/langchain_core/exceptions.py) subclasses ValueError. PydanticOutputParser raises it on malformed JSON (probe).
- Callbacks passed in graph.stream's config reach llm.invoke(messages) inside a functools.partial node without an explicit config argument. In a probe with two nodes, each calling a FakeListChatModel, CallCounter counted 2. generate_answer therefore runs unchanged and is still counted and traced.
- ragdocs.retrieval.retriever.get_retriever is lru_cached on its arguments, so passing Settings (unhashable) raised TypeError. The first q001 attempt failed this way before any API call. build_default_deps now calls get_retriever() with no arguments, as the baseline registry does.

S2 what was built
- src/ragdocs/pipelines/agentic/state.py (new): AgentState TypedDict (events reduced with operator.add), initial_state, Grade, GradeBatch, RewrittenQuery, AgenticDeps dataclass, OUTCOMES.
- src/ragdocs/pipelines/agentic/prompts.py (new): GRADE_SYSTEM_PROMPT, GRADE_USER_TEMPLATE, REWRITE_SYSTEM_PROMPT, REWRITE_USER_TEMPLATE, with the prompt's exact text.
- src/ragdocs/pipelines/agentic/nodes.py (new): retrieve, grade_documents, rewrite_query, web_search, generate, plus helpers (collect_grades, route_decision, merge_relevant, heading_lines, web_page_key, dedupe_web_results, web_chunk_id, web_result_to_chunk).
- src/ragdocs/pipelines/agentic/graph.py (new): build_graph(mode, deps), route_after_grading, bind_structured, build_default_deps, export_mermaid.
- src/ragdocs/pipelines/agentic/pipeline.py (new): AgenticPipeline(mode, deps=None) with stream(); RECURSION_LIMIT = 20.
- src/ragdocs/pipelines/agentic/__init__.py: docstring only.
- src/ragdocs/pipelines/registry.py: "corrective" registered.
- src/ragdocs/config.py: web_text_max_chars = 1800.
- scripts/export_graphs.py (new); tasks.py: `graphs` command.
- scripts/ask.py: prints the outcome of each decision event, and Abstained and Used web after the answer.
- docs/graphs/corrective.mmd (new; generated by `py tasks.py graphs`).
- docs/screenshots/langsmith-corrective-trace.png (new; saved by the human).
- docs/DECISIONS.md: D25 Decision Event Outcome Contract, with the corrective mapping and the tavily_search run name.
- Tests (new): tests/agentic_fakes.py (fakes), tests/test_corrective_graph.py, tests/test_corrective_nodes.py, tests/test_corrective_pipeline.py; 44 collected tests in total.

S2 how to run
- `.venv\Scripts\python scripts\ask.py --pipeline corrective "question"`
- `py tasks.py graphs` rewrites docs/graphs/corrective.mmd.

S2 verification
- Tests: before 199 passed, 1 deselected. After: "243 passed, 1 deselected in 10.80s" (44 new). No existing test was changed. The baseline snapshot test and the import-boundary tests pass unchanged; the new test_agentic_modules_are_runtime_safe covers ragdocs.pipelines.agentic and its pipeline, graph and nodes modules, plus the registry.
- `py tasks.py lint`: "All checks passed!", "142 files already formatted".
- `py tasks.py bundle-check`: "Total bundle size: 229.91 MB (limit: 400.00 MB)", exit 0.
- Smoke traces (2026-11-20, LANGSMITH_TRACING true, TAVILY_API_KEY present; 60 s between questions).
  - Budget check before the runs: openai/gpt-oss-20b 20,000 tokens / 9 requests, openai/gpt-oss-120b 12,000 / 3, gemini-embedding-001 200 / 6. All fit (each Groq model had 180,000 tokens free at 0.9).
  - Tokens below come from the budget recorder's events in cache/budget.json. There were no 429s, and the grader never returned malformed output.
  - The smoke runs used the code before the web de-duplication fix (see Deviations). q043 was not re-run, as the human instructed.
  - q001 (single) "My agent run stops with GRAPH_RECURSION_LIMIT; where do I set a bigger step cap?"
    - retrieve: node_start, retrieval (5 chunks, hybrid), node_end
    - grade_documents: "4 of 5 chunks relevant" (ok); "Route to generate: 4 relevant chunk(s) >= 1" (ok)
    - generate: "Generating from 4 graded excerpts and 0 web results" (info); node_end "Answer generated and validated" (dropped_citations=0, uncited=False)
    - answer
    - llm_calls 2, used_web False, latency_ms 3,112, not abstained
    - Citations: 0b10c87050fe58d0 .../langgraph/errors/GRAPH_RECURSION_LIMIT#troubleshooting; 969a9656a46db3ac .../langgraph/graph-api#recursion-limit
    - Tokens: gpt-oss-20b 2,218 (1 call), gpt-oss-120b 1,773 (1 call), total Groq 3,991; embedding 1 request
  - q009 (version) "Which channel mechanism avoids storing redundant duplicate states by persisting only incremental changes?"
    - Same event sequence as q001: "4 of 5 chunks relevant" (ok), "Route to generate" (ok), "Generating from 4 graded excerpts and 0 web results" (info)
    - llm_calls 2, used_web False, latency_ms 3,819, not abstained; the answer names DeltaChannel
    - Citations: 1275ba85560b4ff7 .../langgraph/checkpointers#optimize-checkpoint-storage; 5d6a26b01d1541a7 .../langgraph/pregel#deltachannel
    - Tokens: gpt-oss-20b 1,942, gpt-oss-120b 2,577, total Groq 4,519; embedding 1 request
  - q043 (unanswerable) "Which RetryPolicy argument caps the total wall-clock time a node may spend across all of its retry attempts?"
    - retrieve (5 chunks)
    - grade_documents: "0 of 5 chunks relevant" (retry); "Route to rewrite_query: too few relevant chunks; rewrite 1 of 1" (retry)
    - rewrite_query: "query rewritten" (retry). New query: "LangGraph RetryPolicy max_retry_time argument total wall-clock time"
    - retrieve (5 chunks)
    - grade_documents: "0 of 5 chunks relevant" (retry); "Route to web_search: too few relevant chunks after 1 rewrite(s)" (retry)
    - web_search: "fell back to web search" (retry), 3 results: .../langgraph/fault-tolerance, .../fault-tolerance#graph-defaults, .../fault-tolerance?ref=docs
    - generate: "Generating from 0 graded excerpts and 3 web results" (info); node_end (dropped_citations=0, uncited=False)
    - answer
    - llm_calls 4 (worst case), used_web True, latency_ms 8,222
    - Abstained with ABSTAIN_TEXT and no citations. It did not hallucinate.
    - Tokens: gpt-oss-20b 4,690 over 3 calls (grade 2,060, rewrite 534, grade 2,096), gpt-oss-120b 1,501, total Groq 6,191; embedding 2 requests
- LangSmith nesting check (langsmith Client.list_runs(trace_id=...), read-only):
  - q001 trace 01a1f84b-00b6-7ad2-9511-97f1d0b80f7f, 13 runs: corrective [chain] > graph [chain] > retrieve > hybrid_retrieve [retriever]; grade_documents > RunnableSequence > ChatGroq [llm], PydanticOutputParser, plus route_after_grading; generate > RunnableSequence > ChatGroq.
  - q043 trace 01a1f84e-f276-73c3-8e04-f7a147d6246f, 26 runs: the same, plus rewrite_query > RunnableSequence > ChatGroq, a second retrieve and grade_documents, and web_search > tavily_search [tool].
  - Same-name parent/child pairs: none in either trace.
  - Screenshot: docs/screenshots/langsmith-corrective-trace.png (q043 trace), 131,857 bytes, confirmed present.
  - q043 trace URL: https://smith.langchain.com/o/dc790a75-743f-467d-a940-18bb085de125/projects/p/e4eb3d8d-cec4-49fa-8825-3da2f1caac1b/trace/01a1f84e-f276-73c3-8e04-f7a147d6246f/run/01a1f84e-f276-73c3-8e04-f7a147d6246f?start_time=2026-11-20T09%3A34%3A45.878167%2B00%3A00

S2 decisions made
- D25 (outcome contract) was added to DECISIONS.md.
- generate also emits an "info" decision ("Generating from k graded excerpts and m web results") when it calls the LLM, so every node except retrieve has a decision event the UI can show.
- The error event message is the exception class name only (for example "ValueError", "GraphRecursionError"). The eval runner's rate-limit check still works because it matches the "RateLimitError" prefix.

S2 deviations from the prompt
- Inner Tavily run named "tavily_search", not "web_search". The prompt's name would have nested a run under one with the same name as its node, which D22 forbids. The human chose tavily_search on 2026-11-20. Recorded in D25.
- Web result de-duplication (added after the smoke runs, at the human's instruction; a correctness fix, not tuning).
  - In q043, Tavily returned one page three times (plain, #graph-defaults, ?ref=docs).
  - web_search now keeps the first result per page in Tavily's order. The key is host + path, lowercased, without a trailing slash, ignoring query and fragment.
  - The kept URL drops its query string but keeps its fragment, and that URL is what url_to_doc_ref receives. Ranks are 1..n over the kept list.
  - The dropped count is in diagnostics["web_duplicates_dropped"] and in the web_search decision event data.
  - Tests cover the three q043-style URLs. The q043 smoke was not re-run (human instruction).
- Answer event in PipelineResult.trace: checked against BaselinePipeline._stream_events. The baseline appends the answer event to the trace (emit appends), then sets e_answer.data to a fresh dump. AgenticPipeline now does the same, so the trace holds every yielded event with the answer event last.
- Settings.web_text_max_chars = 1800 was added, so the truncation length is a setting and not a number in the code (AGENTS.md).
- AgenticPipeline lives in its own module, pipeline.py, which the prompt's file list did not name. This keeps graph.py to graph construction.
- grade_documents makes no LLM call when documents is empty ("0 of 0 chunks relevant"). The prompt did not cover this case, and skipping the call keeps the call bound.
- The parent run's outputs also include diagnostics (missing_grades, invalid_grades, grading_failures, web_duplicates_dropped, rewrite_unchanged, and generate's dropped_citations and uncited).
- The retrieval event data also has mode and query; the per-chunk fields are exactly as specified.
- scripts/ask.py prints decision outcomes, Abstained and Used web. These are display-only additions.

S2 known issues and limitations
- A web search failure (WebSearchError, or RuntimeError for a missing key) ends the run with an error event. The prompt defines no fallback for it.
- The corrective pipeline needs TAVILY_API_KEY at construction, even for questions that never reach web search.

Known limitations for S3
- Web chunk anchors: S1 found no #anchor on Tavily URLs. The S2 smoke showed that Tavily URLs sometimes carry a fragment or query string (q043: .../fault-tolerance#graph-defaults and ?ref=docs).
  - After de-duplication, a kept fragment can map to a real anchor through url_to_doc_ref.
  - Most web chunks still get anchor "", or a "web:" doc_path for pages outside the corpus, and almost never match section-level gold evidence.
  - context_hit@5 and context_evidence_recall@5 therefore undercount answers supported by web results, and S3 must say so next to those rows.
  - first_retrieval_hit@5 is not affected (it uses the first retrieval event, which holds chunk_id and url for every chunk).
- Contexts for corrective are graded chunks plus web results (D22), so context metrics partly measure the grader.

Open questions for the human (S2)
- None open. Resolved: inner run name (tavily_search, human, 2026-11-20).

Proposed follow-ups (out of scope, S2)
- The rewriter added the term "max_retry_time" to the q043 query ("LangGraph RetryPolicy max_retry_time argument total wall-clock time"), and the grader's reasons used the same name ("No mention of max_retry_time in excerpt."). Neither the question text nor anything in data/eval/eval_set.jsonl mentions max_retry_time or retry_time; the question only says "caps the total wall-clock time". The grader and rewriter therefore introduced a parameter name of their own. The prompts were not changed. A later module could tell the rewriter not to name identifiers that appear in neither the question nor the headings, after measuring it on the eval set, not on smoke results.
- A fallback for web search failures (abstain or generate from what remains) instead of an error event.
- Construct TavilySearch lazily, so the pipeline starts without TAVILY_API_KEY.
- config.py declares tavily_api_key twice (same type; harmless; from S1).

Prerequisites for the next session (S3)
- See "Handoff to S3".

Handoff to S3
- Commands (after `py tasks.py budget --need ...` for each model):
  - `py tasks.py eval --pipeline corrective`
  - `py tasks.py judge --run-dir results/runs/<corrective run>` (if eval does not judge)
  - `py tasks.py ragas --run-dir results/runs/<corrective run>` (after `--cache-check`)
  - `py tasks.py experiment --run-dir results/runs/<corrective run>`
  - `py tasks.py compare results/runs/baseline-20261116-1050 results/runs/<corrective run>`
- Measured per smoke question (Groq tokens from the budget recorder):
  - Direct path (2 calls): 3,991 to 4,519 tokens; gpt-oss-20b grade about 1,900 to 2,200, gpt-oss-120b generate about 1,800 to 2,600.
  - Worst case (4 calls, q043): 6,191 tokens; gpt-oss-20b 4,690 (two grades of about 2,100 and one rewrite of 534), gpt-oss-120b 1,501 (abstaining). One Tavily credit and 2 embedding requests.
- Groq budget risks:
  - gpt-oss-20b (grader) now takes 2,000 to 4,700 tokens per item. For 50 items, assuming about 20% take the worst path, that is about 50 x 2,100 + 10 x 2,600 = 131,000 tokens. This is within its 200,000 daily limit (180,000 at 0.9), but tight if more items take the worst path.
  - gpt-oss-120b stays near baseline levels (one call per item, or none when web search returns nothing).
  - Each item can need up to about 6,200 tokens across the two models. 8,000 TPM is per model, so the runner's throttle should keep 20b items apart.
  - The judge (Gemini) and RAGAS budgets are unchanged per item. RAGAS has more context text when web results are used (up to 8 contexts, each web chunk up to 1,800 characters).
- Surprises:
  - Tavily returned the same page three times with a fragment and a query string (now de-duplicated).
  - get_retriever is lru_cached and rejects a Settings argument.
  - The grader and rewriter introduced an identifier that is in neither the question nor the excerpts (see Proposed follow-ups).
