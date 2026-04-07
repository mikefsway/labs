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
- **Target DB**: Supabase with pgvector (same as MostMaker/fraglets)

## Scraper Pipeline

1. `scraper/fetch_orgs.py` — Fetch all org records from UKAS REST API
2. `scraper/fetch_schedules.py` — Discover schedule PDF URLs from media API  
3. `scraper/parse_schedule.py` — Parse schedule PDFs into structured capability JSON

## Key Findings

- UKAS WP REST API is public and unauthenticated
- ACF fields are not exposed via REST (address, contact etc come from PDF parsing)
- Testing schedules have 3 columns: Materials/Products | Test Type/Range | Standards
- Calibration schedules differ: Measured Quantity/Instrument | Range | Expanded Uncertainty
- robots.txt permits API access; no visible T&Cs prohibiting data reuse
- BHB v William Hill precedent favours us on database right

## Commands

```bash
# Activate venv
source venv/bin/activate

# Test PDF parser on a sample
python scraper/parse_schedule.py /tmp/sample_schedule.pdf

# Fetch all organisations
python scraper/fetch_orgs.py

# Discover schedule PDF URLs
python scraper/fetch_schedules.py
```

## Next Steps

- Batch PDF download pipeline (rate-limited, polite)
- Run parser across all downloaded PDFs
- Normalise capability data (clean section numbers, standardise test method refs)
- AI enrichment: generate searchable descriptions per capability
- DB schema + embedding pipeline (Supabase/pgvector)
- API/MCP layer for agent discovery
