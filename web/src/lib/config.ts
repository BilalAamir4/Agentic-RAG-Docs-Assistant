/** Repository that "Source on GitHub" and "Full comparison" link to. */
export const REPO_URL = 'https://github.com/BilalAamir4/Agentic-RAG-Docs-Assistant'

/** API routes served by the FastAPI app (same origin). */
export const API_PIPELINES_PATH = '/api/pipelines'
export const API_ASK_PATH = '/api/ask'

/** Static results file, fetched at runtime so the cache header applies. */
export const RESULTS_PATH = '/results.json'

/** Longest question the API accepts. Matches Settings.max_question_chars in src/ragdocs/config.py. */
export const MAX_QUESTION_CHARS = 500

/** Shortest question the API accepts after trimming. */
export const MIN_QUESTION_CHARS = 3

/** Pipeline selected when the page loads. */
export const DEFAULT_PIPELINE = 'self_rag'

/** Characters of an example question shown on its button. */
export const EXAMPLE_PREVIEW_CHARS = 60

/** Seconds to wait after a 429 that names no Retry-After value. */
export const DEFAULT_RETRY_AFTER_S = 60

/** Messages for failures that have no server text. */
export const MSG_CONNECTION_CLOSED = 'The connection closed before an answer arrived.'
export const MSG_UNREADABLE = 'The server sent an unreadable response.'
export const MSG_NETWORK = 'Could not reach the server.'
export const MSG_SERVER = 'Something went wrong on the server.'
export const MSG_REJECTED = 'The request was not accepted.'
export const MSG_STOPPED = 'Stopped before an answer arrived.'
export const MSG_UNAVAILABLE = 'The service is temporarily unavailable.'

/** Link to the full comparison. It 404s until M14 pushes the repository. */
export const SUMMARY_URL = `${REPO_URL}/blob/main/results/summary.md`
