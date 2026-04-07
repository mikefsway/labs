# Labs - Contract Lab Testing Discovery

Semantic search over UKAS-accredited lab capabilities. Extracts structured capability data from UKAS schedule PDFs and makes it discoverable via embeddings + API.

## Architecture

- **Data source**: UKAS (United Kingdom Accreditation Service) WordPress site
  - REST API: `/wp-json/wp/v2/organisation`, `/wp-json/wp/v2/media`, `/wp-json/wp/v2/schedule`
  - Schedule PDFs: `wp-content/uploads/schedule_uploads/{parent_id}/{accred_num}{Type}-{Single|Multiple}.pdf`
  - ~1,177 testing labs, ~373 calibration labs, ~3,474 schedule PDFs
- **Data model**: "Capability fraglets" — one record per lab capability (not per lab)
  - Each lab produces 30-100+ capability records
  - Structured fields: materials/products, test type, standards, range
  - Header: lab name, accreditation #, address, contact, email, website
- **Target DB**: Supabase with pgvector (repurposed "Test" project)
  - Project ID: ltbkkikpqijldicdjhpx
  - URL: https://ltbkkikpqijldicdjhpx.supabase.co
  - Tables: `labs` (1,524 rows), `capabilities` (14,298 rows)
  - Embedding: vector(512) column on capabilities, IVFFlat index (lists=100)

## Scraper Pipeline

1. `scraper/fetch_orgs.py` — Fetch all org records from UKAS REST API
2. `scraper/fetch_schedules.py` — Discover schedule PDF URLs from media API  
3. `scraper/parse_schedule.py` — Parse schedule PDFs into structured capability JSON
4. `scraper/batch_download.py` — Batch download + parse all PDFs, resumable

## Key Findings

- UKAS WP REST API is public and unauthenticated
- ACF fields are not exposed via REST (address, contact etc come from PDF parsing)
- Testing schedules have 3 columns: Materials/Products | Test Type/Range | Standards
- Calibration schedules differ: Measured Quantity/Instrument | Range | Expanded Uncertainty
- robots.txt permits API access; no visible T&Cs prohibiting data reuse
- BHB v William Hill precedent favours us on database right
- Parser QA'd on 10 random samples — accuracy verified for capability content
- Some labs have both testing + calibration schedules (same accred#, deduped on insert)

## Commands

```bash
# Activate venv
source venv/bin/activate

# Full pipeline
python scraper/fetch_orgs.py
python scraper/fetch_schedules.py
python scraper/batch_download.py

# Test parser on a single PDF
python -c "import sys; sys.path.insert(0,'scraper'); from parse_schedule import parse_schedule; import json; print(json.dumps(parse_schedule('path/to/file.pdf'), indent=2))"
```

## Search & API

- **Hybrid search**: tsvector full-text + pgvector cosine similarity, combined via RRF (Reciprocal Rank Fusion)
  - `search_tsv` generated tsvector column + GIN index on capabilities
  - `hybrid_search_capabilities(query_text, query_embedding, match_count, filter_region)` SQL function
  - Fixes the "asbestos air sampling" problem — keyword match boosts domain-specific results
- **FastAPI app** (`app/`): config, database, services (embedding, hybrid_search), routers (search, labs)
  - `GET /api/search?q=...&limit=&region=` — hybrid search
  - `POST /api/match` — multi-capability matching (find labs covering multiple needs)
  - `GET /api/labs/{lab_id}` — full lab details + capabilities
  - `GET /health` — health check
- **Website**: Jinja2 templates + Tailwind Play CDN + vanilla JS, search-first B2B design
- **MCP server** (`labs_mcp/`): 3 tools — search_lab_capabilities, get_lab, find_labs_for_multiple_tests
  - Combined ASGI via `asgi.py` (FastAPI at /, MCP at /mcp)
  - API key auth on MCP endpoint (LABS_MCP_API_KEYS env var)

## Embedding Pipeline

- `scraper/generate_embeddings.py` — Batch-embeds capabilities.search_text via OpenAI text-embedding-3-small (512 dims)
  - Resumable: only processes rows where embedding IS NULL
  - All 14,298 capabilities embedded as of 2026-04-07
- `scraper/search.py` — CLI search (legacy, uses pure vector search)

## Commands

```bash
# Development
source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Production (Render)
gunicorn asgi:app -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT
```

## Deployment

- **Hosting**: Render (render.yaml)
- **Env vars**: SUPABASE_URL, SUPABASE_SERVICE_KEY, OPENAI_API_KEY, LABS_MCP_API_KEYS

## Next Steps

- Normalise capability data (clean section numbers, standardise test method refs)
- AI enrichment: generate searchable descriptions per capability
- Pick domain name and deploy
