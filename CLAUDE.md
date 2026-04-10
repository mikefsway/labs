# LabCurate — Testing Laboratory Advisor

labcurate.com — B2B testing laboratory advisor. Curates UKAS-accredited lab capabilities, matches against 45k+ standards, and provides AI-powered recommendations.

## Architecture

- **Data sources**:
  - UKAS WordPress REST API + schedule PDFs (1,524 labs, 14,298 capabilities)
  - ISO Open Data (44,807 standards with scopes)
  - ASTM store scrape (505 standards with titles/scopes)
- **Database**: Supabase with pgvector (project `ltbkkikpqijldicdjhpx`)
  - `labs` — 1,524 rows: name, accreditation #, address, contact, lat/lng, schedule_pdfs JSONB
  - `capabilities` — 14,298 rows: materials_products, test_type, standards, embedding vector(512), search_tsv
  - `lab_fraglets` — 1,210 rows: AI-generated descriptions, additional JSONB, embedding vector(512)
  - `lab_sites` — 88 rows: multi-site labs with addresses, lat/lng, capabilities_summary, site_code
  - `standards` — 77,261 rows (45,312 with embeddings): ISO + ASTM, reference, title, scope
  - IVFFlat/GIN indexes on embedding and search_tsv columns
- **Backend**: FastAPI + MCP server, combined ASGI via `asgi.py`
- **Frontend**: Jinja2 templates + Tailwind Play CDN + vanilla JS (no build step)
  - Advisor UI: textarea input, "Find labs" button, search only on submit
  - Dark theme: DM Mono + Plus Jakarta Sans fonts
- **LLM**: GPT-5.4-mini for recommendations (use `max_completion_tokens` not `max_tokens`)
- **Geocoding**: postcodes.io (free, no key) for UK postcodes and place names
- **Hosting**: Render (render.yaml), single web service

## Project structure

```
app/
  main.py                  # FastAPI app + basic auth + page routes
  config.py                # Pydantic Settings from .env
  database.py              # Supabase service client factory
  routers/
    search.py              # GET /api/search, GET /api/search/labs, POST /api/match
    labs.py                # GET /api/labs/{lab_id}
  services/
    embedding.py           # OpenAI text-embedding-3-small (512 dims)
    hybrid_search.py       # Orchestrates embed + RPC calls (capabilities, fraglets, standards)
    recommendation.py      # GPT-5.4-mini advisor: standards advice + lab grouping + cross-reference
    geocode.py             # postcodes.io geocoding
  templates/               # Jinja2: base.html, index.html, lab.html
  static/                  # css/style.css, js/search.js
labs_mcp/
  server.py                # FastMCP: 4 tools for AI agent access (search_lab_capabilities, search_labs, get_lab, find_labs_for_multiple_tests)
asgi.py                    # Combined ASGI: FastAPI at /, MCP at /mcp
scraper/
  fetch_orgs.py            # Fetch org records from UKAS REST API
  fetch_schedules.py       # Discover schedule PDF URLs from media API
  parse_schedule.py        # Parse schedule PDFs into structured capability JSON
  batch_download.py        # Batch download + parse all PDFs, resumable
  generate_embeddings.py   # Batch-embed capabilities (resumable, 100/batch)
  embed_fraglets.py        # Embed lab_fraglets (title+brief+detail+tags)
  embed_standards.py       # Embed standards (reference+title+scope)
  scrape_astm.py           # Scrape ASTM titles from store.astm.org (resumable)
  scrape_astm_guess.py     # Year-guess variant for ASTM refs without year suffix
  load_astm_standards.py   # Load scraped ASTM into Supabase + embed
  search.py                # Legacy CLI search (superseded)
data/                      # Scraped data (gitignored), schedule_pdfs.json, astm_standards.json
render.yaml                # Render deployment config
```

## Recommendation flow

1. User submits query via advisor UI
2. Backend in parallel: embed query → search lab_fraglets + search standards + geocode location
3. GPT-5.4-mini receives: query + top 3 standards (ref+title+scope) + top 20 labs (brief+tags)
4. LLM returns JSON: `{standards_advice, key_standards, groups[{heading, explanation, lab_ids}]}`
5. If key_standards identified: cross-reference against capabilities table (`find_labs_by_standard` RPC)
6. Confirmed labs added as top group, even if not in original search results
7. Frontend renders: standards guidance panel → grouped lab cards interleaved with explanations

## Search RPCs (Supabase)

- `hybrid_search_capabilities(query_text, query_embedding, match_count, filter_region)` — capabilities search
- `hybrid_search_lab_fraglets(query_text, query_embedding, match_count, filter_region)` — fraglet search, returns lat/lng + matched_sites
- `search_standards(query_text, query_embedding, match_count)` — standards search
- `find_labs_by_standard(standard_ref)` — ILIKE match on capabilities.standards
- `haversine_km(lat1, lng1, lat2, lng2)` — distance calculation

All search RPCs check `lab_sites.address` in addition to `labs.address` for region filtering.

## API endpoints

- `GET /api/search?q=...&limit=&region=` — capabilities search
- `GET /api/search/labs?q=...&limit=&location=&recommend=true` — advisor search with recommendations
- `POST /api/match` — multi-capability matching
- `GET /api/labs/{lab_id}` — lab detail + capabilities + fraglet + sites + PDF links
- `GET /health` — health check

## Lab fraglet generation

- 1,210/1,524 done. 314 remaining (bulk 1-14 caps, heavy 15-99, monster 100+)
- 5 Sonnet agents × 25 labs per round = 125 labs/round
- Batching by capability count — see `feedback_fraglet_agent_batching.md`
- Use $frag$ dollar-quoting for SQL inserts
- After insert: run `python -m scraper.embed_fraglets` to embed new fraglets

### Brief field style rules

- **NEVER include the lab name** in the `brief` field. The lab name is displayed separately on the results page and is blurred for unauthenticated users — including it in the brief leaks the name and wastes space.
- **DO include the location** (town/city, county/region) — e.g. "Based in Ramsgate, Kent, provides..."
- Start with either "Based in [location], provides/offers..." or directly with the verb "Provides UKAS-accredited..."
- One to two sentences. Concrete language, no filler, no clichés, no superlatives.
- The `detail` and `title` fields must also not include the lab name.

## IP protection

- Lab detail page shows `brief` + structured `additional` capabilities + UKAS PDF links
- Full `detail` field (generated prose) is NOT exposed to users — used only for search ranking via embeddings
- Recommendation prompt uses brief + tags, not detail

## Key notes

- GPT-5.4-mini requires `max_completion_tokens` (not `max_tokens`) — 400 error otherwise
- Calibration schedules have different column structure (Range | Expanded Uncertainty instead of Standards)
- 88 multi-site labs: addresses were misclassified as capabilities, now in `lab_sites` table with site_code
- schedule_pdfs.json URLs stored in labs.schedule_pdfs JSONB (not predictable URL pattern)
- UKAS data is public; BHB v William Hill precedent favours factual data reuse

## Security

- **Prompt injection**: System/user message separation in LLM prompts. User input sanitised and truncated (500 char max). LLM output `lab_ids` validated against actual search results.
- **Input validation**: `max_length` constraints on all query parameters.
- **Supabase access**: Public endpoints use anon client (not service key). RLS enabled on all tables with SELECT-only anon policy.
- **Rate limiting**: slowapi (10-30 req/min per IP on search endpoints). Brute-force protection on Basic Auth (10 failures / 5 min).
- **MCP auth**: Fails closed (503) when API keys not configured. Timing-safe comparison (`secrets.compare_digest`) for MCP API keys.
- **Bot protection**: Honeypot field + Cloudflare Turnstile on magic link sign-in. Turnstile degrades gracefully when unconfigured. Client-side 30s cooldown between magic link requests.
- **Turnstile env vars**: `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY`. Warning logged when missing.

## Commands

```bash
source venv/bin/activate
uvicorn app.main:app --reload --port 8000          # Dev
python -m scraper.embed_fraglets                     # Embed new fraglets
python -m scraper.embed_standards                    # Embed standards (resumable)
python -m scraper.scrape_astm                        # Scrape ASTM (resumable)
python -m scraper.load_astm_standards                # Load ASTM into Supabase
```

## Agent-facing artifacts — keep these in sync

LabCurate has an MCP server and is listed in the fraglet ecosystem registry. Two files describe it to agents and must track code changes. When you make a **meaningful** change below, update the mapped artifact in the same commit and bump its `last-verified:` date.

"Meaningful" = MCP tool added/removed/renamed, parameter change, new search mode, auth change, new region/industry scope, standards corpus expansion that unlocks a new capability category. **Not** meaningful: scraper maintenance, embedding refreshes, dataset top-ups, UI/template polish.

| If you change...                                            | Update...                                                |
|-------------------------------------------------------------|----------------------------------------------------------|
| `labs_mcp/server.py` (any `@mcp.tool()`)                    | `app/templates/skill.md` AND `app/templates/llms.txt`    |
| `app/routers/**` (public REST endpoints — `/api/search`, `/api/match`, `/api/labs/{id}`) | `app/templates/llms.txt`             |
| `app/services/**` search-mode logic (keyword/vector/region blend) | `app/templates/skill.md` (usage guidance) |
| Region scope expands beyond UK                              | `app/templates/llms.txt`, `fraglets/site/services.json`  |
| Basic auth password / access model changes                  | `app/templates/skill.md` (setup section)                 |
| MCP URL, auth flow, or account requirement                  | `app/templates/skill.md`, `fraglets/site/services.json`  |

`skill.md` and `llms.txt` templates are at `app/templates/`. Routes are wired in `app/main.py` (`/skill.md`, `/llms.txt`, `/robots.txt`, `/sitemap.xml`, `/.well-known/mcp.json`). All six discovery paths are allowlisted in `basic_auth_middleware` so unauthenticated agents can reach them during the testing-phase password gate.

To check for drift manually: `python scripts/check_agent_artifacts.py`. Exits non-zero if any source file is newer than its artifact's `last-verified:` date.

Full rollout plan: `~/.claude/plans/agentic-welcoming-otter.md`.
