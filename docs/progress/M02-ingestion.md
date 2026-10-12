M02: Docs ingestion and chunking
Status: Done
Date: 2026-10-12

Goal
Produce data/processed/chunks.jsonl (one Chunk per line), data/processed/source.json and data/processed/stats.md from a pinned commit, through `py tasks.py ingest`, deterministically.

Research findings (STEP 1)
1. Documentation Source and URL Mapping:
   - Source repository: `https://github.com/langchain-ai/docs` (LangChain consolidated docs repository hosting Mintlify sources).
   - Docs root directory: `src/oss/langgraph`
   - File formats: MDX (`.mdx`, 42 files) and Markdown (`.md`, 1 file: `frontend/overview.md`). No executable notebooks.
   - Pinned commit SHA: `a6e223d2f67558caa20589a03443e918b582943b` (HEAD of `main`).
   - Public base URL: `https://docs.langchain.com/oss/python/langgraph`
   - Path mapping rule: `src/oss/langgraph/<rel_path>` stripped of file extension (`.mdx` or `.md`) appended to `https://docs.langchain.com/oss/python/langgraph/`.
   - Verified on 5 pages with curl.exe returning HTTP 200:
     - `https://docs.langchain.com/oss/python/langgraph/overview` -> 200
     - `https://docs.langchain.com/oss/python/langgraph/quickstart` -> 200
     - `https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph` -> 200
     - `https://docs.langchain.com/oss/python/langgraph/errors/GRAPH_RECURSION_LIMIT` -> 200
     - `https://docs.langchain.com/oss/python/langgraph/agentic-rag` -> 200

2. Markup Conventions Handled:
   - Frontmatter fields: e.g. `title`, `sidebarTitle`, `description`, `keywords`, `boost` in `src/oss/langgraph/overview.mdx`.
   - MDX imports: e.g. `import ConnectDocsMcpPrompt from '/snippets/connect-docs-mcp-prompt.mdx';` in `quickstart.mdx`.
   - JSX components: e.g. `<Expandable title="...">`, `<CodeGroup>`, `<Tip>`, `<Icon icon="download" size={20} />` in `overview.mdx`. Tags removed, inner text preserved.
   - Language-conditional blocks: `:::python` ... `:::` unwrapped; `:::js` ... `:::` and `:::javascript` ... `:::` stripped.
   - Code fences: kept verbatim with language tags (e.g. ````bash pip ... ```` and ````python ... ````).
   - Snippet includes: rendered via imported JSX tags (e.g. `<ConnectDocsMcpPrompt />`), removed along with self-closing tags.
   - Heading anchors: verified on 3 headings in live HTML:
     - `## Acknowledgements` -> `id="acknowledgements"` on `https://docs.langchain.com/oss/python/langgraph/overview`
     - `## Core benefits` -> `id="core-benefits"` on `https://docs.langchain.com/oss/python/langgraph/overview`
     - `### 1. Define tools and model` -> `id="1-define-tools-and-model"` on `https://docs.langchain.com/oss/python/langgraph/quickstart`
     Slug rule: strip tags, lowercase, remove non-alphanumerics except spaces/hyphens, replace spaces with hyphens, deduplicate on collision with `-2`, `-3`.

3. Page Scope:
   - In-scope: 41 pages (conceptual, guides, how-tos, tutorials, error explanations, and frontend integration).
   - Excluded:
     - 2 changelogs in `src/oss/langgraph`: `changelog-js.mdx`, `changelog-py.mdx`.
     - Auto-generated API references: `src/oss/reference/langgraph-python.mdx`, `src/oss/reference/langgraph-javascript.mdx`.
     - JavaScript-only pages: `src/oss/javascript/*`.
     - Non-page snippet files: `src/snippets/*` (100+ files).
     - External product documentation in repo: `langsmith/*`, `oss/deepagents/*`, `oss/langchain/*`.

What was built
- `src/ragdocs/ingest/fetch.py`: shallow clone fetcher with `-c core.longpaths=true` and idempotent commit checking.
- `src/ragdocs/ingest/parse.py`: frontmatter parser and markdown/MDX cleaner producing `ParsedDocument`.
- `src/ragdocs/ingest/chunk.py`: section splitter, merger (<80 tokens), paragraph boundary splitter (>450 tokens), and Chunk builder.
- `scripts/ingest.py`: CLI executing fetch, parse, and chunk pipelines, writing `chunks.jsonl`, `source.json`, and `stats.md`.
- `src/ragdocs/config.py`: updated default `docs_domain = "docs.langchain.com"`.
- `tasks.py`: implemented `cmd_ingest` running `scripts/ingest.py` with pinned constants.
- `tools/sample_chunks.py`: standalone chunk sampler displaying random chunks deterministically.
- `tests/fixtures/sample_guide.md`: markdown fixture testing frontmatter, conditionals, heading hierarchy, small sections, and code fences.
- `tests/test_chunk.py`: unit tests covering chunking, splitting, merging, formatting, and stability invariants.
- `tests/test_config.py`: updated `docs_domain` assertion to match new default.
- `data/processed/chunks.jsonl`: 553 deterministic documentation chunks.
- `data/processed/source.json`: corpus provenance metadata.
- `data/processed/stats.md`: chunk and token distribution statistics.
- `docs/progress/M02-ingestion.md`: module tracking file.

How to run
- Ingestion pipeline: `py tasks.py ingest`
- Unit tests: `py tasks.py test`
- Lint checks: `py tasks.py lint`
- Chunk sampling: `.venv\Scripts\python tools/sample_chunks.py --seed 7 -n 5`
- Checksum validation: `py tasks.py hash data/processed/chunks.jsonl`

Verification
1. Unit tests (`py tasks.py test`):
   ```text
   ..........................                                               [100%]
   26 passed in 1.00s
   ```
2. Lint checks (`py tasks.py lint`):
   ```text
   All checks passed!
   36 files already formatted
   Running ruff check...
   Running ruff format --check...
   ```
3. Determinism check (`chunks.jsonl` hash identical across two successive runs):
   Run 1:
   ```text
   f3614b3f74d9f5ff1a4213937132e9928e7b1904992fbee36092be3bbe046bc5  data/processed/chunks.jsonl
   ```
   Run 2:
   ```text
   f3614b3f74d9f5ff1a4213937132e9928e7b1904992fbee36092be3bbe046bc5  data/processed/chunks.jsonl
   ```
4. One-line validation check:
   ```text
   .venv\Scripts\python -c "import json, sys; sys.path.insert(0, 'src'); from ragdocs.schemas import Chunk; lines = [json.loads(line) for line in open('data/processed/chunks.jsonl', encoding='utf-8')]; validated = [Chunk.model_validate(c) for c in lines]; print(f'Validated {len(validated)}/{len(lines)} chunks as Chunk models successfully.')"
   Validated 553/553 chunks as Chunk models successfully.
   ```
5. Balanced code fences check:
   ```text
   .venv\Scripts\python -c "import json; chunks = [json.loads(l) for l in open('data/processed/chunks.jsonl', encoding='utf-8')]; bad = [c['chunk_id'] for c in chunks if sum(1 for line in c['text'].splitlines() if line.strip().startswith('\x60\x60\x60')) % 2 != 0]; print(f'Unbalanced chunks: {len(bad)} / {len(chunks)}')"
   Unbalanced chunks: 0 / 553
   ```
6. Sampled chunks output (`tools/sample_chunks.py --seed 7 -n 5`):
   ```text
   === Sample 1/5 ===
   Title:        Quickstart
   Heading path: ['4. Define agent']
   URL:          https://docs.langchain.com/oss/python/langgraph/quickstart#4-define-agent
   Tokens:       598
   Text (first 400 chars):
   ```python
   # Step 1: Define tools and model

   from langchain.tools import tool
   from langchain.chat_models import init_chat_model


   model = init_chat_model(
       "claude-sonnet-4-6",
       temperature=0
   )


   # Define tools
   @tool
   def multiply(a: int, b: int) -> int:
       """Multiply `a` and `b`.

       Args:
           a: First int
           b: Second int
       """
       return a * b


   @tool
   def add(a: int, b: int) -
   --------------------------------------------------
   === Sample 2/5 ===
   Title:        Fault tolerance
   Heading path: ['Error handling']
   URL:          https://docs.langchain.com/oss/python/langgraph/fault-tolerance#error-handling
   Tokens:       368
   Text (first 400 chars):
   Requires `langgraph>=1.2`.



   An error handler runs after a node fails and all retries are exhausted. It receives the current state and can update it or route to a different node using @[`Command`]. This is useful for compensation flows (Saga patterns) where you want to recover gracefully rather than abort the entire graph.

   Pass `error_handler=` to @[`add_node`]:

   ```python
   from langgraph.errors 
   --------------------------------------------------
   === Sample 3/5 ===
   Title:        Thinking in LangGraph
   Heading path: ['Step 4: Build your nodes', 'Handle errors appropriately']
   URL:          https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph#handle-errors-appropriately
   Tokens:       448
   Text (first 400 chars):
   ```python
       from langgraph.types import Command


       def execute_tool(state: State) -> Command[Literal["agent", "execute_tool"]]:
           try:
               result = run_tool(state['tool_call'])
               return Command(update={"tool_result": result}, goto="agent")
           except ToolError as e:
               # Let the LLM see what went wrong and try again
               return Command(
               
   --------------------------------------------------
   === Sample 4/5 ===
   Title:        Application structure
   Heading path: []
   URL:          https://docs.langchain.com/oss/python/langgraph/application-structure
   Tokens:       163
   Text (first 400 chars):
   A LangGraph application consists of one or more graphs, a configuration file (`langgraph.json`), a file that specifies dependencies, and an optional `.env` file that specifies environment variables.

   This guide shows a typical structure of an application and shows you how to provide the required configuration to deploy an application with LangSmith Deployment.


   LangSmith Deployment is a managed h
   --------------------------------------------------
   === Sample 5/5 ===
   Title:        Checkpointers
   Heading path: ['Get and update state', 'Get state history']
   URL:          https://docs.langchain.com/oss/python/langgraph/checkpointers#get-state-history
   Tokens:       563
   Text (first 400 chars):
   ```
   [
       StateSnapshot(
           values={'foo': 'b', 'bar': ['a', 'b']},
           next=(),
           config={'configurable': {'thread_id': '1', 'checkpoint_ns': '', 'checkpoint_id': '1ef663ba-28fe-6528-8002-5a559208592c'}},
           metadata={'source': 'loop', 'writes': {'node_b': {'foo': 'b', 'bar': ['b']}}, 'step': 2},
           created_at='2024-08-29T19:19:38.821749+00:00',
           parent_config={'co
   --------------------------------------------------
   ```
7. Live URL & Anchor verification:
   - `curl.exe -s -o NUL -w "%{http_code} https://docs.langchain.com/oss/python/langgraph/quickstart#4-define-agent\n" https://docs.langchain.com/oss/python/langgraph/quickstart` -> HTTP 200, anchor `id="4-define-agent"` confirmed present.
   - `curl.exe -s -o NUL -w "%{http_code} https://docs.langchain.com/oss/python/langgraph/fault-tolerance#error-handling\n" https://docs.langchain.com/oss/python/langgraph/fault-tolerance` -> HTTP 200, anchor `id="error-handling"` confirmed present.
   - `curl.exe -s -o NUL -w "%{http_code} https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph#handle-errors-appropriately\n" https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph` -> HTTP 200, anchor `id="handle-errors-appropriately"` confirmed present.
8. Stats numbers (`data/processed/stats.md`):
   - Page count: 41
   - Chunk count: 553
   - Chunks with code: 396
   - Token percentiles: p10: 108.0, p50: 268.0, p90: 438.8, max: 1870
   - Chunks over 450 tokens: 33

Decisions made
- Pinned commit `a6e223d2f67558caa20589a03443e918b582943b` from official docs repository `https://github.com/langchain-ai/docs`.
- Docs root configured as `src/oss/langgraph` representing in-scope LangGraph Python documentation pages.
- Docs public base URL set to `https://docs.langchain.com/oss/python/langgraph`.

Deviations from the prompt
None.

Known issues and limitations
None.

Open questions for the human
None.

Proposed follow-ups (out of scope)
None.

Prerequisites for the next module
M02 complete; chunks.jsonl, source.json, and stats.md are committed. Ready for M03 eval set creation.
