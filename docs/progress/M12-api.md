M12: Streaming API
Status: Partial (session 1 of 2)
Date: 2026-11-22

Goal
Session 1 (this file): the building blocks of the public streaming API, tested without network access. Session 2 writes POST /api/ask (streaming body), the local runner and the live checks. Module prompt: "M12 (1/2): API building blocks", given by the human on 2026-11-22.

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
- Choose a smaller max_retries for the API's ChatGroq (see 1f) once S2 measures real latency.
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
