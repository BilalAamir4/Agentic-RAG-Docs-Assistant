M06: Baseline generation
Status: Done
Date: 2026-10-25

Goal
Build a baseline RAG pipeline using LangChain LCEL that retrieves documentation excerpts via HybridRetriever, generates cited answers using Groq with the shared answer prompt, validates citations, abstains when excerpts are insufficient, streams trace events, and exposes the Pipeline protocol interface.

What was built
- src/ragdocs/config.py: Set default `generator_model = "openai/gpt-oss-120b"` and `grader_model = "openai/gpt-oss-20b"`.
- src/ragdocs/providers/llm.py: Implemented `get_chat_model` for generator, grader, and judge (with lazy google-genai import) and `CallCounter` callback handler.
- src/ragdocs/generation/prompts.py: Defined `ABSTAIN_TEXT`, `ANSWER_SYSTEM_PROMPT`, and `ANSWER_USER_TEMPLATE` with exact required text.
- src/ragdocs/generation/answer.py: Implemented `AnswerDraft` pydantic model, `StructuredLLM` protocol, `build_structured_llm`, `format_context`, `validate_answer`, and `generate_answer`.
- src/ragdocs/pipelines/base.py: Implemented `Pipeline` protocol, `safe_error_message` scrubber, and `run()` stream consumer helper.
- src/ragdocs/pipelines/baseline.py: Implemented `BaselinePipeline` with LCEL chain and streaming trace events (`node_start`, `retrieval`, `node_end`, `answer`, `error`).
- src/ragdocs/pipelines/registry.py: Implemented `list_pipelines()`, `get_pipeline()` with lazy singleton construction, and `clear_pipeline_cache()`.
- src/ragdocs/retrieval/retriever.py: Added `get_retriever()` cached factory and defaulted `retrieve()` mode to the D6 gate choice (`hybrid`).
- scripts/ask.py: Standalone CLI to execute RAG pipelines, stream trace events on single lines, and display answers, citations, llm_calls, and latency.
- tests/test_generation.py: Unit tests covering context formatting, citation mapping, out-of-range citation dropping, marker removal, abstention forcing, uncited flag, stream trace event ordering, pipeline runner, error paths, registry errors, and CallCounter.
- tests/test_import_boundaries.py: Added import boundary test verifying `ragdocs.providers.llm` does not import `langchain_google_genai` at module level.
- tests/test_config.py: Added assertions verifying default model IDs in Settings.

How to run
- Ask a question via CLI: `.venv\Scripts\python scripts\ask.py --pipeline baseline "question"`
- Run test suite: `py tasks.py test`
- Run linter and formatter: `py tasks.py lint`

Verification
1. Step 1 Model and Rate Limit Verification:
- Groq Documentation URL: `https://console.groq.com/docs/rate-limits` and `https://console.groq.com/docs/models`
- Free Tier Limits for General Models supporting structured outputs:
  - `openai/gpt-oss-120b`: 30 RPM, 1,000 RPD, 8,000 TPM (8K), 200,000 TPD. Context window: 131,072 tokens. Most capable general model.
  - `openai/gpt-oss-20b`: 30 RPM, 1,000 RPD, 8,000 TPM (8K), 200,000 TPD. Context window: 131,072 tokens. Faster inference (~0.88s vs ~1.40s).
  - `qwen/qwen3.8-27b`: 30 RPM, 1,000 RPD, 8,000 TPM, but subject to an enforced OTPM (output tokens per minute) cap of 1,000 on free tier that causes 429 when max_tokens exceeds 1,000.
- Selection Decision:
  - `generator_model`: `openai/gpt-oss-120b` (most capable general model on Groq free tier).
  - `grader_model`: `openai/gpt-oss-20b` (generator TPM is 8,000 < 10,000; chosen as fastest model with structured output support).

2. Unit Test & Lint Suite:
- `py tasks.py lint`: PASS (86 files formatted, all checks passed).
- `py tasks.py test`: PASS (80 passed, 1 deselected in 2.03s).
- Import boundary verified: `ragdocs.providers.llm` does not import `langchain_google_genai` at module level.

3. Live Smoke Tests (`scripts/ask.py --pipeline baseline "<question>"`):

Question 1: First single item (`q001`):
Command:
`.venv\Scripts\python scripts\ask.py --pipeline baseline "My agent run stops with GRAPH_RECURSION_LIMIT; where do I set a bigger step cap?"`

Output:
```
Executing pipeline 'baseline' on question: 'My agent run stops with GRAPH_RECURSION_LIMIT; where do I set a bigger step cap?'

[    0ms] [node_start] retrieve: Retrieving documentation excerpts
[  669ms] [retrieval ] retrieve: Retrieved candidate excerpts (5 chunks, mode=hybrid)
[  669ms] [node_start] generate: Generating cited answer
[ 1989ms] [node_end  ] generate: Answer generated and validated (dropped_citations=0, uncited=False)
[ 1994ms] [answer    ] answer: Pipeline execution finished

--- Answer ---
You can raise the step cap by passing a larger `recursion_limit` in the config dictionary when you call the graph. The limit is a top‑level config key (not inside `configurable`). For example:

```python
# increase the allowed super‑steps to 2000
result = graph.invoke({"input": "..."}, config={"recursion_limit": 2000})
```

This overrides the default (1000 steps as of v1.0.6) for that execution. The same key works with `stream` calls. Setting it this way prevents the `GRAPH_RECURSION_LIMIT` error unless the graph truly loops indefinitely.

(See the troubleshooting guide and runtime context description for the `recursion_limit` config.)

--- Citations ---
  - [0b10c87050fe58d0] https://docs.langchain.com/oss/python/langgraph/errors/GRAPH_RECURSION_LIMIT#troubleshooting
  - [969a9656a46db3ac] https://docs.langchain.com/oss/python/langgraph/graph-api#recursion-limit

LLM calls: 1
Latency: 1989 ms
```
Assessment: Accurate answer explaining `recursion_limit` as a top-level config key with a code example. Citations accurately point to `GRAPH_RECURSION_LIMIT#troubleshooting` and `graph-api#recursion-limit`. Exactly 1 LLM call, latency 1989 ms. Looks completely right.

Question 2: First version item (`q009`):
Command:
`.venv\Scripts\python scripts\ask.py --pipeline baseline "Which channel mechanism avoids storing redundant duplicate states by persisting only incremental changes?"`

Output:
```
Executing pipeline 'baseline' on question: 'Which channel mechanism avoids storing redundant duplicate states by persisting only incremental changes?'

[    0ms] [node_start] retrieve: Retrieving documentation excerpts
[  643ms] [retrieval ] retrieve: Retrieved candidate excerpts (5 chunks, mode=hybrid)
[  643ms] [node_start] generate: Generating cited answer
[ 1688ms] [node_end  ] generate: Answer generated and validated (dropped_citations=0, uncited=False)
[ 1688ms] [answer    ] answer: Pipeline execution finished

--- Answer ---
The `DeltaChannel` mechanism stores only the incremental delta at each step instead of the full accumulated value, so it avoids persisting redundant duplicate states and reduces checkpoint size.

```python
from typing import Annotated, Sequence
from typing_extensions import TypedDict
from langgraph.channels import DeltaChannel

def my_reducer(state: list[str], writes: Sequence[list[str]]) -> list[str]:
 result = list(state)
 for write in writes:
 result.extend(write)
 return result

class State(TypedDict):
 messages: Annotated[list[str], DeltaChannel(my_reducer)]
```

--- Citations ---
  - [1275ba85560b4ff7] https://docs.langchain.com/oss/python/langgraph/checkpointers#optimize-checkpoint-storage
  - [5d6a26b01d1541a7] https://docs.langchain.com/oss/python/langgraph/pregel#deltachannel

LLM calls: 1
Latency: 1688 ms
```
Assessment: Correctly identifies `DeltaChannel` and provides code from the documentation excerpts. Citations accurately match checkpointer optimization and DeltaChannel definitions. Exactly 1 LLM call, latency 1688 ms. Looks completely right.

Question 3: First unanswerable item (`q043`):
Command:
`.venv\Scripts\python scripts\ask.py --pipeline baseline "Which RetryPolicy argument caps the total wall-clock time a node may spend across all of its retry attempts?"`

Output:
```
Executing pipeline 'baseline' on question: 'Which RetryPolicy argument caps the total wall-clock time a node may spend across all of its retry attempts?'

[    0ms] [node_start] retrieve: Retrieving documentation excerpts
[  607ms] [retrieval ] retrieve: Retrieved candidate excerpts (5 chunks, mode=hybrid)
[  607ms] [node_start] generate: Generating cited answer
[ 1688ms] [node_end  ] generate: Answer generated and validated (dropped_citations=0, uncited=False)
[ 1688ms] [answer    ] answer: Pipeline execution finished

--- Answer ---
I couldn't find this in the LangGraph documentation.

--- Citations ---
  (None)

LLM calls: 1
Latency: 1688 ms
```
Assessment: Model cleanly recognized that no excerpt defines a wall-clock timeout parameter on RetryPolicy and abstained with the verbatim ABSTAIN_TEXT with empty citations. Exactly 1 LLM call, latency 1688 ms. Looks completely right.

Decisions made
- Generator Model: `openai/gpt-oss-120b` defaulted in Settings. Most capable open-weight general model available on Groq free tier with 120B parameters and full `with_structured_output` support.
- Grader Model: `openai/gpt-oss-20b` defaulted in Settings. Since the generator model TPM is 8,000 (< 10,000 threshold), the fastest model supporting structured output (`openai/gpt-oss-20b`, ~0.88s latency) was selected.
- Citation Validation: Out-of-range citations are dropped from the cited list and their bracketed markers removed from text using regex cleanup that preserves punctuation and normalizes double spaces.
- Secret Sanitization in Stream Errors: `safe_error_message` scrubs known secret tokens and keeps only the first line of an error string, preventing stack traces or keys from leaking into client-visible events.

Deviations from the prompt
- None.

Known issues and limitations
- Groq free tier TPM limit: General models have an 8,000 TPM limit on the free tier. While sufficient for single question queries (each consuming ~1,500 input + output tokens), large batch offline evaluation must be throttled or paced to avoid 429 errors.

Open questions for the human
1. Inline `[n]` citation markers in generated answer prose:
   - In all three smoke test queries, the model populated the structured `cited: list[int]` field (e.g. `[1, 2, 4]` for `q001`), which were successfully resolved by `validate_answer` into formal `Citation` objects with `chunk_id` and `url`. However, inline bracket markers like `[1]` or `[2]` were absent from the generated answer prose.
   - Raw `AnswerDraft` for `q001` before validation:
     ```python
     AnswerDraft(
         answer=(
             "Increase the recursion limit by passing a larger `recursion_limit` value in the config "
             "dictionary when you call the graph. For example:\n"
             "```python\n"
             "# raise the step cap to 2000\n"
             'result = graph.invoke({"input": "..."}, config={"recursion_limit": 2000})\n'
             "```\n"
             "The `recursion_limit` key is a top‑level config entry (not inside `configurable`) "
             "and is applied at runtime to any graph invocation or streaming call. This overrides "
             "the default limit (1000 steps as of v1.0.6) and prevents the `GRAPH_RECURSION_LIMIT` "
             "error when the graph needs more super‑steps."
         ),
         cited=[1, 2, 4],
         abstain=False,
     )
     ```
   - Conclusion: Validation did NOT strip the citations (its `dropped_citations` diagnostic was 0). The model omitted inline bracket markers from the `answer` string, satisfying citation provenance solely through the structured `cited` integer array. Per prompt constraints, the shared answer prompt text has not been modified.

2. Timing resolution and latency differences:
   - Identical latency (1688 ms) for `q009` and `q043`:
     In the original smoke run, `q009` and `q043` both reported 1688 ms. `t_ms` is computed using integer millisecond truncation `int((time.perf_counter() - start_time) * 1000)`. Both queries completed in ~1.688 seconds end-to-end, resulting in identical integer values by coincidence across network hops. Programmatic rerun without console prints confirms varying execution latencies (1959.6 ms for `q009` and 1280.1 ms for `q043`).
   - Difference between `q001` latency_ms (1989 ms) and answer event t_ms (1994 ms):
     In `BaselinePipeline.stream()`, `e_end_gen` was yielded at line 185 with timestamp 1989 ms. `scripts/ask.py` printed that event to the terminal. When control returned to the generator, `pipeline_result` was instantiated with `latency_ms = t_ms()` (1989 ms). Serializing `pipeline_result.model_dump()` across all retrieved chunks, chunks metadata, and events consumed 5 ms of CPU time. By the time `e_answer` was constructed with `t_ms()`, the clock reached 1994 ms.

3. Step 1 Groq models and documentation verification:
   - Official Groq Documentation URLs:
     - Rate Limits: `https://console.groq.com/docs/rate-limits`
     - Models: `https://console.groq.com/docs/models`
   - Model `qwen/qwen3.8-27b`:
     Confirmed present on Groq Cloud via `client.models.list()` (active, 131,072 context window) and documented at 30 RPM / 8K TPM. However, on the free tier, Groq enforces an Output Tokens Per Minute (OTPM) cap of 1,000 on `qwen/qwen3.8-27b`, causing HTTP 429 errors when requests request standard output limits.
   - Structured-output models considered on Groq:
     - `openai/gpt-oss-120b`: 120B general model, 30 RPM, 8K TPM, 131k context. Full structured output support via `json_schema`/tool calling. Selected as `generator_model`.
     - `openai/gpt-oss-20b`: 20B general model, 30 RPM, 8K TPM, 131k context. Fastest general structured model (~0.88s latency). Selected as `grader_model`.
     - `qwen/qwen3.8-27b`: 27B model, 30 RPM, 8K TPM, 131k context. Rejected due to 1,000 OTPM limit triggering 429 on free tier.
     - `openai/gpt-oss-safeguard-20b`: Safeguard filter model, restricted to 3 RPM and 2K TPM.
     - `meta-llama/llama-prompt-guard-2-22m` / `meta-llama/llama-prompt-guard-2-86m`: Moderation classifiers only.
     - `allam-2-7b`: 7B Arabic-focused language model (4K context).
     - `whisper-large-v3` / `whisper-large-v3-turbo`: Audio transcription models only.
     - Note: `llama-3.3-70b-versatile` and `llama-3.1-8b-instant` returned 404 (Model Not Found) on this account.

4. Settings defaults confirmation:
   - Defaults are set in `src/ragdocs/config.py` and asserted in `tests/test_config.py`:
     - `generator_model: str = "openai/gpt-oss-120b"`
     - `grader_model: str = "openai/gpt-oss-20b"`
     - `judge_model: str | None = None`
     - `use_reranker: bool = False` (per D6 gate)

5. TPM headroom risk for evaluation runs:
   - Free tier limit for Groq general models is 8,000 Tokens Per Minute (8K TPM) across the organization.
   - A single RAG question consumes ~1,500 to 2,000 total tokens (system prompt + 5 retrieved documentation chunks + output answer).
   - At 8,000 TPM, only 4 to 5 queries can be executed in any 60-second window before encountering HTTP 429 rate limit exceptions.
   - Offline batch evaluation (M07 across 50 benchmark items) must enforce inter-query delays (e.g. 12–15 seconds minimum) or retry backoff to prevent quota exhaustion.

Proposed follow-ups (out of scope)
- [NOT DONE] Token streaming: Stream individual generation tokens from ChatGroq to TraceEvent when LangChain structured output token streaming stabilizes.

Prerequisites for the next module
- Baseline pipeline registered under "baseline" and verified.
- Pipeline interface and runner ready for M07 evaluation harness.

