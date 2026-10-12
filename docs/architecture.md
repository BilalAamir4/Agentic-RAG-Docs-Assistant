# Architecture Overview

The system operates across two decoupled environments: an offline pipeline executed locally on Windows 11 and an online production service hosted on Vercel running Linux. Offline workflows handle documentation ingestion, content chunking, dual-index construction (BM25 sparse tokens and Gemini 768-dimensional dense embeddings), and systematic pipeline evaluation over a frozen 50-question benchmark. All offline operations output reproducible, deterministic artifacts into versioned repository directories, culminating in a committed in-memory index that eliminates the operational complexity and cost of maintaining dedicated external vector databases.

Online inference is designed for free-tier serverless execution on Vercel. A static HTML, CSS, and vanilla JavaScript interface hosted in `public/` communicates directly with a FastAPI endpoint defined in `api/index.py`. Upon cold start, the FastAPI service loads the committed index into memory and provides sub-millisecond retrieval routines, supporting three interchangeable architectures: a baseline hybrid retrieval pipeline, a corrective RAG workflow with targeted web fallbacks, and an adaptive self-RAG state machine with automated critique and regeneration loops. Production abuse protection is managed via Upstash Redis rate limiting, while external model providers (Groq, Gemini, Cohere, Tavily) are invoked strictly through stateless API calls.

## Repository Layout

```text
.
├── api/
│   └── index.py
├── data/
│   ├── eval/
│   │   └── .gitkeep
│   ├── index/
│   │   └── .gitkeep
│   └── processed/
│       └── .gitkeep
├── docs/
│   ├── progress/
│   │   └── PROGRESS.md
│   ├── architecture.md
│   └── DECISIONS.md
├── public/
│   └── index.html
├── results/
│   └── runs/
│       └── .gitkeep
├── scripts/
│   └── .gitkeep
├── src/
│   └── ragdocs/
│       ├── api/
│       │   └── __init__.py
│       ├── eval/
│       │   └── __init__.py
│       ├── generation/
│       │   └── __init__.py
│       ├── index/
│       │   └── __init__.py
│       ├── ingest/
│       │   └── __init__.py
│       ├── pipelines/
│       │   ├── agentic/
│       │   │   └── __init__.py
│       │   └── __init__.py
│       ├── providers/
│       │   └── __init__.py
│       ├── retrieval/
│       │   └── __init__.py
│       ├── __init__.py
│       ├── config.py
│       ├── io_utils.py
│       ├── logging_setup.py
│       └── schemas.py
├── tests/
│   ├── test_config.py
│   ├── test_io_utils.py
│   └── test_schemas.py
├── tools/
│   └── .gitkeep
├── .env.example
├── .gitattributes
├── .gitignore
├── .python-version
├── .vercelignore
├── AGENTS.md
├── pyproject.toml
├── requirements-dev.txt
├── requirements.txt
└── tasks.py
```
