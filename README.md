# Deep Research Scaffold

This is a clean scaffold extracted from the `deep_research` architecture.
It keeps the reusable shape and removes demo-specific providers, heavy
external services, generated files, and course-specific comments.

## Architecture

```text
front/
  Vite + Vue client
  - submits research requests
  - consumes Server-Sent Events

app/
  app_main.py
  backend/
    config/      FastAPI/runtime settings
    router/      health and research endpoints
    schemas/     request/response models
    service/     workflow service and SSE bridge
  research_agents/
    config.py    workflow config loader
    state.py     LangGraph state contract
    graph.py     node wiring and route decisions
    nodes.py     node implementations
    tools.py     pluggable retrieval/search tools
    adapters/    LLM adapter protocol and default stub
    memory/      memory interface and in-memory implementation
```

## Workflow

```text
START
  -> intent
    -> direct_answer -> END
    -> plan
      -> web_search
      -> local_rag
      -> evidence_judge
      -> analyze
        -> reflect -> web_search/local_rag
        -> write -> END
```

The default implementation is deterministic and runs without API keys. Replace
the adapters in `app/research_agents/adapters/` and `app/research_agents/tools.py`
when you connect a real LLM, web search, vector database, or long-term memory.

## Backend Quick Start

```powershell
cd deep_research_scaffold
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd app
uvicorn app_main:app --reload --port 8000
```

Health check:

```powershell
curl http://127.0.0.1:8000/api/v1/health
```

Run once:

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/research/run `
  -H "Content-Type: application/json" `
  -d "{\"query\":\"Compare RAG and multi-agent research workflows\"}"
```

## Frontend Quick Start

```powershell
cd deep_research_scaffold/front
npm install
npm run dev
```

The Vite dev server proxies `/api` to `http://127.0.0.1:8000`.

## Extension Points

- `LLMClient` in `app/research_agents/adapters/llm.py`
- `SearchTools` in `app/research_agents/tools.py`
- `MemoryStore` in `app/research_agents/memory/store.py`
- `ResearchState` in `app/research_agents/state.py`
- route conditions in `app/research_agents/graph.py`

## Production Checklist

- Replace `RuleBasedLLMClient` with a real provider.
- Add source allowlists, citation validation, and retry policies.
- Move memory from `InMemoryMemoryStore` to Redis/Postgres/vector DB.
- Add tests for route decisions, JSON parsing, citations, and SSE events.
- Keep secrets in `.env`, never in `config.json`.

