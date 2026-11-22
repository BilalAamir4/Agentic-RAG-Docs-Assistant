# M14: Production deploy
Status: Partial (session 1 of 2)
Date: 2026-11-23

## Goal
Session 1 of 2 (module prompt "M14 (1/2)", given by the human on 2026-11-23): every code, configuration and CI change the first public deployment needs, committed and tested offline; secret and personal-data checks over what S2 will push; an S2 handoff. Nothing was pushed, no tag was created or moved, no GitHub or Vercel setting was changed.

## What was built (session 1)
- src/ragdocs/api/app.py: GET /api/deps-probe and its helpers (PACKAGE_MODULE_MAP, _find_requirements_file, _parse_requirements_packages, the importlib imports) removed.
- tests/test_api_health.py: the deps-probe test removed (the only existing test changed).
- src/ragdocs/config.py: upstash_redis_rest_url and upstash_redis_rest_token accept UPSTASH_REDIS_REST_URL / _TOKEN first, KV_REST_API_URL / KV_REST_API_TOKEN second, and the field names as constructor arguments. .env.example comments updated.
- tests/test_config_upstash.py (5 tests), tests/test_production_env.py (6 tests: the production table passes; each of 5 required variables removed raises RuntimeError naming the setting).
- vercel.json: `headers` array added; `functions` and `rewrites` unchanged (diff against 04b903a shows only the comma after `rewrites`). tests/test_vercel_config.py (5 tests).
- web/package.json, web/package-lock.json: `@tailwindcss/vite` moved to devDependencies (see "npm dependency split"). docs/DECISIONS.md: D31.
- .github/workflows/ci.yml: workflow "CI".
- tools/smoke_prod.py + tests/test_smoke_prod.py (25 tests); tasks.py: `smoke --url URL [extra args]`.
- tools/secret_scan.py + tests/test_secret_scan.py (7 tests).
- docs/progress/M14-production-deploy.md, PROGRESS.md.
Commits (local, unpushed): ef0151a "M14 (1/2): production hardening" (rewrite of cefed41, see "cefed41 rewrite"), 7aa5c2e "M14 (1/2): require IP_HASH_SALT in production", then the record commit "M14 (1/2): push readiness record".

## How to run
- `py tasks.py smoke --url https://<production domain>` (all checks, 3 live asks, about 45 s apart in the worst case); `--no-asks` for no quota use; `--local` against `py tasks.py dev`.
- `.venv\Scripts\python tools\secret_scan.py --range origin/main..HEAD` (local only).
- CI: `.github/workflows/ci.yml` on push and pull request to main.

## Step 1 findings
Documentation was read through the web-fetch tool; where a page does not say something, it is marked "not stated" and the design does not depend on it.

a) Upstash integration env vars.
- https://vercel.com/marketplace/upstash, https://upstash.com/docs/redis/howto/vercelintegration and https://vercel.com/docs/redis (updated 2026-01-13) do NOT name the variables, which token is read-only, a prefix option, or target environments. They only say the integration "will set the required environment variables" and that the app must be redeployed.
- Web search result (secondary, not a page I read): Vercel's storage docs say Marketplace Redis integrations keep the Vercel KV names for compatibility, so KV_REST_API_URL and KV_REST_API_TOKEN are expected; one source says UPSTASH_KV_URL appears if KV_URL already exists in the project; Upstash's SDK `Redis.fromEnv()` accepts either UPSTASH_REDIS_REST_* or KV_REST_API_*.
- Not verified: the read-only token's name (KV_REST_API_READ_ONLY_TOKEN is the Vercel KV name from memory), whether a prefix can be set, the default prefix. Handled by: both pairs accepted, the read-only name never read, and S2 checks the names in the dashboard (handoff step 7). A custom prefix would rename the variables and startup would then fail with "UPSTASH_REDIS_REST_URL is missing", so Bilal leaves the prefix empty/default and reports the names shown.

b) vercel.json headers (https://vercel.com/docs/project-configuration/vercel-json, https://vercel.com/docs/headers/cache-control-headers).
- Syntax: array of {source, headers: [{key, value}]}; `source` matches the pathname without the query string. Verified.
- The page says the rules apply to "static files, Vercel functions, and a wildcard that matches all routes". Python is not named.
- "/(.*)" matching "/": not stated. In path-to-regexp semantics it does (empty capture). Smoke check 1 tests the CSP on GET / after deploy.
- Several rules setting the same header: not stated. The design avoids it: no two rules set the same header on one path (the catch-all sets only the four security headers; the Cache-Control rules have disjoint sources). tests/test_vercel_config.py asserts this.
- Function responses: "Cache-Control headers returned from Vercel Functions take priority over Cache-Control headers from vercel.json". For other headers, precedence between a function's headers and vercel.json is not stated. No Cache-Control rule matches /api/. The CSP on /api/* JSON responses is not checked by the smoke tool.

c) Hobby and Deployment Protection (https://vercel.com/docs/deployment-protection, https://vercel.com/docs/plans/hobby).
- The Hobby page lists "Vercel Authentication for preview and production deployments". "Standard Protection" protects all domains except production domains; "All Deployments" protects the production domain too. The default for a new project is not stated (a team can set a default in its settings). Whether production is public by default on Hobby: not stated. S2 asks Bilal for the setting and confirms with an unauthenticated `curl.exe -I https://<domain>/` (200 means public; a 401 or a redirect to vercel.com/login means protected).

d) Free-tier scope per provider.
- Groq (https://console.groq.com/docs/rate-limits): "Rate limits apply at the organization level, not individual users." Keys are not mentioned; by that sentence all keys in one organization share one quota. A separate production quota needs a separate Groq organization (how to create one is not stated on the page).
- Google Gemini API (https://aistudio.google.com/docs/rate-limits, redirected from ai.google.dev): "Rate limits are applied per project, not per API key." Keys in the same project share quota. A separate production quota needs a separate Google Cloud project (implied, not stated).
- Tavily (https://docs.tavily.com/documentation/rate-limits): "All API keys in the same organization or account share one limit." Credits (https://docs.tavily.com/documentation/api-credits: 1,000 free credits a month): scope per key or per account not stated; treat as per account.
- Consequence for Bilal: the production keys can be a separate key, but only a separate organization (Groq), project (Google) or account (Tavily) gives a separate quota. If Bilal uses keys in the same org/project/account, production traffic and eval runs draw from one quota; the daily global cap of 32 asks (D10) is the protection.

e) Actions and Node. Latest releases (https://github.com/actions/checkout/releases/latest etc.; the pages show day and month only): actions/checkout v7.0.1 (20 Jul), actions/setup-python v7.1.0 (22 Oct), actions/setup-node v7.1.0 (8 Oct). All major v7. Inputs used (README): python-version, node-version, cache, cache-dependency-path. Local Node 24.15.0 (npm 11.12.1); M13 recorded node 24.15.0. CI uses node-version 24. Local `py` is Python 3.13.5, so setup needs `py -3.12 tasks.py setup` (tasks.py says so).

f) Repository facts.
- Live tests are deselected by `-m "not live"` in tasks.py `cmd_test` (the marker is declared in pyproject.toml `markers`); the only live test is tests/test_embeddings_live.py:9 (the "1 deselected").
- No test runs git on history or tags: searched tests/ for subprocess, "eval-set-v1", rev-parse, git_commit and "git"; the subprocess calls are `python -c` import checks (test_api_blocks, test_api_stream, test_corrective_pipeline, test_import_boundaries, test_local_server, test_self_rag_graph, test_tracing). (src/ragdocs/eval/runner.py uses git; no unit test calls it.) The clean-clone rehearsal below is the real proof.
- Files the API reads at runtime (Settings.index_dir = data/index; ragdocs.index.loader, vector_index, bm25_index, docs_urls):
  | file | git ls-files | .vercelignore |
  | data/index/manifest.json | tracked | not excluded |
  | data/index/bm25.json | tracked | not excluded |
  | data/index/chunk_meta.jsonl | tracked | not excluded |
  | data/index/vectors.f16.npy | tracked | not excluded |
  The function bundle includes them through vercel.json includeFiles "{src/**,data/index/**,requirements.txt}". Nothing else is read (src/ragdocs/api/app.py no longer reads requirements.txt). No stop.
- Repo root package.json: none (Test-Path False). No stop.
- vercel.json before M14 (04b903a): `functions` {"api/index.py": maxDuration 60, includeFiles "{src/**,data/index/**,requirements.txt}"}, `rewrites` [{"/api/(.*)" -> "/api/index"}]. .vercelignore: data/raw, data/processed, data/eval, results, cache, tests, tools, scripts, docs, .venv, src/ragdocs/ingest, src/ragdocs/eval, tasks.py, pyproject.toml, web.

g) Settings and the production environment (src/ragdocs/config.py, src/ragdocs/api/startup.py).
| setting | env var(s) as config.py defines them | required in production by validate_runtime_settings |
| groq_api_key | GROQ_API_KEY | yes |
| google_api_key | GOOGLE_API_KEY | yes |
| tavily_api_key | TAVILY_API_KEY | yes |
| upstash_redis_rest_url | UPSTASH_REDIS_REST_URL, then KV_REST_API_URL (new in M14) | yes (reported as UPSTASH_REDIS_REST_URL) |
| upstash_redis_rest_token | UPSTASH_REDIS_REST_TOKEN, then KV_REST_API_TOKEN (new) | yes (reported as UPSTASH_REDIS_REST_TOKEN) |
| env | RAGDOCS_ENV (or env) | selects production |
| ip_hash_salt | IP_HASH_SALT | yes (added in 7aa5c2e; absent locally it logs one WARNING) |
| llm_max_retries | LLM_MAX_RETRIES | no |
| langsmith_tracing | LANGSMITH_TRACING | tracing above sampling rate 0.1 is refused |
| langsmith_sampling_rate | LANGSMITH_TRACING_SAMPLING_RATE | only matters when tracing is on |
Case handling: pydantic-settings matches env var names case-insensitively and config.py sets no env_prefix, so AliasChoices needs no special handling; the field names stay valid constructor arguments through a third alias, so existing tests are unchanged.

h) web/package.json at 04b903a. dependencies: @tailwindcss/vite ^4.3.5, class-variance-authority ^0.7.1, cn ^0.5.2, lucide-react ^1.77.0, radix-ui ^1.8.1, react ^19.3.1, react-dom ^19.3.1, shadcn ^4.23.0, tailwindcss ^4.3.5, tw-animate-css ^1.4.0. devDependencies: @types/node ^24.19.2, @types/react ^19.3.0, @types/react-dom ^19.3.0, @vitejs/plugin-react ^6.1.2, oxlint ^1.90.0, typescript ~7.0.2, vite ^8.3.6, vitest ^5.1.1.

i) Line endings. `git config core.autocrlf`: false. `git ls-files --eol -- web public`: no file stored as i/crlf or i/mixed. No stop.

## Vercel Production env vars
Set each in the Production scope only. Names are exactly those in config.py (1g).
| name | who sets it | value guidance | Sensitive |
| GROQ_API_KEY | Bilal | production key, see handoff step 1 (separate organization for a separate quota) | yes |
| GOOGLE_API_KEY | Bilal | production key from a separate Google Cloud project for a separate quota | yes |
| TAVILY_API_KEY | Bilal | production key (credits and rate limit are per account) | yes |
| RAGDOCS_ENV | Bilal | production | no |
| LANGSMITH_TRACING | Bilal | false | no |
| IP_HASH_SALT | Bilal | 64 hex characters he generates himself (handoff step 4) | yes |
| LLM_MAX_RETRIES | Bilal | 1 (one Groq call then takes at most 2 x 20 = 40 s plus 0.5 s backoff, inside the 50 s request limit) | no |
| KV_REST_API_URL | the Upstash integration | injected when the integration is connected with Production selected (verify the name in the dashboard) | yes (set by the integration) |
| KV_REST_API_TOKEN | the Upstash integration | injected by the integration (read-write token) | yes (set by the integration) |

Do not set:
- COHERE_API_KEY (use_reranker is False).
- LANGSMITH_API_KEY, LANGSMITH_PROJECT, LANGSMITH_ENDPOINT, LANGSMITH_TRACING_SAMPLING_RATE (tracing is off; D18).
- RATE_LIMIT_PER_IP_PER_HOUR, DAILY_GLOBAL_CAP, MAX_QUESTION_CHARS, MAX_BODY_BYTES, REQUEST_TIMEOUT_S, SSE_PING_INTERVAL_S, LLM_TIMEOUT_S, TRACE_FLUSH_TIMEOUT_S, WEB_MAX_RESULTS, MIN_RELEVANT_CHUNKS, MAX_QUERY_REWRITES, MAX_REGENERATIONS (the defaults are the reviewed production values; the .env.example lists them as optional).
- UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN (the integration's names are used; if both pairs exist the UPSTASH_ ones win).
- KV_REST_API_READ_ONLY_TOKEN is injected by the integration but is never read.
- Any eval-only variable: none other than COHERE_API_KEY exists in .env.example.

## npm dependency split (D31)
Throwaway build with source maps (`npx vite build --sourcemap --outDir <temp> --emptyOutDir`, deleted afterwards; public/ untouched):
| package | bundled JS (source maps list node_modules/<pkg>/) | bundled CSS (@import in web/src/index.css) | class |
| @tailwindcss/vite | no | no | build-only |
| class-variance-authority | yes (1) | no | bundled |
| cn | yes (3) | no | bundled |
| lucide-react | yes (16) | no | bundled |
| radix-ui | no (0), see note | no | bundled (note) |
| react | yes (4) | no | bundled |
| react-dom | yes (4) | no | bundled |
| shadcn | no | yes (`@import "shadcn/tailwind.css"`) | bundled (CSS) |
| tailwindcss | no | yes (`@import "tailwindcss"`) | bundled (CSS) |
| tw-animate-css | no | yes (`@import "tw-animate-css"`) | bundled (CSS) |
Note: the maps list no path under node_modules/radix-ui/ because it only re-exports; 6 source files import it and the maps list its dependencies (@radix-ui/react-collapsible, react-radio-group, react-label, react-slot and 15 more). Moving it would drop those from `npm audit --omit=dev`, so by the intent of the rule it stays (deviation from the literal rule).
- Build before the move: sha256 manifest of public/ (5 files) written outside the repo. `@tailwindcss/vite` moved to devDependencies with its range string unchanged; `npm install` in web/, then `py tasks.py web-install`.
- Lockfile: `git diff web/package-lock.json` adds `"dev": true` lines (and turns two `"devOptional": true` into `"dev": true`) and moves the `@tailwindcss/vite` line from the root package's dependencies to devDependencies; no "version", "resolved" or "integrity" line changed.
- Build after the move: same 5 files, same hashes ("manifest identical: True"; `git status --short public` clean).
- Audit. Command CI runs: `npm audit --omit=dev --audit-level=high` in web/ (shadcn stays in dependencies, so its four moderate advisories are in scope of `--omit=dev`). Output: "4 moderate severity vulnerabilities" (minimatch GHSA-g3hv-75wg-m249 > @ts-morph/common > ts-morph > shadcn), exit 0. Plain `npm audit --omit=dev` exits 1 on the same four. They are in the shadcn CLI's chain (build code); only shadcn's tailwind.css reaches public/ (M13 grepped the built files for minimatch, ts-morph, globparts, shadcn: none).
- D31 appended to docs/DECISIONS.md.

## Verification (offline)
- `py tasks.py lint` (first commit): "175 files already formatted", ruff check passed, exit 0.
- `py tasks.py test`: "498 passed, 1 deselected in 34.91s" after the IP_HASH_SALT change (449 at 04b903a; 496 at the first commit: +47 new, -1 removed deps-probe test; +2 for the salt: one parametrized case in each of test_api_blocks and test_production_env). `py tasks.py lint`: exit 0.
- `py tasks.py web-lint`: two warnings only (ui/button.tsx:66, ui/badge.tsx:48). `py tasks.py web-test`: "Test Files 10 passed (10)", "Tests 71 passed (71)". `py tasks.py web-build`: built; public/ unchanged (git status clean).
- `py tasks.py bundle-check`: "Total bundle size: 230.40 MB (limit: 400.00 MB)" (M13: 230.40 MB).
- ci.yml parsed with yaml.safe_load (PyYAML 6.0.3): name "CI", triggers push and pull_request, 13 steps.
- Local smoke (`py tasks.py smoke --url http://127.0.0.1:8000 --local --pipelines baseline`, LANGSMITH_TRACING=false, server started through a scratchpad launcher that installs the budget recorder, see Deviations 8). Budget pre-check: openai/gpt-oss-120b 8,000 tokens 6 requests: fits (200,000 free); gemini-embedding-001 500 tokens 2 requests: fits (922 free). After the run: gpt-oss-120b 1 request, 1,870 tokens; embeddings 79 requests (1 new), 925 tokens.
```
check                       result  detail
1 GET / page and CSP        PASS    200 text/html, title, CSP
2 GET / security headers    SKIP    --local
3 /assets cache headers     SKIP    --local
4 /results.json             SKIP    --local
5 /api/health               PASS    ok, env local, commit local
6 /api/pipelines            PASS    baseline, corrective, self_rag
7 /api/deps-probe is gone   PASS    404
8 POST /api/ask validation  PASS    422
9 ask baseline              PASS    first event 3.2s, total 5.3s, 5 events
```
  Server stopped (port 8000 not listening).

## cefed41 rewrite (approved once by the human)
- Before: cefed41 was on no remote (`git fetch origin`; `git branch -r --contains cefed41` printed nothing; `git ls-remote origin` showed no ref at cefed41; origin/main = 04b903a).
- tests/test_secret_scan.py now builds every fake value at run time from parts (`"gsk" + "_" + "A" * 24`, `KEY = "_K" + "EY"`, `TOKEN = "_TO" + "KEN"`, used in the temporary .env, the assignment fixtures and the expected output). No scanner rule was exempted or weakened; the tests still prove every rule fires (7 tests pass). A self-scan of the file with scan_line found 0 hits.
- Procedure: `git stash push -- docs/progress/M14-production-deploy.md`, `git reset --soft 04b903a`, stage, commit, `git stash pop`.
- Old hash cefed41, new hash ef0151a. `git diff cefed41 HEAD --stat` (taken before the salt commit): only tests/test_secret_scan.py (10 insertions, 6 deletions). No attribution trailer was added (AGENTS.md forbids one).
- `secret_scan.py --range origin/main..HEAD` after the rewrite: "findings: 0".

## IP_HASH_SALT required in production
- src/ragdocs/api/startup.py: IP_HASH_SALT added to REQUIRED_KEYS; the RuntimeError names "IP_HASH_SALT is missing", never a value; locally the absence logs one WARNING like the other missing settings. .env.example comment updated.
- Tests changed (all in 7aa5c2e):
  - tests/test_api_blocks.py: SECRETS gets "ip_hash_salt": "fake-salt-0000" (so the parametrized test_production_requires_each_secret now also covers IP_HASH_SALT, and complete-production tests get a salt). test_local_never_raises_and_warns: the expected warning count 5 became 6 and it asserts IP_HASH_SALT is among them. This is the one change beyond "add a fake salt"; it follows directly from the requested WARNING, so I made it and record it here.
  - tests/test_api_stream.py: SECRETS gets the same fake salt (complete production configuration).
  - tests/test_production_env.py: IP_HASH_SALT added to REQUIRED_REPORTS, so the remove-one-variable loop covers it.
- `py tasks.py lint`: exit 0; `py tasks.py test`: "498 passed, 1 deselected in 34.91s".

## Public-history scan (history already on origin, up to 04b903a)
- 33 commits are reachable from 04b903a; the single root commit is e514f80d5d739c26fd7730358efad011cdeec49b.
- Range form: `<root>..04b903a` excludes the root's own diff (it covers 32 commits; 7 findings), so I also ran `secret_scan.py --range 04b903a` (the rev-list form of a single revision, which scans every commit including the root: 33 commits, 509 blobs, 19.83 MB). Result: 7 findings, all rule "assignment", no key pattern, no .env value, no oversized blob, no tracked .env/cache/.venv/node_modules file.
  | commit | path:line | name | verdict |
  | 00d3d859e86a | src/ragdocs/pipelines/agentic/nodes.py:36 | CHARS_PER_TOKEN | false positive: an integer constant |
  | a33490b14ba9 | tools/ragas_score.py:56 | CHARS_PER_TOKEN | false positive: integer constant |
  | 7ee734e8e791 | src/ragdocs/providers/embeddings.py:21 | CHARS_PER_TOKEN | false positive: integer constant |
  | 1ca68efba7f6 | src/ragdocs/tracing.py:31 | ENV_API_KEY | false positive: the value is an ALL-CAPS environment variable name |
  | f82849a844c2 | tests/test_websearch.py:14 | FAKE_KEY | false positive: test fixture, the value contains "fake"/"test"; it starts with a provider prefix but matches no key pattern and no .env value |
  | 1ca68efba7f6 | tests/test_tracing.py:23 | FAKE_KEY | false positive: same |
  | 9b6ef85dcd3c | tools/index_sanity.py:45 | GOOGLE_API_KEY | false positive: code that checks a line for the variable name while parsing .env, no value |
  Values were inspected only by shape (integer, ALL-CAPS name, length, first 5 characters of the two fixtures); none was printed.
- Images in the 04b903a tree (13 PNG screenshots, each added once and never changed; 2 favicon.svg files are vector text): all viewed.
  | file | result |
  | ui-s1-static, ui-baseline, ui-corrective, ui-self-rag, ui-dark, ui-mobile | pass (app only) |
  | langsmith-baseline-trace, langsmith-self-rag-trace, langsmith-three-way-comparison | pass |
  | langsmith-baseline-experiment, langsmith-baseline-vs-corrective, langsmith-eval-item, langsmith-corrective-trace | ACCEPTED by the human: they show the account display name "Ds Bilal" and (one) a workspace id in a URL fragment; a display name and a workspace id are not credentials. They stay. |
  No image shows a key, token or e-mail address.

## Clean-clone rehearsal
Second rehearsal, clone of HEAD 7aa5c2e under %TEMP%\m14-rehearsal (no .env, cache/ or untracked file), PIP_DEFAULT_TIMEOUT=120, pip's normal cache (tasks.py setup does not disable it), `py -3.12 tasks.py setup` for step 4 (the default `py` is 3.13.5), CI steps 4 to 13 in order. Every step exited 0 (the 45-minute limit was not reached):
| step | exit | duration |
| 4 setup | 0 | 140.2 s |
| 5 lint | 0 | 1.0 s |
| 6 test ("498 passed, 1 deselected in 41.76s") | 0 | 44.7 s |
| 7 bundle-check ("Total bundle size: 230.37 MB") | 0 | 97.0 s |
| 8 web-install | 0 | 40.9 s |
| 9 web-lint | 0 | 1.1 s |
| 10 web-test | 0 | 1.4 s |
| 11 web-build | 0 | 1.5 s |
| 12 public/ matches a fresh build (git status --porcelain -- public/ empty) | 0 | 0.3 s |
| 13 npm audit --omit=dev --audit-level=high | 0 | 1.3 s |
Total about 330 s on Windows with a warm pip cache. No test needed an untracked or ignored file. The earlier rehearsal on cefed41 (before the rewrite) also passed every step; its setup took 2,410.8 s on a stalled network. Step 12 on Windows shows the build is reproducible; CI repeats it on Ubuntu. Unproven until the first CI run: everything on Ubuntu (all steps), and Windows with a cold cache. The clone was deleted.

## Push readiness
- `git fetch origin`: origin/main = 04b903a (not 4183f16, see Deviations 1). `git rev-list --count origin/main..HEAD`: 2 commits, first "M14 (1/2): production hardening" (ef0151a), last "M14 (1/2): require IP_HASH_SALT in production" (7aa5c2e); the record commit makes 3. `git merge-base --is-ancestor origin/main HEAD`: exit 0.
- Tags (all annotated; no lightweight tag exists):
  | tag | type | target commit | on origin (peeled) |
  | eval-set-v1 | tag (annotated) | c92688dd35816e0133517033f53db22d3b233396 | yes, same target |
  | v1-baseline | tag (annotated) | a33490b14ba96dada0750a4082226fda09a0b8a2 | yes, same target |
  | v2-agentic | tag (annotated) | 56a5043633f81822900d2e9cf6856f6db2059f80 | no (to push) |
- Secret scan over origin/main..HEAD after each commit: "findings: 0" (24 blobs, 0.42 MB). The scan after the record commit is stated at the end of this file.
- Images in origin/main..HEAD: none added. All images on origin were checked (see above).
- Push size: `git rev-list --objects origin/main..HEAD` piped to `git cat-file --batch-check`: 42 objects listed (one printed "missing" and was not counted), 454,103 bytes = 0.43 MB uncompressed, before the record commit.

## Decisions made
- D31 (above). The audit level is high because shadcn's CSS is bundled (see D31).
- Header rules are written so no two rules set the same header on one path; the open questions in 1b therefore cannot change the result for Cache-Control.
- Aliases keep the field names; the UPSTASH_ pair wins; the read-only token is never accepted.
- `py tasks.py smoke` takes extra arguments after the URL without `--` (parse_known_args, smoke only; every other command still rejects unknown arguments).
- Human decisions of 2026-11-23: fixtures built from parts without exempting any rule; a one-time local rewrite of the unpushed cefed41; scan of the public history; the four LangSmith screenshots stay (accepted); IP_HASH_SALT required in production; rehearsal retried with limits.

## Deviations from the prompt and from the build-plan M14 spec
The build-plan M14 text was not re-read in this session; differences from it beyond the prompt's own additions are not listed.
1. The first prompt says origin/main is at 4183f16 and everything from M04 is local. After `git fetch origin`, origin/main is 04b903a (M13); `git reflog show origin/main` shows "update by push" entries: M04 to M13 were pushed by the human earlier. The push range is therefore M14 commits only, and the first scan did not cover the public history (done in session 2 of the instructions, see "Public-history scan").
2. radix-ui classified as bundled although the literal source-map rule says build-only (npm split note).
3. Audit command is `npm audit --omit=dev --audit-level=high` (the prompt's second branch, since shadcn stayed).
4. The local smoke ran against a server started by a scratchpad launcher (budget recorder installed, then `uvicorn.run("ragdocs.api.local:app")`) instead of `py tasks.py dev`, as in M12, to follow the AGENTS.md rule that every live call is recorded. The launcher is not committed.
5. `py tasks.py setup` in the rehearsals was run as `py -3.12 tasks.py setup` (the default `py` here is 3.13.5 and tasks.py refuses it).
6. The first secret scan reported three findings (fake fixtures); I stopped as instructed. The human then approved fixing the fixtures and one local rewrite; the scan is now clean.
7. test_local_never_raises_and_warns changed its count from 5 to 6 warnings (see "IP_HASH_SALT required in production"); the instruction allowed only a fake salt in tests, but the requested WARNING requires this assertion change.

## Known issues and limitations
- The Upstash integration variable names, the prefix option and header rule precedence are unverified in the docs (Step 1a, 1b); they are checked in production (S2 handoff).
- The CSP and other vercel.json headers are only tested as configuration; they are first observed on a real deployment in S2.
- Upstash timeout is set through a private attribute of the pinned upstash-redis 1.8.0 (`redis._http._client.timeout`; M12). No change now. A version upgrade must re-check it; a test added in M12 builds a real limiter to catch a rename.
- Four LangSmith screenshots on the public repository show the account display name and a workspace id; accepted by the human (not credentials).
- The npm audit reports 4 moderate advisories in the shadcn CLI chain (build code); accepted under D31 and reviewed by hand when dependencies change.
- The secret scan's generic "assignment" rule produces false positives on constants named *_TOKEN or *_KEY (7 in the public history, all reviewed above); the rule stays as is.

## Open questions for the human
- None open. Resolved on 2026-11-23: the three scan findings (fixtures rebuilt, cefed41 rewritten once), the public screenshots (accepted), IP_HASH_SALT (now required).

## Proposed follow-ups (out of scope)
- Add a per-call timeout to Tavily searches (M12 follow-up, still open).
- Optionally add an allow-list of reviewed false positives to secret_scan.py (a decision for the human; not done).

## Prerequisites for the next module
- S2 handoff below.

## S2 handoff
Push commands (S2; from the repository root; PowerShell)
1. `git status` must be clean and `git log --oneline -4` must show the three M14 commits above 04b903a (ef0151a production hardening, 7aa5c2e IP_HASH_SALT, the push readiness record). `.venv\Scripts\python tools\secret_scan.py --range origin/main..HEAD` must print "findings: 0".
2. `git push origin main`
3. Tags: all three local tags are annotated and none is lightweight. eval-set-v1 and v1-baseline are on origin with the same targets. Push the missing one by name: `git push origin v2-agentic`. (`git push --follow-tags origin main` would also send v2-agentic because it is annotated and reachable.)
4. Watch the CI run for the pushed commit on GitHub (Actions tab, workflow "CI", Ubuntu and Windows). Do not enable the Vercel deployment before CI is green.

Vercel dashboard steps for Bilal (Production scope only; S2 does not use the Vercel CLI)
1. Production keys (quota scope from Step 1d): Groq: a key in a separate Groq organization for a separate quota (limits are per organization; keys in one organization share it); Google AI Studio: a key from a separate Google Cloud project (limits are per project); Tavily: a key on his account (all keys on one account share the rate limit; credits assumed per account). With the same organization, project or account as the eval keys the quotas are shared.
2. Vercel project: confirm it is connected to the GitHub repository (the URL the origin remote uses) and to branch main.
3. Add the Upstash integration: project > Storage (Marketplace) > Upstash for Redis > create or connect a database in the region closest to the function region, select the Production environment, keep the default environment variable prefix (do not set a custom one), then read the variable names the dashboard shows. Expected: KV_REST_API_URL and KV_REST_API_TOKEN. Settings accepts UPSTASH_REDIS_REST_URL/_TOKEN and KV_REST_API_URL/_TOKEN only; any other names need a code change, so tell S2 before the first deploy.
4. Generate IP_HASH_SALT himself: in his own terminal run `py -c "import secrets; print(secrets.token_hex(32))"` and paste the output directly into Vercel (never into chat, a file or a commit). Production now refuses to start without it.
5. Settings > Environment Variables, Production only: GROQ_API_KEY, GOOGLE_API_KEY, TAVILY_API_KEY, IP_HASH_SALT (marked Sensitive); RAGDOCS_ENV = production; LANGSMITH_TRACING = false; LLM_MAX_RETRIES = 1. Mark the two Upstash variables Sensitive if the dashboard allows it. Do not set anything from the "Do not set" list. Exact table: "Vercel Production env vars" above.
6. Redeploy (variables only take effect for new deployments).
7. Report back to S2 (S2 asks for each): the connected Git repository, production branch, root directory, framework preset, build and install command overrides (all should be empty/default: Vercel does not run npm or a build, public/ is committed), function region, production domain, Deployment Protection setting.

S2 checks in production (not confirmed in the documentation during S1)
- The variable names the Upstash integration injects, whether a prefix option exists and its default, and which token is read-only (S2 reads the names in the dashboard; values are never read or shown).
- That "/(.*)" in vercel.json matches "/" (smoke check 1: CSP on GET /) and which value wins if two header rules ever match (none do today).
- That vercel.json headers (CSP etc.) do or do not reach /api/ responses from the Python function, and that the function's own Cache-Control ("no-cache, no-transform") on the SSE stream is not replaced.
- Whether the production domain is public with the project's Deployment Protection setting (`curl.exe -I https://<domain>/`: 200 means public).
- That frames arrive progressively through Vercel's Python runtime (`tools/sse_probe.py --base-url`), the `pipeline=... outcome=...` INFO lines appear in Vercel's logs, and X-Forwarded-For is read correctly (M12 carry-over).
- Unproven in S1 and proved by the first CI run: all CI steps on Ubuntu, and Windows with a cold cache (the Windows rehearsal passed every step; see above).

Expected CI duration: the Windows rehearsal took about 330 s with a warm pip cache (setup 140 s, tests 45 s, bundle-check 97 s, npm ci 41 s, the rest under 10 s); a cold cache or a slow network can add minutes (one earlier rehearsal needed 40 minutes for pip alone). The job timeout is 30 minutes; if the first run times out, tell the human.

Smoke usage after deploy
- `py tasks.py smoke --url https://<production domain> --no-asks` first (no quota), then `py tasks.py smoke --url https://<production domain>` (3 valid asks, one per pipeline, 15 s apart; the per-IP limit is 5 per hour and the global cap 32 per day; any ask uses production quota). A failing row names the cause; a 429 or 503 is shown with its body.
- Check by hand once: `curl.exe -I https://<production domain>/` (security headers, no-cache), one /assets/ file (immutable), /api/health ("env":"production").

Upstash private-attribute note (carry-over 6)
`build_redis` sets the Upstash timeout through a private attribute of the pinned upstash-redis 1.8.0 (`redis._http._client.timeout`). No change in M14. Any upgrade of upstash-redis must re-check it; a test added in M12 builds a real limiter to catch a rename.