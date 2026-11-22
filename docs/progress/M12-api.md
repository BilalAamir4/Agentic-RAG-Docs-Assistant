M12: Streaming API
Status: Done
Date: 2026-11-22

Goal
Session 1 (sections up to "S2 handoff"): the building blocks of the public streaming API, tested without network access. Session 2 writes POST /api/ask (streaming body), the local runner and the live checks. Module prompt: "M12 (1/2): API building blocks", given by the human on 2026-11-22.

What was built
- src/ragdocs/api/sse.py (new): format_event, ping, SSE_HEADERS, SSE_MEDIA_TYPE.
- src/ragdocs/api/models.py (new): AskRequest, QuestionError, validate_question, the exact error strings.
- src/ragdocs/api/ratelimit.py (new): LimitResult, RateLimiter, client_key, client_ip, build_redis, UpstashRateLimiter, DisabledRateLimiter, get_rate_limiter, rate_limiter_dependency, reset_rate_limiter_state.
- src/ragdocs/api/startup.py (new): validate_runtime_settings.
- src/ragdocs/api/preflight.py (new): ask_preflight, body_size_guard, BodyTooLarge, validation_message, error_response.
- src/ragdocs/api/app.py: lifespan (calls validate_runtime_settings), exception handlers (RequestValidationError, QuestionError, BodyTooLarge, Exception), GET /api/pipelines. GET /api/deps-probe unchanged (its comment now says M14 removes it).
- src/ragdocs/config.py: new fields (Step 2); duplicate tavily_api_key line removed.
- .env.example: new variables; RAGDOCS_ENV now "local" (an empty value failed validation, the M07 follow-up).
- tools/sse_probe.py (new): standalone SSE probe.
- tests/test_api_blocks.py (new, 41 tests); tests/test_config.py (2 assertions, see Deviations).
- docs/DECISIONS.md: D28. docs/progress/PROGRESS.md, M11-self-rag.md: the M11 hash.

How to run
- `py tasks.py test`, `py tasks.py lint`, `py tasks.py bundle-check`.
- After S2: `.venv\Scripts\python tools\sse_probe.py --question "..." --pipeline self_rag`.

Step 0
- `git log -1 --format=%H v2-agentic`: 56a5043633f81822900d2e9cf6856f6db2059f80. Written into the PROGRESS.md M11 row and the M11 file header.
- `git status` before any edit: clean.

Step 1: verification (paths under .venv/Lib/site-packages)
Installed versions (importlib.metadata): fastapi 0.143.0, starlette 1.7.0, uvicorn 0.54.0, httpx 0.28.1, upstash-redis 1.8.0, upstash-ratelimit 1.2.0, langchain-groq 1.1.3, groq 0.37.1, langsmith 0.14.7.

a) requirements.txt: fastapi==0.143.0, httpx==0.28.1, upstash-redis==1.8.0 and upstash-ratelimit==1.2.0 are pinned runtime lines. starlette is only a dependency of fastapi (1.7.0). uvicorn==0.54.0 is in requirements-dev.txt only (Vercel supplies its own ASGI server). httpx is runtime, so tools/sse_probe.py runs in the dev venv. No stop condition.

b) upstash-redis 1.8.0 (upstash_redis/client.py, http.py, commands.py)
- Sync client: `Redis(url, token, rest_encoding="base64", rest_retries=1, rest_retry_interval=3, allow_telemetry=True, read_your_writes=True)`; `Redis.from_env()` reads UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN.
- `incr(key)` returns the new integer value; `expire(key, seconds, nx=, xx=, gt=, lt=)` returns the REST result (1 when set).
- Errors: a REST reply with an "error" field raises upstash_redis.errors.UpstashError (http.py format_response). Network failures raise the httpx exception (after the retries; http.py execute re-raises last_error). An auth failure comes back as an error reply and so also raises UpstashError. The limiter catches Exception, so it does not depend on the class.
- Important: SyncHttpClient builds `httpx.Client(timeout=None)` (http.py) and, with the default rest_retries=1, sleeps 3 s and retries once. The client has no timeout parameter, so an unreachable Upstash host could hang until the function limit. build_redis (ratelimit.py) therefore passes rest_retries=0 and sets `redis._http._client.timeout` to Settings.upstash_timeout_s (3 s). That touches a private attribute; a test builds a real UpstashRateLimiter from fake settings to catch a future rename.

c) upstash-ratelimit 1.2.0 (limiter.py, ratelimit.py)
- A plain fixed window exists: `FixedWindow(max_requests, window, unit="s")`, wrapped as `Ratelimit(redis, limiter, prefix="@upstash/ratelimit")`. No stop condition.
- `Ratelimit.limit(identifier, rate=1)` returns `Response(allowed: bool, limit: int, remaining: int, reset: float)`. reset is an absolute Unix timestamp in seconds (limiter.py: `ms_to_s((curr_window + 1) * window_ms)`; the docstring says "Unix timestamp in seconds when the limits are reset"). Windows are aligned to the epoch, not to the first request. Retry-after is therefore `max(1, ceil(reset - now))`.
- One Redis call (EVAL, INCRBY plus PEXPIRE on first use) per limit().

d) FastAPI and Starlette
- StreamingResponse (starlette/responses.py line 224): a sync iterator is wrapped by iterate_in_threadpool (concurrency.py), which runs each `next()` through anyio.to_thread.run_sync. So a sync generator runs in the thread pool, one next() at a time. An async iterable is used as is.
- Disconnect: uvicorn 0.54 sends ASGI spec_version "2.3" (h11_impl.py line 210), so StreamingResponse uses the task-group path (responses.py lines 275 to 282) and cancels stream_response when it receives http.disconnect. A `next()` already running in a thread cannot be cancelled and finishes. iterate_in_threadpool has no try/finally, so nothing calls close() on the sync generator.
- Measured (throwaway script in the session scratchpad, real uvicorn 0.54, generator yielding once per second, client closed after 2 frames at t = 1.2 s): yield 2 still ran at t = 2.2 s (the in-flight next()), no further yields, and GeneratorExit/finally ran only after an explicit gc.collect() at t = 5.2 s. Without the collect, nothing closed the generator in the 4 s window. So after a disconnect: at most one more event is produced, and close() runs when the generator is garbage collected, not at the disconnect.
- RequestValidationError: `@app.exception_handler(RequestValidationError)` (fastapi/applications.py; fastapi.exceptions.RequestValidationError). `exc.errors()` gives the pydantic error list.
- Lifespan: `FastAPI(lifespan=<async context manager function>)`; startup code runs before `yield`. TestClient runs it only when used as a context manager.
- A handler for Exception is served by Starlette's ServerErrorMiddleware, which sends the response and then re-raises; TestClient needs raise_server_exceptions=False to see the 500.

e) SSE headers and Vercel streaming
- Cache-Control "no-cache, no-transform" and X-Accel-Buffering "no" are set in SSE_HEADERS; media type "text/event-stream; charset=utf-8" is set through StreamingResponse(media_type=...) (SSE_MEDIA_TYPE). Starlette appends charset for text/* only when absent, so the explicit value is kept. A "Connection: keep-alive" header is also in SSE_HEADERS.
- Vercel: https://vercel.com/docs/functions/runtimes/python: "Vercel Functions support streaming responses when using the Python runtime. This lets you send parts of a response as they become ready." Also https://vercel.com/docs/functions/streaming-functions ("Streaming Python functions": "You can stream responses from Vercel Functions that use the Python runtime."). The docs never say Python buffers, and give no FastAPI or SSE example, so a deployed check is still needed in M14. No stop condition. Vercel's limits page (https://vercel.com/docs/functions/limitations) states Hobby max duration 300 s and that the duration "includes time spent processing the request and sending the response, including streamed responses". vercel.json sets 60 s.

f) langchain-groq 1.1.3 (chat_models.py lines 414 to 421, 519 to 520)
- Timeout parameter: `timeout` (field request_timeout, alias "timeout"); default None. ChatGroq passes `"timeout": self.request_timeout` to the groq client, so the default None is passed explicitly, and groq treats an explicit None as no timeout (groq's own default httpx.Timeout(60, connect=5) applies only when the argument is not given; groq/_client.py line 54 and _constants.py line 9).
- Retries parameter: `max_retries`, ChatGroq default 2 (groq default also 2). The project's llm.py passes max_retries=3 (M11 S1 fact d).
- Worst case of one call: with the current defaults, unbounded (timeout None). With llm_timeout_s = 20 and max_retries = 3: 20 x 4 = 80 s plus retry backoff (up to 8 s each, M11 S1 d), above both the 50 s request_timeout_s and vercel.json's 60 s. With max_retries = 2: 20 x 3 = 60 s plus backoff. So S2 cannot rely on the per-call timeout alone; it needs the wall-clock check in the handoff below, and should build the API's ChatGroq with a smaller max_retries.

g) langsmith 0.14.7
- Traces are sent from a background thread: Client keeps a tracing_queue and a ThreadPoolExecutor (langsmith/client.py; langchain_core/tracers/langchain.py `_get_executor`). `flush(timeout=None)` waits on tracing_queue.join(), so with no timeout it blocks until the queue is drained; `flush(timeout=n)` bounds the wait (client.py lines 4196 to 4218). ragdocs.tracing.flush_traces calls wait_for_all_tracers, which calls `_CLIENT.flush()` with no timeout and does nothing if no client exists or tracing is off. So its worst case is unbounded in code (bounded in practice by the HTTP timeouts of the background sends).
- A serverless function can be frozen after the response ends, so queued traces could be lost; with tracing on, flush before the end of the stream. Production tracing is off by default (D18), so by default there is nothing to flush.

h) X-Forwarded-For on Vercel: https://vercel.com/docs/headers/request-headers: "The public IP address of the client that made the request." and "we currently overwrite the X-Forwarded-For header and do not forward external IPs. This restriction is in place to prevent IP spoofing." The page does not say a client-supplied first entry is always dropped, only that the header is overwritten. Decision: trust the first entry (as the prompt specifies). Locally, the header is client-controlled, which is acceptable for development.

i) Settings (src/ragdocs/config.py) before this session
- env: existed (Literal["local","production"], default "local", env var RAGDOCS_ENV or "env"). Kept.
- Existing: max_question_chars 500 (unchanged), rate_limit_per_ip_per_hour 20, daily_global_cap 300, upstash_redis_rest_url and upstash_redis_rest_token as SecretStr | None (env UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN), groq_api_key, google_api_key, cohere_api_key, tavily_api_key (all SecretStr | None; tavily_api_key was declared twice), langsmith_tracing (bool), langsmith_sampling_rate (env LANGSMITH_TRACING_SAMPLING_RATE, 0 to 1, default 1.0).
- Settings.require(name) is generic: it lower-cases the name, raises RuntimeError naming the env var when the attribute is missing, None or empty, else returns the secret. It demands nothing by itself. The only caller for COHERE_API_KEY is CohereReranker (providers/reranker.py line 57), and the factory returns NoopReranker when use_reranker is False (line 102). So no change to require was needed.
- M07 recorded that a sampling variable exists (LANGSMITH_TRACING_SAMPLING_RATE, Settings.langsmith_sampling_rate), so the "no sampling variable" production error never applies.

Step 2: Settings
| Field | Env var | Old | New |
|---|---|---|---|
| env | RAGDOCS_ENV | existed, "local" | unchanged |
| max_question_chars | MAX_QUESTION_CHARS | 500 | unchanged |
| rate_limit_per_ip_per_hour | RATE_LIMIT_PER_IP_PER_HOUR | 20 | 5 |
| daily_global_cap | DAILY_GLOBAL_CAP | 300 | 32 (Step 2a) |
| upstash_redis_rest_url, upstash_redis_rest_token | UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN | SecretStr | unchanged (kept as SecretStr, not str) |
| ip_hash_salt | IP_HASH_SALT | - | SecretStr or None |
| max_body_bytes | MAX_BODY_BYTES | - | 8192 |
| request_timeout_s | REQUEST_TIMEOUT_S | - | 50.0 |
| sse_ping_interval_s | SSE_PING_INTERVAL_S | - | 10.0 |
| llm_timeout_s | LLM_TIMEOUT_S | - | 20.0 |
| upstash_timeout_s (not in the prompt) | UPSTASH_TIMEOUT_S | - | 3.0 |

Step 2a: daily_global_cap
Sources: per_question.jsonl usage.by_model and scores.used_web of baseline-20261116-1050 (the baseline run frozen at v1-baseline; baseline-20261116-0919 is also in the tag but has no failed-attempt data and is the earlier run), corrective-20261120-1852, self_rag-20261121-0744; 50 questions each. Limits from Settings: groq_tpd_limit 200,000 and groq_rpd_limit 1,000 per model, embedding_rpd_limit 1,000. A script in the session scratchpad computed this (not committed).

| Model | Run | Total tokens (50 q) | Mean tokens/q | Total calls | Mean calls/q |
|---|---|---|---|---|---|
| gpt-oss-120b | baseline | 116,678 | 2,333.6 | 50 | 1.00 |
| gpt-oss-120b | corrective | 89,993 | 1,799.9 | 50 | 1.00 |
| gpt-oss-120b | self_rag | 98,675 | 1,973.5 | 53 | 1.06 |
| gpt-oss-20b | corrective | 138,872 | 2,777.4 | 66 | 1.32 |
| gpt-oss-20b | self_rag | 243,679 | 4,873.6 | 157 | 3.14 |

| Limit | Largest mean | Formula | Questions/day |
|---|---|---|---|
| gpt-oss-120b TPD | 2,333.6 tokens | floor(0.8 x 200,000 / 2,333.6) | 68 |
| gpt-oss-120b RPD | 1.06 calls | floor(0.8 x 1,000 / 1.06) | 754 |
| gpt-oss-20b TPD | 4,873.6 tokens | floor(0.8 x 200,000 / 4,873.6) | 32 |
| gpt-oss-20b RPD | 3.14 calls | floor(0.8 x 1,000 / 3.14) | 254 |
| Tavily | used_web 0.16 (corrective; self_rag 0.14; baseline 0) | floor(0.8 x 1,000 / 30 / 0.16) | 166 |
| Gemini embeddings | 1 per question | floor(0.8 x 1,000 / 1) | 800 |

- Tavily: 1,000 free credits per month on the free plan and 1 credit per basic search, from https://www.tavily.com/pricing and https://docs.tavily.com/documentation/api-credits (read 2026-11-22).
- Embedding caching was not counted on.
- Minimum: 32 (gpt-oss-20b tokens per day, self_rag). daily_global_cap = 32. It is above 15, so no stop.
- Caveat: the cap counts accepted questions, but a self_rag question can fail partway or regenerate; the means come from the 50 eval questions, and real visitor questions may differ. Corrective and baseline traffic use fewer tokens, so 32 is conservative for them.

Step 3 notes
- Decisions on interfaces S2 should know:
  - ask_preflight takes the raw body bytes (S2 reads `await request.body()`), not a parsed model, so size and JSON checks happen in the order the prompt gives. body_size_guard is a dependency S2 adds to the route (`dependencies=[Depends(body_size_guard)]`); with no body parameter on the route, FastAPI does not read the body before the dependency runs. ask_preflight also checks Content-Length and the real length itself.
  - AskRequest is used inside ask_preflight; the RequestValidationError handler is registered as the prompt requires (for any route that declares AskRequest directly) and uses the same message mapping.
  - Validation order inside the question: question missing or not a string beats an unknown pipeline.
- Content-Length on Vercel: https://vercel.com/docs/functions/limitations states the 4.5 MB request body limit (413 FUNCTION_PAYLOAD_TOO_LARGE) but does not say whether Content-Length is added to forwarded requests. Not verified. ask_preflight therefore also checks len(body) after reading, so a missing header cannot bypass max_body_bytes (the body is read first in that case).

Verification
- `py tasks.py lint`: "All checks passed!", "160 files already formatted".
- `py tasks.py test`: "389 passed, 1 deselected in 14.89s" (348 existing + 41 new in tests/test_api_blocks.py; 348 is 389 minus 41, not run separately).
- `py tasks.py bundle-check`: "Total bundle size: 230.36 MB (limit: 400.00 MB)".
- `git diff v2-agentic -- requirements.txt`: empty.
- Nothing under src/ragdocs/pipelines/, the retriever, prompts, data/ or results/ changed; api/index.py and vercel.json unchanged. No live API calls and no network in tests.

Decisions made
- D28 (docs/DECISIONS.md): the limiter fails closed.
- upstash_timeout_s added as a Setting (not in the prompt) because the Upstash client has no timeout of its own (Step 1b).
- Upstash secrets stay SecretStr, so the URL is never printed by accident.
- In production, get_rate_limiter raises on missing Upstash settings (startup validation also reports it first).

Deviations from the prompt
- tests/test_config.py lines 46 and 47 changed from 20 and 300 to 5 and 32, which are the defaults the prompt requires. This is an existing test changed for a reason other than the Settings.require fix, which is a stop condition; the human approved the change in this session.
- upstash_redis_rest_url is SecretStr, not str (existing field kept).
- Extra setting upstash_timeout_s; extra header "Connection: keep-alive" in SSE_HEADERS; Cache-Control is "no-cache, no-transform" (prompt: no-cache).
- Settings.require not changed: it never demanded COHERE_API_KEY.
- RAGDOCS_ENV in .env.example is "local" instead of empty.
- Build plan vs prompt: the prompt takes precedence everywhere; the differences recorded here are the 5 per hour limit, daily cap 32, fail-closed D28, validation message bodies, and ask_preflight (the build plan's text was not re-read, so any other difference is not listed).

Known issues and limitations
- build_redis sets a private httpx attribute of upstash-redis 1.8.0; a version bump needs the test re-checked.
- The per-IP check and the global counter are separate calls (up to 3 HTTP calls per request, each bounded by 3 s). An IP-allowed request that is then refused by the global cap still consumed its per-IP slot.
- The global counter increments for every request that passes the IP window, including ones that later fail in the pipeline.
- Vercel streaming and Content-Length behaviour are documented but not tested on a deployment (M14).
- X-Forwarded-For is trusted as the first entry; locally it is client-controlled.

Open questions for the human
- None open. Resolved: the test_config.py assertion change (approved).

Proposed follow-ups (out of scope)
- (Done in S2: Settings.llm_max_retries, production value 1; see "S2" below.)
- Consider refunding the global counter or counting only completed questions.

Prerequisites for the next module
- S2 handoff below.

S2 handoff
Signatures S2 calls (all under ragdocs.api):
- `preflight.ask_preflight(request: Request, body: bytes, limiter: RateLimiter, settings: Settings) -> tuple[str, str] | JSONResponse` returns (stripped question, pipeline name) or the response to return as is (413, 422, 429 with Retry-After, 503).
- `preflight.body_size_guard(request: Request) -> None` (dependency; raises BodyTooLarge, handled by the app as 413).
- `sse.format_event(event_name: str, payload: dict) -> str`; `sse.ping() -> str`; `sse.SSE_HEADERS: dict[str, str]`; `sse.SSE_MEDIA_TYPE = "text/event-stream; charset=utf-8"`.
- `ratelimit.rate_limiter_dependency() -> RateLimiter` (process-wide; override with app.dependency_overrides); `ratelimit.RateLimiter.check(client_key) -> LimitResult(allowed, retry_after_s, reason)`.
- `startup.validate_runtime_settings(settings: Settings) -> None` is already called by the app lifespan; S2 does not call it again.
- `app.PIPELINES`, GET /api/pipelines done.
- Settings S2 uses: request_timeout_s (50), sse_ping_interval_s (10), llm_timeout_s (20), max_question_chars, max_body_bytes.

Behaviour S2 must design around
- Disconnect (1d): a sync generator in StreamingResponse runs in the thread pool, one next() at a time. After a client disconnect the in-flight next() finishes, nothing further is pulled, and close() runs only when the generator is garbage collected (measured: not within 4 s without gc.collect()). Do not rely on GeneratorExit or finally to stop work or release resources; use an explicit stop signal or a deadline checked between events, and keep the stream's own wall-clock limit (request_timeout_s).
- Worst-case LLM call time (1f): ChatGroq timeout defaults to None (no timeout), max_retries 2 (the project's llm.py uses 3). With llm_timeout_s 20: 20 x (3 + 1) = 80 s plus backoff at max_retries 3, or 60 s plus backoff at 2. Both exceed request_timeout_s 50 and vercel.json maxDuration 60, so a hung call is not bounded by the per-call timeout; S2 must enforce the 50 s total itself and send an error event.
- Traces (1g): langsmith sends from a background thread; flush_traces blocks until the queue drains (no timeout argument in ragdocs.tracing). With tracing on, flush before the stream ends or the function may be frozen first; with tracing off (default in production, D18) nothing needs flushing.
- Ping: send ping() every sse_ping_interval_s while waiting for the next pipeline event.
- Streaming response: use StreamingResponse(media_type=SSE_MEDIA_TYPE, headers=SSE_HEADERS).


---

# S2: POST /api/ask, stream runner, local server, live check
Module prompt: "M12 (2/2)" (streaming endpoint), given by the human on 2026-11-22. Commit: "M12: streaming ask API with rate limits" (not pushed).

## What was built (S2)
- src/ragdocs/api/stream.py (new): StreamRunner (async generator events() plus a daemon worker thread), log_request, configure_request_logging, default_poll, never_disconnected, message constants.
- src/ragdocs/api/app.py: lifespan now also calls configure_request_logging and configure_tracing (stores app.state.tracing_active); get_pipeline (lock-guarded cache), reset_pipeline_cache, POST /api/ask, _RecordingLimiter, _peek_body, _log_refused.
- src/ragdocs/api/local.py (new, local only): configure_local(target, public_dir) adds CORS for http://localhost:8000 and http://127.0.0.1:8000 and mounts StaticFiles(public/, html=True) at "/" after the API routes.
- src/ragdocs/providers/llm.py: ChatGroq now gets timeout=Settings.llm_timeout_s and max_retries=Settings.llm_max_retries (was a literal 3). No pipeline file changed.
- src/ragdocs/config.py: llm_max_retries (3), trace_flush_timeout_s (5.0). .env.example: LLM_MAX_RETRIES, TRACE_FLUSH_TIMEOUT_S.
- tasks.py: dev runs ragdocs.api.local:app. tools/sse_probe.py: --stop-after N.
- tests/test_api_stream.py (new, 45 test cases). docs/DECISIONS.md: D29.
- Not changed: ask_preflight, ratelimit, startup, sse, models (S1 code used as is), api/index.py, vercel.json, requirements*.txt, pipelines, retriever, prompts, index, eval set, results/.

## How to run
- `py tasks.py dev` (API plus public/ on http://127.0.0.1:8000), then `.venv\Scripts\python tools\sse_probe.py --pipeline baseline --question "..."`.
- `py tasks.py lint`, `py tasks.py test`, `py tasks.py bundle-check`.

## Step 0: async disconnect handling (verified)
- starlette 1.7.0 responses.py (StreamingResponse.__call__, lines 261 to 282): for ASGI spec_version below 2.4 (uvicorn 0.54 sends 2.3) it runs stream_response and listen_for_disconnect in a task group; on http.disconnect the group is cancelled, so the task iterating the async body receives CancelledError at the generator's current await. For spec_version 2.4 or higher it only notices on the next send (OSError to ClientDisconnect), so a server upgrade changes this: re-run the measurement.
- Request.is_disconnected() (requests.py line 328) does a non-blocking receive() under a cancelled scope, so it can be awaited while the response streams. It competes with listen_for_disconnect for the same receive channel; either one sees the disconnect, and the cancellation path still runs. The runner polls it once per loop turn as the prompt specifies.
- Measurement (throwaway tools/_async_disc.py, deleted, not committed; real uvicorn 0.54, async generator awaiting asyncio.sleep(0.5) per yield, httpx client read 2 chunks then closed): the generator received CancelledError and ran finally 0.000 s after the client closed (below the 15 ms Windows clock resolution), with no gc.collect(). The stop condition (over 2 s) was not met.
- Test tooling: pytest-asyncio 1.4.0 is already pinned in requirements-dev.txt, and anyio 4.15.1 (with its pytest plugin) is installed. Tests use @pytest.mark.asyncio in strict mode (no config change, no new dependency).

## Contract as built (M13 builds against this)
Routes: GET /api/health, GET /api/pipelines (S1), POST /api/ask. Locally GET / serves public/.

POST /api/ask
- Request: JSON body `{"question": string, "pipeline": "baseline" | "corrective" | "self_rag"}`; pipeline defaults to "self_rag". The question is stripped, 3 to 500 characters, no control characters except newline and tab. Body at most 8192 bytes.
- Errors before streaming (JSON, `Content-Type: application/json`):

| Status | Body | When |
|---|---|---|
| 413 | `{"error":"Request body too large."}` | body over 8192 bytes (declared or actual) |
| 422 | `{"error":"Send JSON with a \"question\" string."}` | bad JSON, not an object, question missing or not a string |
| 422 | `{"error":"Unknown pipeline. Choose baseline, corrective or self_rag."}` | unknown pipeline |
| 422 | `{"error":"The question must be between 3 and 500 characters."}` | length |
| 422 | `{"error":"The question contains unsupported control characters."}` | control characters |
| 429 | `{"error":"Rate limit reached. Try again later.","retry_after_s":N}` plus header `Retry-After: N` | per-IP window (5 per hour) |
| 503 | `{"error":"The demo's daily budget is used up. It resets at 00:00 UTC."}` | daily global cap (32) |
| 503 | `{"error":"The service is temporarily unavailable."}` | limiter store failure (D28, fail closed) |
| 500 | `{"error":"Internal error."}` | unhandled exception before streaming |

- Success: HTTP 200 with headers `Content-Type: text/event-stream; charset=utf-8`, `Cache-Control: no-cache, no-transform`, `X-Accel-Buffering: no`, `Connection: keep-alive`. Failures after this point arrive as an SSE `error` event, still with HTTP 200.
- SSE frames (`event: <name>\ndata: <one-line JSON>\n\n`, compact JSON, UTF-8, not ASCII-escaped):
  - `trace`: one TraceEvent: `{"type": "node_start"|"node_end"|"decision"|"retrieval", "node": str, "message": str, "data": object, "t_ms": int}`. t_ms is milliseconds since the pipeline started.
  - `answer`: one PipelineResult (the same JSON the eval files store): `question`, `pipeline`, `answer {text, citations [{chunk_id, url}], abstained}`, `contexts` (RetrievedChunk list), `trace` (all trace events), `llm_calls`, `latency_ms`, `used_web`, and `diagnostics` only when non-empty. Sent at most once, always last. `answer.abstained` tells an abstention from an answer.
  - `error`: `{"error": string}`, sent at most once, always last. Messages: the pipeline's own safe message (form "ExceptionClass: first line"; it can name a provider error class, so show it as plain text), "The request took too long." (after 50 s), "The server is missing configuration.", "Internal error.".
  - Keep-alive: the comment frame `: ping\n\n` every 10 s without another frame. It is not an event; EventSource and fetch-based SSE parsers ignore it.
- Every stream ends with exactly one `answer` or one `error` frame, then the connection closes. A client that disconnects stops the work.

Log line (logger "ragdocs.api", one INFO line per /api/ask request, written to stderr): `pipeline=<name|-> outcome=<answer|abstained|error|timeout|disconnected|limited|invalid> latency_ms=<int> llm_calls=<int|-> used_web=<true|false|-> question_chars=<int|-> [limit_reason=ip|global|unavailable]`. Never the question, answer, IP, client key or any key.

## Step 6: live check (3 pipelines, q001, tracing off, local server)
Server: LANGSMITH_TRACING=false; see Deviations item 8 for how it was started. q001 question: "My agent run stops with GRAPH_RECURSION_LIMIT; where do I set a bigger step cap?" (an eval item, not a visitor question). Probe lines are cut to 150 characters here.

baseline (first event 3.3 s including the lazy pipeline load, total 5.7 s, 4 trace events, ends in answer, exit 0)
```
   3.3s  trace      {"type":"node_start","node":"retrieve","message":"Retrieving documentation excerpts","data":{},"t_ms":0}
   4.0s  trace      {"type":"retrieval","node":"retrieve","message":"Retrieved candidate excerpts","data":{"mode":"hybrid","chunks":[{"rank":1,"title"
   4.0s  trace      {"type":"node_start","node":"generate","message":"Generating cited answer","data":{},"t_ms":705}
   5.7s  trace      {"type":"node_end","node":"generate","message":"Answer generated and validated","data":{"dropped_citations":0,"uncited":false},"t_
   5.7s  answer     {"question":"My agent run stops with GRAPH_RECURSION_LIMIT; where do I set a bigger step cap?","pipeline":"baseline","answer":{"te
first event 3.3s, total 5.7s, trace events 4, last answer
```
corrective (first event 2.7 s, total 5.1 s, 10 trace events, ends in answer, exit 0)
```
   2.7s  trace      {"type":"node_start","node":"retrieve","message":"Retrieving documentation excerpts","data":{},"t_ms":608}
   2.7s  trace      {"type":"retrieval","node":"retrieve","message":"Retrieved candidate excerpts","data":{"mode":"hybrid","query":"My agent run stops
   2.7s  trace      {"type":"node_end","node":"retrieve","message":"Retrieved 5 excerpts","data":{},"t_ms":609}
   3.7s  trace      {"type":"node_start","node":"grade_documents","message":"Grading 5 excerpts","data":{},"t_ms":1561}
   3.7s  trace      {"type":"decision","node":"grade_documents","message":"4 of 5 chunks relevant","data":{"grades":[{"index":1,"chunk_id":"0b10c87050
   5.1s  answer     {"question":"My agent run stops with GRAPH_RECURSION_LIMIT; where do I set a bigger step cap?","pipe
first event 2.7s, total 5.1s, trace events 10, last answer
```
self_rag (first event 2.3 s, total 6.4 s, 16 trace events, ends in answer, exit 0)
```
   2.3s  trace      {"type":"node_start","node":"decide_retrieval","message":"Deciding whether to retrieve","data":{},"t_ms":582}
   2.3s  trace      {"type":"decision","node":"decide_retrieval","message":"retrieval needed: Question about LangGraph recursion limit setting.","data
   2.3s  trace      {"type":"node_end","node":"decide_retrieval","message":"Retrieval decided","data":{},"t_ms":582}
   2.9s  trace      {"type":"node_start","node":"retrieve","message":"Retrieving documentation excerpts","data":{},"t_ms":1158}
   2.9s  trace      {"type":"retrieval","node":"retrieve","message":"Retrieved candidate excerpts","data":{"mode":"hybrid","query":"My agent run stops
   6.4s  answer     {"question":"My agent run stops with GRAPH_RECURSION_LIMIT; where do I set a bigger step cap?","pipe
first event 2.3s, total 6.4s, trace events 16, last answer
```
(The corrective and self_rag blocks show the first 5 lines and the last line; the lines between are omitted.)

- Progressive, not buffered: frames arrive at different times (corrective: 2.7 s, 3.7 s, ..., 5.1 s). No pipeline took over 50 s (longest 6.4 s). Frames that share a timestamp are events the graph produced in one step.
- 422 (2-character question "ab"): the probe prints `status 422` and the body `{"error":"The question must be between 3 and 500 characters."}`.
- GET / : 200, first 80 characters `'<!DOCTYPE html>\n<html lang="en">\n<head>\n  <meta charset="UTF-8">\n  <meta name="v'`. public/index.html already exists (the M01 skeleton), so it was not created; M13 owns it. GET /api/health : 200, `'{"status":"ok","env":"local","python":"3.12.9","commit":"local"}'`.
- Disconnect (self_rag, `--stop-after 2`, run three times): the `outcome=disconnected` log line appeared 0.18 s, 0.12 s and 0.12 s before the probe printed its exit time (server log 21:32:24,552 vs probe exit 21:32:24.731; 21:33:56,236 vs 21:33:56.351; 21:34:22,252 vs 21:34:22.371), so within the 2 s limit. After the disconnect no Groq call was made: with the budget ledger working (second run), gpt-oss-20b requests rose by one (the decide_retrieval call made before the disconnect) and stayed flat for the next 14 s, and gpt-oss-120b stayed at 0 requests. One Gemini embedding call (the retrieve step already in flight) was recorded around the disconnect. llm_calls is "-" for a disconnected request because there is no PipelineResult.
- Server log lines (INFO, one per /api/ask request; no question text; uvicorn access lines omitted):
```
pipeline=baseline outcome=answer latency_ms=5422 llm_calls=1 used_web=false question_chars=80
pipeline=corrective outcome=answer latency_ms=4718 llm_calls=2 used_web=false question_chars=80
pipeline=self_rag outcome=answer latency_ms=6078 llm_calls=4 used_web=false question_chars=80
pipeline=baseline outcome=invalid latency_ms=0 llm_calls=- used_web=- question_chars=-
pipeline=self_rag outcome=disconnected latency_ms=547 llm_calls=- used_web=- question_chars=80
pipeline=baseline outcome=answer latency_ms=4812 llm_calls=1 used_web=false question_chars=80
pipeline=self_rag outcome=disconnected latency_ms=2375 llm_calls=- used_web=- question_chars=80
pipeline=self_rag outcome=disconnected latency_ms=640 llm_calls=- used_web=- question_chars=80
```
(Eight lines for eight /api/ask requests. The 2375 ms line is a disconnect check whose ledger snapshot failed because of a script error, so it was repeated once.)
- The server was stopped after the checks (port 8000 no longer answers).
- Not exercised live: the trace flush path (tracing off, the D18 default) and the 50 s timeout (fake-clock tests only).

## Step 3 log audit
Searched src/ragdocs/pipelines, providers, retrieval and generation for logging calls. Only src/ragdocs/providers/websearch.py logs: a WARNING with the Tavily exception class, status and retry number, and a WARNING listing dropped off-domain result URLs (third-party URLs, not the question or answer). Nothing logs a question or answer. No stop. None changed.

## Step 7: verification
- `py tasks.py lint`: "All checks passed!", "164 files already formatted".
- `py tasks.py test`: "434 passed, 1 deselected in 36.41s" (389 after S1 plus 45 in tests/test_api_stream.py).
- `py tasks.py bundle-check`: "Total bundle size: 230.40 MB (limit: 400.00 MB)".
- `git diff v2-agentic -- requirements.txt api/index.py vercel.json src/ragdocs/pipelines`: empty (0 bytes).
- No earlier test was changed. The baseline snapshot and message-fixture tests pass unchanged (no existing test asserted ChatGroq constructor arguments).
- The new tests sleep at most about 0.1 s in total (a 0.02 s race window, a 1 ms poll loop, the 0.05 s flush timeout). The test run is slower than in S1 (14.89 s to 36.41 s) mainly because of one test that starts a subprocess importing the app.

## Decisions made (S2)
- D29 (docs/DECISIONS.md): the async-generator-plus-worker-thread design and llm_max_retries 1 in production.
- llm_max_retries default is 3. ChatGroq's own default is 2, but ragdocs.providers.llm passed 3 before M12 and the prompt wants local runs and eval unchanged, so 3 is "the value used today". Please confirm.
- Eval writes every non-secret Settings field into config.json (runner.py _settings_snapshot), so runs from now on also record llm_max_retries and trace_flush_timeout_s. llm_timeout_s (20 s, added in S1) now really applies to eval runs too, because ChatGroq receives it; before, the eval used no timeout. A call slower than 20 s is retried up to 3 times and then fails; M15 should know.
- The route runs ask_preflight in asyncio.to_thread because the limiter makes blocking HTTP calls (up to 3 x 3 s); on the event loop those would stop pings for every other request in the process.

## Deviations from the prompt (S2)
1. Trace flush wait: the prompt says `wait_for(to_thread(thread.join), timeout)`. I use `to_thread(thread.join, timeout)` and then `thread.is_alive()`. With wait_for, a timeout leaves the executor thread blocked in join() until the flush ends, which also makes asyncio.run wait for it at shutdown; joining with a timeout bounds both.
2. The worker thread runs inside contextvars.copy_context(). Found in Step 6: the first four asks ran with a plain thread, and the budget recorder (a ContextVar hook in ragdocs.eval.budget_recorder) saw embeddings but no Groq calls. LangChain callbacks and LangSmith tracing context use ContextVars too, so this also keeps tracing parents correct. A test covers it.
3. configure_request_logging (new): neither uvicorn nor Vercel sets a handler for INFO, so the request log line was dropped (seen with `py tasks.py dev`: only WARNINGs printed). It adds one stderr handler to the "ragdocs.api" logger; records still propagate, so caplog works.
4. Recording the limiter reason: ask_preflight returns only a response, so the route wraps the limiter (_RecordingLimiter) to know whether a refusal was "limited" (and its reason) or "invalid"; _peek_body re-parses the body for the pipeline name and question length (the text itself is never logged). ask_preflight is unchanged.
5. `response_model=None` on the route (FastAPI cannot build a response model from `StreamingResponse | JSONResponse`).
6. local.py uses the absolute path REPO_ROOT/"public" instead of the relative "public" (independent of the working directory) and exposes configure_local so a test can use a temporary directory without mutating the shared app. CORS allows methods GET and POST and the header Content-Type.
7. StreamRunner has an extra optional argument started_at so latency_ms is measured from the route's start, not from the first events() call.
8. The live server was started with a scratchpad launcher (not committed) that calls install_budget_recorder and then uvicorn.run("ragdocs.api.local:app") in the same process, instead of `py tasks.py dev`. Reason: the AGENTS.md rule that every live call goes through the budget recorder, and ragdocs.api must not import ragdocs.eval. `py tasks.py dev` itself was checked separately (it starts, serves / and /api/health, no live call). LANGSMITH_TRACING=false was set in the process environment.
9. Live asks: 3 required, plus 3 extra (two partial self_rag asks for the disconnect check and one baseline ask to confirm the recorder after fix 2), and one more partial self_rag ask from the first disconnect run (4 on the first server, 3 on the second; 7 in total). Budget was checked with `py tasks.py budget --need` before each batch: openai/gpt-oss-120b 10000:8 fits, openai/gpt-oss-20b 16000:14 fits, gemini-embedding-001 300:5 fits; later asks 3000:2, 1500:3 and 100:1, all fit. The first four asks (baseline, corrective, self_rag, first disconnect run) were not recorded for Groq in the ledger because of the context bug (item 2); their usage was roughly 6k tokens on gpt-oss-120b and 8k on gpt-oss-20b, estimated from the S1 per-question means and the llm_calls logged, not measured. Their embedding calls were recorded.
10. The build-plan M12 text was not re-read in S2; apart from the differences listed in S1 and above, any others are not listed.
11. StreamRunner's default poll raises asyncio.TimeoutError (the builtin TimeoutError in Python 3.12); the prompt's test wording "poll returns Empty" was implemented as a poll that raises it.

## Abandoned-thread limitation
After a timeout or a disconnect the worker thread cannot be interrupted: it runs until the call it is in (LLM, Tavily or embedding) returns, then sees the cancel flag at its next event, closes the pipeline stream and exits. The runner's finally and the request log do not wait for it.
- Worst case for one Groq call before Step 2.4: timeout None, so unbounded (a hung connection).
- After Step 2.4 with llm_timeout_s 20 and llm_max_retries 3 (the default): 4 attempts x 20 s = 80 s plus backoff 0.5 + 1 + 2 = 3.5 s, about 83.5 s. groq honours a Retry-After header of 60 s or less, which can add more.
- With LLM_MAX_RETRIES=1 (production): 2 attempts x 20 s = 40 s plus 0.5 s backoff, about 40.5 s, inside the 50 s request limit and Vercel's 60 s maxDuration. A Retry-After of up to 60 s would still exceed it; the runner's 50 s timeout then ends the response and the thread idles until the call returns.
- Pipelines make several calls in sequence (up to 8 for self_rag, D27); the 50 s total is enforced by the runner, not by the per-call timeout. Tavily searches (web_search_max_attempts 3, backoff 1 s and 2 s) were not given a per-call timeout here.
- On Vercel a thread still running after the response ends may be frozen with the instance; it holds no request resources.

## Known issues and limitations (S2)
- The first request after a cold start loads the retriever and pipeline inside the worker (2 to 3 s measured locally), so pings and the 50 s budget already cover it; the first event of the first ask came at 3.3 s.
- The trace flush after the answer keeps the connection open for up to trace_flush_timeout_s (5 s) when tracing is on and LangSmith is slow; only unit-tested with a fake flush, not run live.
- The global counter and the per-IP check are separate Upstash calls (S1 limitation, unchanged).
- When a client disconnects, the in-flight retrieval embedding call still happens (one Gemini request seen).
- uvicorn spec_version 2.4 or newer changes how Starlette reports a disconnect (see Step 0). Vercel's server was not tested here (M14).

## Open questions for the human (S2)
- Confirm the llm_max_retries default of 3 (project value) rather than 2 (ChatGroq library default).
- The unrecorded Groq usage of the first four asks (deviation 9): add an adjustment to the budget ledger, or is the estimate enough?

## Proposed follow-ups (out of scope, S2)
- A per-call timeout for Tavily searches.
- Refund the global counter when a request ends in error, timeout or disconnect (the S1 follow-up still applies).
- A deployed check that Vercel streams frames progressively (M14).

## M14 carry-over
- Vercel Production env vars, alongside GROQ_API_KEY, GOOGLE_API_KEY, TAVILY_API_KEY and the LangSmith settings:
  - RAGDOCS_ENV=production.
  - IP_HASH_SALT: a random 32-byte hex value that Bilal generates (for example `.venv\Scripts\python -c "import secrets; print(secrets.token_hex(32))"`); never commit it.
  - LLM_MAX_RETRIES=1, so one call takes at most 2 x 20 = 40 s plus 0.5 s backoff and stays inside the 50 s request limit.
  - Upstash: Settings reads UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN. If the Vercel Upstash integration provides KV_REST_API_URL and KV_REST_API_TOKEN instead, add the two UPSTASH_ names as aliases (or copy the values); the lifespan check fails production startup when either is missing.
  - LANGSMITH_TRACING stays false by default (D18); if turned on, LANGSMITH_TRACING_SAMPLING_RATE must be 0.1 or lower.
- D28: the limiter fails closed (503 "The service is temporarily unavailable.") when Upstash is unreachable or errors. Check that Upstash is reachable from the Vercel region before launch.
- build_redis sets the Upstash timeout through a private attribute of the pinned upstash-redis 1.8.0 (`redis._http._client.timeout`); an upgrade must re-check it (a test builds a real limiter to catch a rename).
- Deployed checks: progressive frames through Vercel's Python runtime (tools/sse_probe.py --base-url), the disconnect log line, X-Forwarded-For handling, and that the INFO log lines appear in Vercel's logs (configure_request_logging writes to stderr).
- Remove GET /api/deps-probe (S1 note).
- api/index.py and vercel.json are unchanged. Check that the function bundle includes src/ragdocs/api/stream.py, and that vercel.json maxDuration (60) is at least request_timeout_s plus trace_flush_timeout_s (50 + 5 = 55).

## Prerequisites for the next module (M13)
- Build the trace UI against the contract above. public/index.html currently is the M01 skeleton.
