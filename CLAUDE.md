# LabScope — UKAS Lab Testing Discovery

B2B proof of concept: search-first discovery of UKAS-accredited lab testing capabilities. Part of the fraglets supply-side model — each capability is a discoverable, embeddable unit.

## Architecture

- **Data source**: UKAS (United Kingdom Accreditation Service) WordPress site
  - REST API: `/wp-json/wp/v2/organisation`, `/wp-json/wp/v2/media`
  - Schedule PDFs: ~3,474 PDFs containing structured capability tables
- **Database**: Supabase with pgvector (project `ltbkkikpqijldicdjhpx`)
  - `labs` table (1,524 rows): name, accreditation #, address, contact, email, website
  - `capabilities` table (14,298 rows): materials_products, test_type, standards, search_text, embedding vector(512), search_tsv tsvector
  - IVFFlat index on embedding (100 lists), GIN index on search_tsv
- **Backend**: FastAPI + MCP server, combined ASGI via `asgi.py`
- **Frontend**: Jinja2 templates + Tailwind Play CDN + vanilla JS (no build step)
  - Dark "precision instrument" theme: DM Mono + Plus Jakarta Sans fonts
  - Search-first design with example queries, about section, API/MCP docs inline
- **Hosting**: Render (render.yaml), single web service

## Project structure

```
app/
  main.py                  # FastAPI app + static mount + page routes
  config.py                # Pydantic Settings from .env
  database.py              # Supabase service client factory
  routers/
    search.py              # GET /api/search, POST /api/match
    labs.py                # GET /api/labs/{lab_id}
  services/
    embedding.py           # OpenAI text-embedding-3-small (512 dims)
    hybrid_search.py       # Orchestrates embed + RPC call + multi-match
  templates/               # Jinja2: base.html, index.html, lab.html
  static/                  # css/style.css, js/search.js
labs_mcp/
  server.py                # FastMCP: 3 tools for AI agent access
asgi.py                    # Combined ASGI: FastAPI at /, MCP at /mcp
scraper/                   # Data pipeline (fetch, parse, embed)
data/                      # Scraped data, market research, project plan
render.yaml                # Render deployment config
```

## Search

- **Hybrid search**: tsvector full-text + pgvector cosine similarity, combined via RRF (Reciprocal Rank Fusion, k=60)
  - `hybrid_search_capabilities(query_text, query_embedding, match_count, filter_region)` SQL function
  - Two CTEs ranked independently, FULL OUTER JOIN, missing ranks default to 1000000
  - Fixes short-query failures (e.g. "asbestos air sampling" now returns asbestos labs, not generic air sampling)
- **API endpoints**:
  - `GET /api/search?q=...&limit=&region=` — hybrid search
  - `POST /api/match` — multi-capability matching (find labs covering multiple needs)
  - `GET /api/labs/{lab_id}` — full lab details + all capabilities
  - `GET /health` — health check
- **MCP tools** (at `/mcp`):
  - `search_lab_capabilities(query, limit, region)`
  - `get_lab(lab_id)`
  - `find_labs_for_multiple_tests(queries[], limit, region)`
  - API key auth via `LABS_MCP_API_KEYS` env var (comma-separated, empty = open)

## Scraper pipeline

1. `scraper/fetch_orgs.py` — Fetch org records from UKAS REST API
2. `scraper/fetch_schedules.py` — Discover schedule PDF URLs from media API
3. `scraper/parse_schedule.py` — Parse schedule PDFs into structured capability JSON
4. `scraper/batch_download.py` — Batch download + parse all PDFs, resumable
5. `scraper/generate_embeddings.py` — Batch-embed capabilities (resumable, 100/batch)
6. `scraper/search.py` — Legacy CLI search (pure vector, superseded by hybrid)

## Commands

```bash
# Development
source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Production (Render)
gunicorn asgi:app -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT

# Scraper pipeline
python scraper/fetch_orgs.py
python scraper/fetch_schedules.py
python scraper/batch_download.py
python scraper/generate_embeddings.py
```

## Deployment

- **Hosting**: Render (render.yaml), single web service
- **Env vars**: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `OPENAI_API_KEY`, `LABS_MCP_API_KEYS`
- **Start command**: `gunicorn asgi:app -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`

## Key findings

- UKAS WP REST API is public and unauthenticated
- Testing schedules: 3 columns (Materials/Products | Test Type/Range | Standards)
- Calibration schedules differ (Measured Quantity | Range | Expanded Uncertainty)
- robots.txt permits API access; BHB v William Hill precedent favours data reuse
- Parser QA'd on 10 random samples — accuracy verified

## Next steps

- Normalise capability data (clean section numbers, standardise test method refs)
- AI enrichment: generate searchable descriptions per capability
- Pick domain name (candidates: LabScope, ScopeSearch, TestFind)
- Market research saved at `data/market_research.md`
- Full project plan at `data/project_plan.md`
