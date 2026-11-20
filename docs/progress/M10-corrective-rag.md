M10: Corrective RAG
Status: Done (S1, S2 and S3 complete)
Date: 2026-11-21

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

---

S3: full evaluation of corrective and comparison with the baseline (2026-11-20)

Module prompt: "M10 (3/3): evaluation", given by the human on 2026-11-20.

S3 Step 0: state check (2026-11-20 18:52Z, before any API call)
- a) HEAD 00d3d85 "M10 (2/3): corrective graph and pipeline"; git status: only docs/audit/ untracked.
- b) `py tasks.py lint`: "142 files already formatted", ruff check and format pass. `py tasks.py test`: "243 passed, 1 deselected in 13.79s".
- c) .env: LANGSMITH_TRACING true; GROQ_API_KEY present, GOOGLE_API_KEY present, TAVILY_API_KEY present, LANGSMITH_API_KEY present.
- d) Settings.judge_prompt_version = 2. Baseline effective judge_prompt_version = 2 (highest file judge_v2.jsonl; summary.json judge.effective_prompt_version 2; config.json records 1, the setting at generation time). Equal.
- Baseline current experiment: langsmith_experiment.json marks baseline-20261116-1050-r2 (id ebe73692-136c-4fe9-b310-2484bdc29620) current. The prompt expected r3 or later; there is no r3 entry (the "-r3" in S1 came from a test's copy of the folder). Following the prompt's rule "use the entry marked current", r2 is used.
- e) `py tasks.py budget` (18:51Z): openai/gpt-oss-120b 0/1000 requests, 0/200,000 tokens; openai/gpt-oss-20b 0/1000, 0/200,000; gemini-3.5-flash-lite (judge) 0/500; gemini-3.1-flash-lite (RAGAS LLM) 0/500; gemini-embedding-001 4/1000 (89 tokens).
- f) Budget plan (50 items). Sources: S2 smoke (grade about 1,900 to 2,200 tokens, rewrite 534, generate 1,500 to 2,600) and the baseline run (gpt-oss-120b 116,678 tokens over 50 calls, 2,334 per item; judge 88,544 tokens over 39 calls).
  - openai/gpt-oss-20b (grader, rewriter): best case 50 x 1 grade x 2,100 = 105,000 tokens, 50 requests; worst case 50 x (2 x 2,100 + 534) = 236,700 tokens, 150 requests. Cap at 0.9 = 180,000, bucket drain 2.315 tokens/s: best case 1 day; worst case exceeds the cap by about 57,000 tokens, about 7 h of drain, so within 2 calendar days.
  - openai/gpt-oss-120b (generator): at most 50 calls; about 50 x 2,600 = 130,000 tokens worst case, 116,700 at the baseline rate; 1 day. Fewer if items abstain on empty web without an LLM call.
  - Judge gemini-3.5-flash-lite: at most 42 calls (answerable, non-abstained), about 42 x 2,270 = 95,000 tokens; 1 day (cap 450 requests).
  - RAGAS gemini-3.1-flash-lite: estimate from Settings.ragas_llm_calls_per_metric (3, 6, 7, 2) over at most 42 items: 126 + 252 + 294 + 84 = 756 requests (context precision grows with the number of contexts, up to 8 with web); cap 450 per Pacific day, so 2 days. The exact plan comes from `--plan-only` after the eval.
  - Embeddings gemini-embedding-001: eval up to 2 requests per item (100); RAGAS response_relevancy 2 per item (up to 84); 1 day.
  - Tavily: at most 1 credit per item, at most 50 credits.
  - Worst case for Groq needs 2 days at most (not more than 2), so no warning applies.
  - `py tasks.py budget --need openai/gpt-oss-20b=180000:150 --need openai/gpt-oss-120b=130000:50 --need gemini-embedding-001=400:100`: all three "fits".

S3 Step 1: eval run (in progress, stopped)
- `py tasks.py eval --pipeline corrective` started 18:52Z; run folder results/runs/corrective-20261120-1852.
- STOP rule hit: q008 used 9,560 Groq tokens (limit 8,000 per item). The runner was stopped by ending its process after 8 complete items (per_question.jsonl 8 lines, q001 to q008; no partial line; failed_attempts.jsonl empty). The folder is resumable with `py tasks.py eval --pipeline corrective --run-dir results/runs/corrective-20261120-1852`.
- q008 detail: direct path (graded 2 of 5 relevant on the first try, route to generate, 2 LLM calls, no retries, no web). gpt-oss-20b grade 4,857 in + 294 out = 5,151; gpt-oss-120b generate 4,172 in + 237 out = 4,409 (from 2 graded excerpts). The answer abstained (false abstention candidate). The cost is input size: q008 was also the largest baseline item (5,236 tokens for one 120b call over 5 excerpts; the next largest baseline item was 3,109).
- q001 to q007: all graded relevant on the first try, 2 calls each, 2,917 to 4,912 Groq tokens; no grading failures, missing or invalid grades.
- Open question for the human: continue the run with q008 accepted as recorded, or another instruction.
- Human decision (2026-11-21): resume with q008 kept exactly as recorded. The 8,000-token STOP is replaced for the rest of S3 (see Deviations).
- Checks before resuming (no code changed):
  - a) Throttle (src/ragdocs/eval/throttle.py, runner.py):
    - The estimate is per model. UsageEstimator keeps, per model, the maximum tokens and requests seen in one item. wait_all calls each model's RollingBudget.wait_for with that model's own estimate. Before the first observation every model gets eval_initial_token_estimate (3,000). On resume, seed_estimator feeds the done items into it.
    - RollingBudget.wait_for first checks the daily cap (DailyLimitReached, exit 3). It then loops until window tokens + estimate <= tokens_per_min x safety and requests fit, or until the per-minute window has no events (`if fits or not self._events: return`). An estimate above 8,000 x 0.9 = 7,200 therefore waits for an empty window at worst, then proceeds. It does not wait forever and does not raise.
    - After q008 the estimates are gpt-oss-20b 5,151 and gpt-oss-120b 4,409, both under 7,200. The next wait_for returns after at most one window (60 s).
    - The per-minute window is in memory, so a resumed process starts with an empty window.
    - The pre-approved fix applies only if wait_for could block forever or the estimate were a cross-model total. Neither is true, so it was not applied and no code changed.
  - b) Groq 429 handling (installed sources):
    - src/ragdocs/providers/llm.py builds ChatGroq with max_retries=3 for both the generator and the grader. langchain_groq passes max_retries to the groq client.
    - groq/_base_client.py _should_retry retries on status 429 unless the response has the header x-should-retry: false. _calculate_retry_timeout uses retry-after-ms or retry-after when it is between 0 and 60 s. Otherwise it backs off exponentially: 0.5 s x 2^n, capped at 8 s (groq/_constants.py), with up to 25% jitter. So a call is tried at most 4 times (1 + 3 retries), and a retry-after over 60 s is not honoured; the backoff is used instead.
    - When the retries run out, RateLimitError ends the graph with an error event. The runner (_run_one) writes the attempt to failed_attempts.jsonl and calls handle_rate_limit. That function waits for the retry-after parsed from the message (default rate_limit_default_wait_s 60 s) plus 1 s, and the item is retried. A rate-limited attempt does not use up an item attempt.
    - The run pauses with exit 3 (RateLimitPause) if the wait is over rate_limit_max_wait_s (1,800 s), if the waits for one item exceed rate_limit_max_waits_per_item (3), or if a per-day 429 is the second budget-model miss (budget_model_max_misses 2).
- Budget before resuming (2026-11-20 19:31Z by the machine clock): gpt-oss-20b balance 15,952/200,000, gpt-oss-120b 10,849/200,000, embeddings 12/1000. `py tasks.py budget --need openai/gpt-oss-20b=150000:130 --need openai/gpt-oss-120b=120000:42 --need gemini-embedding-001=400:84`: all three "fits".
- Rules for the remaining items (human, 2026-11-21):
  - Per-item tokens per model are recorded and reported, not a STOP.
  - Every item over 7,200 tokens on one model is listed below.
  - STOP if any single LLM call uses more than 7,200 tokens (checked per call from the cache/budget.json events).
  - STOP if the same item fails on rate-limit retries twice in a row.
  - Exit 3 is handled as before.
- Note for Step 3 (human): q008 abstained in both pipelines. Corrective graded 2 of 5 excerpts relevant before abstaining, so that false abstention happened at generation, not grading.
- Resumed run: `py tasks.py eval --pipeline corrective --run-dir results/runs/corrective-20261120-1852`, 2026-11-20 19:31Z to about 20:30Z (machine clock), exit 0. Final lines: "q050 done (4 calls, 8248 ms)", "All items done. Summary written to results/runs/corrective-20261120-1852/summary.md".
- Failed attempts (failed_attempts.jsonl). Each was retried and succeeded on the second attempt; neither was a rate-limit failure:
  - q043: stage grade_documents, message "WebSearchError", 2026-11-20T19:59:50Z. The stage is the last node_start before the error. The error came from the web_search node, which emits its node_start only in its return value, so the stage still reads grade_documents. Its TraceEvent message is the class name only (S2 decision). The LangSmith trace (tavily_search run, read-only) gives "Tavily search failed after 1 attempt(s): ConnectionError (status None)": a connection error with no HTTP status, which TavilySearch does not retry (it retries only 429 and 5xx).
  - q049: stage grade_documents, message "BadRequestError". It was a Groq 400 on the rewrite_query call (structured RewrittenQuery on gpt-oss-20b), not on a grader call. The LangSmith trace shows the error on ChatGroq under rewrite_query. rewrite_query emits its node_start only in its return value, so the stage still reads grade_documents. budget.json has one gpt-oss-20b request with 0 tokens in the run. The runner retried the whole item, which then completed (4 calls, web fallback).
- Per item (Groq tokens per model are input + output, from per_question usage):
  | id | category | path | grading k of n | llm_calls | gpt-oss-20b | gpt-oss-120b | used_web | abstained |
  |---|---|---|---|---|---|---|---|---|
  | q001 | single | graded relevant first try | 4 of 5 | 2 | 1,915 | 1,761 | False | False |
  | q002 | single | graded relevant first try | 5 of 5 | 2 | 2,219 | 2,522 | False | False |
  | q003 | single | graded relevant first try | 1 of 5 | 2 | 2,603 | 923 | False | False |
  | q004 | single | graded relevant first try | 4 of 5 | 2 | 2,601 | 2,311 | False | False |
  | q005 | single | graded relevant first try | 4 of 5 | 2 | 2,333 | 2,095 | False | False |
  | q006 | single | graded relevant first try | 2 of 5 | 2 | 2,604 | 1,076 | False | False |
  | q007 | single | graded relevant first try | 2 of 5 | 2 | 1,847 | 1,070 | False | False |
  | q008 | single | graded relevant first try | 2 of 5 | 2 | 5,151 | 4,409 | False | True |
  | q009 | version | graded relevant first try | 4 of 5 | 2 | 1,942 | 2,233 | False | False |
  | q010 | single | graded relevant first try | 3 of 5 | 2 | 2,968 | 2,081 | False | False |
  | q011 | single | graded relevant first try | 3 of 5 | 2 | 3,153 | 2,433 | False | False |
  | q012 | single | graded relevant first try | 2 of 5 | 2 | 2,099 | 1,434 | False | False |
  | q013 | single | graded relevant first try | 5 of 5 | 2 | 2,338 | 2,724 | False | False |
  | q014 | single | graded relevant first try | 2 of 5 | 2 | 1,896 | 975 | False | False |
  | q015 | single | graded relevant first try | 3 of 5 | 2 | 2,298 | 1,508 | False | False |
  | q016 | single | graded relevant first try | 4 of 5 | 2 | 2,146 | 2,189 | False | False |
  | q017 | single | graded relevant first try | 2 of 5 | 2 | 2,089 | 1,575 | False | False |
  | q018 | single | graded relevant first try | 4 of 5 | 2 | 2,257 | 2,338 | False | False |
  | q019 | single | graded relevant first try | 2 of 5 | 2 | 2,579 | 1,564 | False | False |
  | q020 | single | graded relevant first try | 3 of 5 | 2 | 2,337 | 1,720 | False | False |
  | q021 | single | graded relevant first try | 4 of 5 | 2 | 1,491 | 1,290 | False | False |
  | q022 | single | graded relevant first try | 2 of 5 | 2 | 2,319 | 1,415 | False | False |
  | q023 | single | graded relevant first try | 4 of 5 | 2 | 2,650 | 2,025 | False | False |
  | q024 | single | graded relevant first try | 1 of 5 | 2 | 2,743 | 1,193 | False | False |
  | q025 | single | web fallback | 0 of 5; 0 of 5 | 4 | 4,313 | 1,839 | True | True |
  | q026 | single | graded relevant first try | 1 of 5 | 2 | 2,241 | 1,101 | False | False |
  | q027 | single | graded relevant first try | 4 of 5 | 2 | 1,958 | 1,787 | False | False |
  | q028 | single | graded relevant first try | 1 of 5 | 2 | 1,933 | 799 | False | False |
  | q029 | multi | graded relevant first try | 5 of 5 | 2 | 2,890 | 2,109 | False | True |
  | q030 | multi | graded relevant first try | 4 of 5 | 2 | 2,890 | 2,232 | False | False |
  | q031 | multi | graded relevant first try | 2 of 5 | 2 | 2,446 | 1,538 | False | False |
  | q032 | multi | graded relevant first try | 4 of 5 | 2 | 1,891 | 1,887 | False | False |
  | q033 | multi | graded relevant first try | 3 of 5 | 2 | 2,633 | 1,921 | False | False |
  | q034 | multi | graded relevant first try | 4 of 5 | 2 | 1,881 | 2,126 | False | False |
  | q035 | multi | graded relevant first try | 1 of 5 | 2 | 2,246 | 1,326 | False | False |
  | q036 | multi | graded relevant first try | 5 of 5 | 2 | 2,029 | 2,764 | False | False |
  | q037 | version | graded relevant first try | 5 of 5 | 2 | 2,277 | 2,396 | False | False |
  | q038 | version | graded relevant first try | 3 of 5 | 2 | 2,648 | 2,009 | False | False |
  | q039 | single | graded relevant first try | 5 of 5 | 2 | 2,660 | 2,822 | False | False |
  | q040 | version | graded relevant first try | 5 of 5 | 2 | 2,663 | 2,420 | False | False |
  | q041 | version | graded relevant first try | 5 of 5 | 2 | 2,046 | 2,089 | False | False |
  | q042 | version | graded relevant first try | 4 of 5 | 2 | 2,136 | 1,789 | False | False |
  | q043 | unanswerable | web fallback | 0 of 5; 0 of 5 | 4 | 5,672 | 985 | True | True |
  | q044 | unanswerable | web fallback | 0 of 5; 0 of 5 | 4 | 4,042 | 1,359 | True | True |
  | q045 | unanswerable | web fallback | 0 of 5; 0 of 5 | 4 | 3,921 | 1,591 | True | True |
  | q046 | unanswerable | web fallback | 0 of 5; 0 of 5 | 4 | 4,643 | 1,393 | True | True |
  | q047 | unanswerable | graded relevant first try | 1 of 5 | 2 | 2,422 | 1,002 | False | True |
  | q048 | unanswerable | web fallback | 0 of 5; 0 of 5 | 4 | 5,290 | 1,264 | True | True |
  | q049 | unanswerable | web fallback | 0 of 5; 0 of 5 | 4 | 4,869 | 1,511 | True | True |
  | q050 | unanswerable | web fallback | 0 of 5; 0 of 5 | 4 | 5,654 | 1,070 | True | True |
- Paths: graded relevant on the first try 42 (q001 to q024, q026 to q042, q047); rewrote then relevant 0; web fallback 8 (q025 and q043 to q046, q048 to q050), each after 0 of 5 on both gradings; abstained on empty web 0 (every web search returned 1 to 3 results).
- Diagnostics over 50 items: grading_failures 0, missing_grades 0, invalid_grades 0, rewrite_unchanged 0, web_duplicates_dropped 4. Malformed grading on 0 of 50 items (STOP rule: more than 3).
- Web hosts: 20 web results across 8 items, all docs.langchain.com (STOP rule: none outside). 11 of the 20 URLs are outside the ingested LangGraph Python corpus (oss/javascript, oss/python/langchain, oss/python/integrations, langsmith).
- Token rules:
  - Items over 7,200 tokens on one model: none. The largest per item were gpt-oss-20b 5,672 (q043) and gpt-oss-120b 4,409 (q008).
  - Largest single LLM call (cache/budget.json events since the run started): gpt-oss-20b 5,151, gpt-oss-120b 4,409. The per-call STOP (over 7,200) did not apply.
  - Rate-limit failures in a row: none.
  - The old 8,000 combined rule would have flagged only q008 (9,560).
- Totals in per_question.jsonl: gpt-oss-20b 138,872 tokens over 66 calls; gpt-oss-120b 89,993 tokens over 50 calls.
  - budget.json recorded 71 gpt-oss-20b requests and 50 gpt-oss-120b requests, including the failed attempts: q043's first attempt, and q049's 400, which counts as 1 request with 0 tokens.
  - 8 web items used 8 Tavily credits.
- Step 1.3: per_question.jsonl has 50 lines with 50 unique ids. summary.json and summary.md exist.
- Judge (D9: eval does not judge): `py tasks.py budget --need gemini-3.5-flash-lite=110000:42` "fits"; `py tasks.py judge --run-dir results/runs/corrective-20261120-1852`, exit 0, "Judging complete". judge_v2.jsonl: 39/39 eligible items judged, 0 cached, 66,166 tokens in and 2,540 out, gemini-3.5-flash-lite, prompt version 2.

S3 Step 2: RAGAS and experiment
- Plan (`py tasks.py ragas --run-dir results/runs/corrective-20261120-1852 --plan-only`): "faithfulness 39 x 3 = 117; response_relevancy 39 x 6 = 234; context_precision 42 x 7 = 294; context_recall 42 x 2 = 84; total 729 requests; used today 0/500; cap at 0.9 = 450; days needed 2"; embeddings 78 requests. `--cache-check`: 1/42 items fully cached, still needed 720 LLM and 78 embedding requests.
- `py tasks.py budget --need gemini-3.1-flash-lite=1125000:450 --need gemini-embedding-001=6000:78`: both "fits" (the tool caps itself at 450 per Pacific day and exits 3 at the cap).
- `py tasks.py ragas --run-dir results/runs/corrective-20261120-1852` (2026-11-20 20:13Z to about 20:45Z), exit 0 in one session: "Wrote ragas_config.json, ragas_scores.jsonl, ragas_summary.json to results/runs/corrective-20261120-1852". Actual use: 367 LLM requests (461,056 tokens) and 35 embedding requests, below the 729 estimate (fewer contexts per item than the estimate assumes). cache/ragas_errors.jsonl: no entries from this run (no retried failures).

  | metric | mean | n_eligible | n_scored | n_errored |
  |---|---|---|---|---|
  | faithfulness (prose-level grounding signal) | 0.909 | 39 | 39 | 0 |
  | response_relevancy | 0.823 | 39 | 39 | 0 |
  | context_precision (on contexts given to the generator) | 0.781 | 42 | 42 | 0 |
  | context_recall (on contexts given to the generator) | 0.821 | 42 | 42 | 0 |

- 10% error rule: 0/39, 0/39, 0/42, 0/42. PASS.
- `py tasks.py experiment --run-dir results/runs/corrective-20261120-1852` (no --replace): "Dataset ragdocs-eval-set-v1 verified (same 50 ids and sha256)"; experiment corrective-20261120-1852, id 1b13b3ef-e94f-423b-bcee-eb930ae61de1, 50 examples, current.
  - URL: https://smith.langchain.com/o/dc790a75-743f-467d-a940-18bb085de125/datasets/6f229f5d-8cff-45b9-840f-3ec576feb329/compare?selectedSessions=1b13b3ef-e94f-423b-bcee-eb930ae61de1
- API check (Client.read_project include_stats, read-only): both corrective-20261120-1852 and baseline-20261116-1050-r2 have the same 15 feedback keys: abstention_correct, citation_support, context_evidence_recall_at_5, context_hit_at_5, context_precision, context_recall, correctness, faithfulness, first_retrieval_hit_at_5, hallucinated, latency_ms, llm_calls, must_mention_coverage, response_relevancy, tokens. Corrective n and mean: correctness 42 1.786; first_retrieval_hit_at_5 42 0.810; context_hit_at_5 42 0.786; faithfulness 39 0.909; response_relevancy 39 0.823; context_precision 42 0.781; context_recall 42 0.821; tokens 50 4,577.3; llm_calls 50 2.32.

S3 Step 3: compare and record
- `py tasks.py compare results/runs/baseline-20261116-1050 results/runs/corrective-20261120-1852`: exit 0, "Wrote .../results/summary.md" (compare accepted the pair: same tracing setting, judge prompt version 2 in both). results/summary.md as written:

  # Run comparison
  
  Judge gemini-3.5-flash-lite, prompt version 2. Rates are rate (count/n); correctness n = every answerable item.
  
  ## Overall
  
  | Field | baseline-20261116-1050 | corrective-20261120-1852 |
  |---|---|---|
  | items | 50 | 50 |
  | answerable n | 42 | 42 |
  | correct (correctness = 2) | 0.905 (38/42) | 0.881 (37/42) |
  | correct or partial (correctness >= 1) | 0.929 (39/42) | 0.905 (38/42) |
  | mean correctness (0-2) | 1.833 (n=42) | 1.786 (n=42) |
  | citation_support (judged items) | 1.000 (39/39) | 0.949 (37/39) |
  | first-retrieval hit@5 (like-for-like retrieval) | 0.810 (34/42) | 0.810 (34/42) |
  | context_hit@5 (on contexts given to the generator) | 0.810 (34/42) | 0.786 (33/42) |
  | mean context_evidence_recall@5 (on contexts given to the generator) | 0.726 (n=42) | 0.702 (n=42) |
  | mean must_mention coverage (soft signal, D15) | 0.905 (n=42) | 0.905 (n=42) |
  | false_abstention | 0.071 (3/42) | 0.071 (3/42) |
  | abstention_correct (unanswerable) | 1.000 (8/8) | 1.000 (8/8) |
  | hallucinated (unanswerable) | 0.000 (0/8) | 0.000 (0/8) |
  | mean llm_calls | 1.000 (n=50) | 2.320 (n=50) |
  | p50 latency_ms | 2208 ms | 3167 ms |
  | p95 latency_ms | 3734 ms | 8002 ms |
  | mean tokens per question | 2333.560 (n=50) | 4577.300 (n=50) |
  | used_web | 0.000 (0/50) | 0.160 (8/50) |
  | structured_output_failures (failed attempts before success) | 0 (n=50) | 2 (n=50) |
  | items with >= 1 structured_output failure | 0.000 (0/50) | 0.040 (2/50) |
  | rate-limited attempts (not counted above) | 10 (n=50) | 0 (n=50) |
  | RAGAS faithfulness (prose-level grounding signal) | 0.922 (39) | 0.909 (39) |
  | RAGAS response_relevancy | 0.813 (39) | 0.823 (39) |
  | RAGAS context_precision (on contexts given to the generator) | 0.720 (42) | 0.781 (42) |
  | RAGAS context_recall (on contexts given to the generator) | 0.845 (42) | 0.821 (42) |
  
  ## single
  
  | Field | baseline-20261116-1050 | corrective-20261120-1852 |
  |---|---|---|
  | items | 28 | 28 |
  | answerable n | 28 | 28 |
  | correct (correctness = 2) | 0.893 (25/28) | 0.893 (25/28) |
  | correct or partial (correctness >= 1) | 0.929 (26/28) | 0.893 (25/28) |
  | mean correctness (0-2) | 1.821 (n=28) | 1.786 (n=28) |
  | citation_support (judged items) | 1.000 (26/26) | 0.962 (25/26) |
  | first-retrieval hit@5 (like-for-like retrieval) | 0.786 (22/28) | 0.786 (22/28) |
  | context_hit@5 (on contexts given to the generator) | 0.786 (22/28) | 0.750 (21/28) |
  | mean context_evidence_recall@5 (on contexts given to the generator) | 0.786 (n=28) | 0.750 (n=28) |
  | mean must_mention coverage (soft signal, D15) | 0.893 (n=28) | 0.893 (n=28) |
  | false_abstention | 0.071 (2/28) | 0.071 (2/28) |
  | abstention_correct (unanswerable) | - | - |
  | hallucinated (unanswerable) | - | - |
  | mean llm_calls | 1.000 (n=28) | 2.071 (n=28) |
  | p50 latency_ms | 2062 ms | 2942 ms |
  | p95 latency_ms | 3447 ms | 6515 ms |
  | mean tokens per question | 2399.107 (n=28) | 4311.429 (n=28) |
  | used_web | 0.000 (0/28) | 0.036 (1/28) |
  | structured_output_failures (failed attempts before success) | 0 (n=28) | 0 (n=28) |
  | items with >= 1 structured_output failure | 0.000 (0/28) | 0.000 (0/28) |
  | rate-limited attempts (not counted above) | 10 (n=28) | 0 (n=28) |
  | RAGAS faithfulness (prose-level grounding signal) | 0.908 (26) | 0.922 (26) |
  | RAGAS response_relevancy | 0.818 (26) | 0.827 (26) |
  | RAGAS context_precision (on contexts given to the generator) | 0.772 (28) | 0.848 (28) |
  | RAGAS context_recall (on contexts given to the generator) | 0.857 (28) | 0.857 (28) |
  
  ## multi
  
  | Field | baseline-20261116-1050 | corrective-20261120-1852 |
  |---|---|---|
  | items | 8 | 8 |
  | answerable n | 8 | 8 |
  | correct (correctness = 2) | 0.875 (7/8) | 0.750 (6/8) |
  | correct or partial (correctness >= 1) | 0.875 (7/8) | 0.875 (7/8) |
  | mean correctness (0-2) | 1.750 (n=8) | 1.625 (n=8) |
  | citation_support (judged items) | 1.000 (7/7) | 0.857 (6/7) |
  | first-retrieval hit@5 (like-for-like retrieval) | 0.875 (7/8) | 0.875 (7/8) |
  | context_hit@5 (on contexts given to the generator) | 0.875 (7/8) | 0.875 (7/8) |
  | mean context_evidence_recall@5 (on contexts given to the generator) | 0.500 (n=8) | 0.500 (n=8) |
  | mean must_mention coverage (soft signal, D15) | 0.875 (n=8) | 0.875 (n=8) |
  | false_abstention | 0.125 (1/8) | 0.125 (1/8) |
  | abstention_correct (unanswerable) | - | - |
  | hallucinated (unanswerable) | - | - |
  | mean llm_calls | 1.000 (n=8) | 2.000 (n=8) |
  | p50 latency_ms | 2772 ms | 3692 ms |
  | p95 latency_ms | 3610 ms | 4243 ms |
  | mean tokens per question | 2368.500 (n=8) | 4351.125 (n=8) |
  | used_web | 0.000 (0/8) | 0.000 (0/8) |
  | structured_output_failures (failed attempts before success) | 0 (n=8) | 0 (n=8) |
  | items with >= 1 structured_output failure | 0.000 (0/8) | 0.000 (0/8) |
  | rate-limited attempts (not counted above) | 0 (n=8) | 0 (n=8) |
  | RAGAS faithfulness (prose-level grounding signal) | 0.907 (7) | 0.827 (7) |
  | RAGAS response_relevancy | 0.817 (7) | 0.843 (7) |
  | RAGAS context_precision (on contexts given to the generator) | 0.479 (8) | 0.500 (8) |
  | RAGAS context_recall (on contexts given to the generator) | 0.688 (8) | 0.562 (8) |
  
  ## version
  
  | Field | baseline-20261116-1050 | corrective-20261120-1852 |
  |---|---|---|
  | items | 6 | 6 |
  | answerable n | 6 | 6 |
  | correct (correctness = 2) | 1.000 (6/6) | 1.000 (6/6) |
  | correct or partial (correctness >= 1) | 1.000 (6/6) | 1.000 (6/6) |
  | mean correctness (0-2) | 2.000 (n=6) | 2.000 (n=6) |
  | citation_support (judged items) | 1.000 (6/6) | 1.000 (6/6) |
  | first-retrieval hit@5 (like-for-like retrieval) | 0.833 (5/6) | 0.833 (5/6) |
  | context_hit@5 (on contexts given to the generator) | 0.833 (5/6) | 0.833 (5/6) |
  | mean context_evidence_recall@5 (on contexts given to the generator) | 0.750 (n=6) | 0.750 (n=6) |
  | mean must_mention coverage (soft signal, D15) | 1.000 (n=6) | 1.000 (n=6) |
  | false_abstention | 0.000 (0/6) | 0.000 (0/6) |
  | abstention_correct (unanswerable) | - | - |
  | hallucinated (unanswerable) | - | - |
  | mean llm_calls | 1.000 (n=6) | 2.000 (n=6) |
  | p50 latency_ms | 2430 ms | 3047 ms |
  | p95 latency_ms | 3420 ms | 3816 ms |
  | mean tokens per question | 2352.833 (n=6) | 4441.333 (n=6) |
  | used_web | 0.000 (0/6) | 0.000 (0/6) |
  | structured_output_failures (failed attempts before success) | 0 (n=6) | 0 (n=6) |
  | items with >= 1 structured_output failure | 0.000 (0/6) | 0.000 (0/6) |
  | rate-limited attempts (not counted above) | 0 (n=6) | 0 (n=6) |
  | RAGAS faithfulness (prose-level grounding signal) | 1.000 (6) | 0.948 (6) |
  | RAGAS response_relevancy | 0.784 (6) | 0.778 (6) |
  | RAGAS context_precision (on contexts given to the generator) | 0.798 (6) | 0.847 (6) |
  | RAGAS context_recall (on contexts given to the generator) | 1.000 (6) | 1.000 (6) |
  
  ## unanswerable
  
  | Field | baseline-20261116-1050 | corrective-20261120-1852 |
  |---|---|---|
  | items | 8 | 8 |
  | answerable n | 0 | 0 |
  | correct (correctness = 2) | - | - |
  | correct or partial (correctness >= 1) | - | - |
  | mean correctness (0-2) | - | - |
  | citation_support (judged items) | - | - |
  | first-retrieval hit@5 (like-for-like retrieval) | - | - |
  | context_hit@5 (on contexts given to the generator) | - | - |
  | mean context_evidence_recall@5 (on contexts given to the generator) | - | - |
  | mean must_mention coverage (soft signal, D15) | - | - |
  | false_abstention | - | - |
  | abstention_correct (unanswerable) | 1.000 (8/8) | 1.000 (8/8) |
  | hallucinated (unanswerable) | 0.000 (0/8) | 0.000 (0/8) |
  | mean llm_calls | 1.000 (n=8) | 3.750 (n=8) |
  | p50 latency_ms | 1822 ms | 6638 ms |
  | p95 latency_ms | 4181 ms | 8706 ms |
  | mean tokens per question | 2054.750 (n=8) | 5836.000 (n=8) |
  | used_web | 0.000 (0/8) | 0.875 (7/8) |
  | structured_output_failures (failed attempts before success) | 0 (n=8) | 2 (n=8) |
  | items with >= 1 structured_output failure | 0.000 (0/8) | 0.250 (2/8) |
  | rate-limited attempts (not counted above) | 0 (n=8) | 0 (n=8) |
  | RAGAS faithfulness (prose-level grounding signal) | - | - |
  | RAGAS response_relevancy | - | - |
  | RAGAS context_precision (on contexts given to the generator) | - | - |
  | RAGAS context_recall (on contexts given to the generator) | - | - |
  
  ## Changed questions (against baseline-20261116-1050)
  
  ### corrective-20261120-1852
  
  - q024: correctness 1 -> 0 (worse)
  - q034: correctness 2 -> 1 (worse)
  
  
  ## Paired
  
  Means over items scored in every compared run (n). A paired item is better or worse when the difference exceeds 0.2; the verdict is "no measurable difference" unless wins minus losses is 3 or more (D19).
  
  ### corrective-20261120-1852 against baseline-20261116-1050
  
  **Correctness verdict (primary): no measurable difference.** 0 items better, 2 worse, 40 unchanged, out of 42 answerable items (a direction needs a net of 3 items). The correctness row in the table is supporting detail; must_mention coverage is a soft signal (D15).
  
  | Metric | n | first mean | this mean | better | worse | verdict |
  |---|---|---|---|---|---|---|
  | correctness (0-2; abstained = 0) | 42 | 1.833 | 1.786 | 0 | 2 | no measurable difference |
  | context_evidence_recall@5 (on contexts given to the generator) | 42 | 0.726 | 0.702 | 0 | 1 | no measurable difference |
  | must_mention coverage (soft signal, D15) | 42 | 0.905 | 0.905 | 0 | 0 | no measurable difference |
  | RAGAS faithfulness (prose-level grounding signal) | 39 | 0.922 | 0.909 | 2 | 3 | no measurable difference |
  | RAGAS response_relevancy | 39 | 0.813 | 0.823 | 1 | 0 | no measurable difference |
  | RAGAS context_precision (on contexts given to the generator) | 42 | 0.720 | 0.781 | 3 | 1 | no measurable difference |
  | RAGAS context_recall (on contexts given to the generator) | 42 | 0.845 | 0.821 | 0 | 1 | no measurable difference |

- Changed questions (one line each; deciding branch and k-of-n grading from the corrective trace):
  - q024 | single | correctness 1 -> 0, citation_support 1 -> 0; not abstained in either | graded relevant | 1 of 5 (kept excerpt 1, "unordered updates in parallel supersteps"). Judge v2 rationale: the answer attributes the failure to inconsistent ordering instead of missing reducers. Gold evidence was not in the first retrieval (first-retrieval hit@5 0 in both runs).
  - q034 | multi | correctness 2 -> 1, citation_support 1 -> 0; not abstained in either | graded relevant | 4 of 5. Judge v2 rationale: the answer invents an "@update_state" decorator instead of graph.update_state(config, values). First-retrieval hit@5 1 in both runs.
  - No question changed on abstention.
- Observations (counts; noise rules D19):
  - False abstentions: baseline 3/42 (q008, q025, q029), corrective 3/42 (the same three items).
    - q008: first grading 2 of 5 relevant, route to generate, abstained at generation (not grading; human note). Gold evidence not in the first retrieval (first-retrieval hit@5 0 in both runs).
    - q025: 0 of 5 on both gradings, then web search (3 results: python/langgraph/interrupts, javascript/langgraph/graph-api-control-flow, python/langchain/structured-output); abstained. Gold evidence not in the first retrieval, so retrieval missed gold evidence (not grader strictness).
    - q029: 5 of 5 relevant, gold evidence at first-retrieval rank 1; abstained at generation.
    - Corrective false abstentions with 0 of n relevant on a first retrieval that held gold evidence (grader too strict): 0. Retrieval missed gold evidence: 1 (q025).
  - Unanswerable items: abstention_correct baseline 8/8, corrective 8/8; hallucinated 0/8 in both. Corrective unanswerables that reached web search: 7 of 8 (q043, q044, q045, q046, q048, q049, q050); q047 graded 1 of 5 relevant on the first try and abstained at generation.
  - Retrieval: first-retrieval hit@5 baseline 34/42, corrective 34/42 (like-for-like). Corrective context_hit@5 (on contexts given to the generator) 33/42. The one-item drop is q014: the grader marked the gold chunk (excerpt 2) not relevant ("Mentions entrypoint, not discrete step decorator") and kept excerpts 3 and 4; correctness did not change. Limitation: web chunks mostly get anchor "" or a "web:" doc_path, so they almost never match section-level gold evidence; context_hit@5 and context_evidence_recall@5 undercount web-supported answers. In this run no web-using item gave an answer (all 8 abstained), so the undercount affects no answered item here.
  - Web chunks and the pinned docs commit (D8): no answer cites a web chunk (all 8 web-using items abstained with no citations). 11 of the 20 web URLs were outside the ingested LangGraph Python corpus. Nothing to note further.
  - Identifiers named by the grader or rewriter that appear in neither the question nor any excerpt (retrieved chunk text, titles, headings, web contexts; case-insensitive search over identifier-like words). All are in rewritten queries of unanswerable items:
    - q043 "max_retry_time" (as in S2).
    - q044 "Neo4jCheckpointer" (compound of the question's "Neo4j" and "checkpointer").
    - q045 "WebSocketServer" (compound of the question's "WebSocket server").
    - q046 "max_checkpoints_per_thread".
    - q048 "export_graphql".
    - q049 "node_executor".
    - q050 "token_usage".
    - The search also flagged q008's grader reason "StateSnapshots". That is the plural of StateSnapshot, which appears 6 times in q008's excerpt 4, so it is not counted.
    - No grader reason on any answerable item named a new identifier.
  - The summary row "structured_output_failures 2 (items 2/50)" counts every failed attempt in failed_attempts.jsonl. Neither was a structured-output failure: q043's was a WebSearchError (Tavily ConnectionError) and q049's a Groq 400 json_validate_failed on the rewrite_query call. Both items succeeded on retry. The grading diagnostics (grading_failures, missing and invalid grades) were 0 on every item.
- Screenshot (Step 3.4): docs/screenshots/langsmith-baseline-vs-corrective.png, 197,022 bytes, saved by the human (comparison view of baseline-20261116-1050-r2 and corrective-20261120-1852). Confirmed present.

S3 additional facts (human request, 2026-11-21; read from the run folders and the LangSmith traces, no code, prompt or settings change)
- 1) Grader acceptance on the first retrieval:
  - 41 of 42 answerable items had at least 1 chunk marked relevant on the first retrieval. The exception is q025.
  - On 7 of those 41 the first retrieval missed all gold evidence (first_retrieval_hit@5 = 0): q008, q012, q018, q024, q031, q038, q039.
  - With min_relevant_chunks = 1, these items went straight to generate and never reached rewrite or web search.
  - Their corrective outcomes: q008 false abstention; q024 correctness 0; the other 5 judged as in the summary.
- 2) Rewrites:
  - 8 items were rewritten: q025, q043, q044, q045, q046, q048, q049, q050.
  - The second retrieval produced a relevant chunk on 0 of 8.
  - All 8 then went to web search.
- 3) q049:
  - The call was rewrite_query's structured RewrittenQuery call on gpt-oss-20b (json_schema, strict). It was not a grader call; the corrected Step 1 line says so.
  - Groq returned a 400 with error type "invalid_request_error" and code "json_validate_failed". Message: "Failed to validate JSON. Please adjust your prompt. See 'failed_generation' for more details."; failed_generation was empty.
  - The groq client did not retry it. A 400 is not retryable in groq/_base_client.py _should_retry.
  - The error ended the graph with an error event. The runner recorded a failed attempt and retried the whole item (eval_item_attempts 2), which completed on the second attempt.
- 4) q025, the only answerable item that fell back to web search:
  - Question: "What exception is raised when a node function outputs a list rather than a mapping?" Gold evidence: errors/INVALID_GRAPH_NODE_RETURN_VALUE.mdx, anchor "".
  - Baseline: false abstention, context_hit@5 0.
  - Corrective: first grading 0 of 5, then the query was rewritten to "NodeError exception raised for node output list instead of mapping". The second grading was also 0 of 5.
  - Web search returned 3 results, none of them the gold page:
    - https://docs.langchain.com/oss/python/langgraph/interrupts (maps to interrupts.mdx, anchor "")
    - https://docs.langchain.com/oss/javascript/langgraph/graph-api-control-flow (outside the corpus, web: doc_path)
    - https://docs.langchain.com/oss/python/langchain/structured-output (outside the corpus; its snippet is raw page JSX such as "_jsx(_components.code,...")
  - The generator abstained: false abstention, correctness 0, context_hit@5 0. Same outcome in both pipelines.
- 5) Grading drop behind context_hit@5 0.810 -> 0.786: 1 item, q014.
  - Gold evidence was in the first retrieval (excerpt 2). The grader marked it not relevant ("Mentions entrypoint, not discrete step decorator"), so it was not in the contexts given to the generator.
  - Correctness did not change against the baseline.

S3 final verification (2026-11-21, before commit)
- `py tasks.py lint`: "All checks passed!", "142 files already formatted".
- `py tasks.py test`: "243 passed, 1 deselected in 12.34s".
- `py tasks.py bundle-check`: "Total bundle size: 229.91 MB (limit: 400.00 MB)", exit 0.
- git status before staging: M docs/progress/M10-corrective-rag.md, M docs/progress/PROGRESS.md, M results/summary.md; untracked docs/audit/ (stays untracked), docs/screenshots/langsmith-baseline-vs-corrective.png, results/runs/corrective-20261120-1852/. data/processed/source.json unmodified.

S3 budget plan against measured use

| item | plan | measured |
|---|---|---|
| gpt-oss-20b | 105,000 (best) to 236,700 (worst) tokens, 50 to 150 requests | 145,923 tokens, 71 requests in cache/budget.json, including q043's failed first attempt (7,051 tokens) and q049's 0-token 400; 138,872 tokens over 66 calls in per_question.jsonl |
| gpt-oss-120b | about 116,700 to 130,000 tokens, at most 50 calls | 89,993 tokens, 50 calls |
| judge gemini-3.5-flash-lite | at most 42 calls, about 95,000 tokens | 39 calls, 68,706 tokens |
| RAGAS gemini-3.1-flash-lite | 729 to 756 requests, 2 days | 367 requests, 461,056 tokens, 1 day |
| embeddings gemini-embedding-001 | up to 100 (eval) plus 78 to 84 (RAGAS) | 61 (eval) plus 35 (RAGAS) |
| Tavily | at most 50 credits | 8 searches that returned results, plus q043's failed first attempt (a connection error, probably not billed) |
| days | at most 2 | 1 (2026-11-20 18:52Z to 20:47Z by the machine clock, plus the stop for the human decision) |

S3 deviations from the prompt
- The 8,000-token STOP was replaced after q008.
  - Human's reason: "it summed both models, but Groq's limit is 8,000 tokens per minute per model, and q008 stayed under it on each model (5,151 on gpt-oss-20b, 4,409 on gpt-oss-120b)".
  - New rules for the remaining items: record and report per-item tokens per model; STOP on any single call over 7,200 tokens, or on two rate-limit failures in a row for one item.
  - The first eval process was ended by hand after q008, and the same run folder was resumed. Only one corrective run folder exists.
- The baseline's current experiment is r2 (marked current), not r3 or later as the prompt expected; no r3 exists.
- The eval does not judge (D9), so `py tasks.py judge` was run on the corrective folder between Step 1 and Step 2.
- The ragas export wrote ragas_input.jsonl into the run folder. It is a harness file, as for the baseline, and is committed with the folder.
- The pre-approved throttle fix was not applied, because check (a) showed it was not needed.

S3 known issues and limitations
- The failed_attempts "stage" field is the last node_start before the error. rewrite_query and web_search emit node_start only in their return value, so a failure inside them is recorded as stage grade_documents (q043, q049).
- summary.md's structured_output_failures row counts every failed attempt, including ones that are not structured-output failures (q043, a WebSearchError).
- The TraceEvent error message is the class name only, so causes have to be read from LangSmith.
- TavilySearch does not retry a connection error with no HTTP status (q043).
- On 7 of the 8 rewrites (all unanswerables), the rewriter introduced identifiers that are in neither the question nor any excerpt. None of the 8 rewrites produced a relevant chunk.

Proposed follow-ups (S3; S2's list above still stands)
- Grader leniency on first retrieval. In 7 of 41 first-retrieval acceptances, no gold evidence was retrieved, yet min_relevant_chunks = 1 sent the item to generate. This is a candidate pre-registered ablation, not a change: fix the metric and the noise rule before running it.
- Rewriter identifier invention: 7 of 8 rewrites named identifiers in neither the question nor the excerpts (see the Step 3 observations). Prompt ideas belong to a later module and should be measured on the eval set.
- A 400 json_validate_failed on a structured grader or rewriter call (q049) ends the graph with an error event. In M12 that error event would reach API users unless the API handles it, for example with one retry of the call or a fallback route.
- Retry Tavily connection errors (status None) the same way as 5xx (q043).
- Record the failing node correctly in failed_attempts, either by emitting node_start before the call or by taking the node from the exception.
- Report structured_output_failures in summary.md separately from other failed attempts.
- Web snippets can be raw page markup (the q025 structured-output page). Consider cleaning web content before generation.

Handoff to M11
- Corrective cost, measured on 50 items:
  - Per item: mean 2.32 LLM calls and 4,577 tokens (baseline: 1.00 and 2,334).
  - Direct path: 2 calls and 2,700 to 5,600 Groq tokens. 4-call web path: 5,400 to 6,700 tokens.
  - Per run: gpt-oss-20b about 139,000 to 146,000 tokens, gpt-oss-120b about 90,000.
  - Largest single call: 5,151 tokens (gpt-oss-20b), 4,409 (gpt-oss-120b).
  - Latency: p50 3,167 ms, p95 8,002 ms.
- Grader behaviour:
  - It accepts at least 1 chunk on the first retrieval for 41 of 42 answerable items, including 7 whose first retrieval holds no gold evidence.
  - It rejected the gold chunk on 1 item (q014).
  - It graded 0 of 5 on both retrievals for 7 of 8 unanswerables and for q025.
  - Rewrites never rescued an item (0 of 8).
  - Malformed grading: 0 of 50 items.
- Throttle:
  - Estimates are per model, and wait_for proceeds once the per-minute window is empty.
  - A single call above 7,200 tokens would exceed 8,000 x 0.9 and would still be sent after an empty window.
  - Self-RAG's extra calls (generation grading) add to gpt-oss-20b usage.
- Groq 400s: a structured call on gpt-oss-20b can fail with 400 json_validate_failed (q049, on rewrite_query). The client does not retry it. The eval runner retries the item, but in M12 users would see an error event.
- Quota state after S3 (2026-11-20 about 20:47Z by the machine clock):
  - The gpt-oss-20b and gpt-oss-120b buckets drain at 2.315 tokens/s from about 146,000 and 90,000.
  - Gemini, Pacific day 2026-11-20: judge 39/500, RAGAS LLM 367/500, embeddings 100/1000.
  - A full self-RAG run should start after the Groq buckets have drained.
- Compare: baseline-20261116-1050 against corrective-20261120-1852 shows no measurable difference on any paired metric. M11 compares against both with `py tasks.py compare results/runs/baseline-20261116-1050 results/runs/corrective-20261120-1852 <self-rag run>`.
- `py tasks.py ingest` was not run in S3, and data/processed/source.json is unmodified.
