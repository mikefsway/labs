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

## Embedding & Search Pipeline

- `scraper/generate_embeddings.py` — Batch-embeds capabilities.search_text via OpenAI text-embedding-3-small (512 dims)
  - Resumable: only processes rows where embedding IS NULL
  - Reads credentials from `.env` (OPENAI_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY)
  - All 14,298 capabilities embedded as of 2026-04-07
- `scraper/search.py` — Semantic search CLI: embeds a query and calls `match_capabilities` RPC
  - Usage: `python scraper/search.py "tensile testing of steel"`
- `match_capabilities(query_embedding, match_count)` — Supabase SQL function for cosine similarity search
  - Joins capabilities → labs, returns lab_name, materials, test_type, standards, similarity score
- **Known limitation**: short queries (e.g. "asbestos air sampling") match generic concepts ("air sampling") over specific labs. Hybrid search (keyword boost + vector) would fix this.

## Next Steps

- Hybrid search: combine keyword filtering/boosting with vector similarity (RRF or keyword pre-filter)
- Normalise capability data (clean section numbers, standardise test method refs)
- AI enrichment: generate searchable descriptions per capability
- API/MCP layer for agent discovery
- Search UI or endpoint for "find me a lab that can test X"
