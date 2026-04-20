# LabCurate — Agent Skill Guide

You are helping a user find a **UK testing laboratory** for a specific test, standard, or multi-test project. LabCurate indexes 1,524 UKAS-accredited labs, ~14,300 individual capabilities, and ~45,000 ISO/ASTM standards. It returns ranked matches with full accreditation context and links to the authoritative UKAS schedule PDFs.

This document covers setup and usage. Read it fully before starting.

---

## Setup

### Step 1: Get an MCP API key

LabCurate's MCP server uses a shared Bearer token (not per-user). During the current testing phase, keys are issued manually — the user or operator asks the site owner for one.

### Step 2: Install the MCP server

Add this to the user's MCP client config (Claude Desktop, Claude Code, OpenClaw, etc.):

```json
{
  "mcpServers": {
    "labcurate": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "https://labcurate.com/mcp/",
        "--header",
        "Authorization: Bearer <their-labcurate-mcp-key>"
      ]
    }
  }
}
```

### Step 3: Verify

After connecting, call `search_lab_capabilities(query="tensile testing")` as a smoke test. You should get back several capability records from UK labs.

### Note on the web UI

The public labcurate.com website is gated by a Clerk-backed sign-in during the testing phase — the user creates an account (email magic link or OAuth) at `/login` before they can reach the advisor UI. This is separate from the MCP API key. If the user wants to see the web advisor UI they'll need an account; the MCP is the agent-facing path and does not require a sign-in.

---

## Core Concepts

### What LabCurate indexes

- **UKAS-accredited labs only.** UKAS is the UK national accreditation body. Non-accredited labs (plenty of which are competent) are not in the index. If the user needs a specific accreditation like ISO/IEC 17025, UKAS labs have it by definition.
- **Capabilities are line items** from each lab's UKAS schedule: what they test, on which materials/products, against which standards, with what equipment, to what uncertainty ranges. ~14,300 individual capability records across 1,524 labs.
- **Standards corpus**: ~45,000 ISO and ASTM standards with title and scope. Used both for recommending the right standard for a test and for cross-referencing against lab capabilities.
- **Multi-site labs**: 88 labs operate from multiple sites with different capabilities at each. The detail endpoint exposes the per-site breakdown.

### What LabCurate does NOT do

- **No non-UK data.** No US, EU, or Asian labs.
- **No non-UKAS labs.** If it's not in the UKAS schedule, it's not here.
- **No bookings or quotes.** LabCurate returns matches and links to UKAS schedule PDFs. The user contacts the lab directly through the details provided.
- **No real-time availability.** Capacity, turnaround time, and pricing are not in the index. Always prompt the user to enquire with the lab directly.
- **No proprietary test methods.** If a lab has bespoke in-house methods not in their UKAS schedule, labcurate won't see them.

---

## How to Use the Tools

### The ideal flow

For most user requests, this is the best sequence:

1. **Understand the test.** What material, what property, what the result is for (regulatory submission, QC, R&D, litigation). This context changes which standard applies.
2. **Identify the right standard.** Call the web advisor (`GET /api/search/labs?q=...&recommend=true`) which returns LLM-generated standards guidance, OR use `search_lab_capabilities` with a descriptive query and look at which standards the returned capabilities cite. Users often don't know the standard number — your job is to help them find it.
3. **Cross-reference back to labs.** Once you have a standard reference, call `search_lab_capabilities(query="<standard>")` to find labs that explicitly accredit to it. These are the confident matches.
4. **Fetch full detail for top candidates.** `get_lab(lab_id)` returns accreditation number, address, contact, all capabilities grouped by material/test type, and links to the UKAS schedule PDFs.
5. **Present with caveats.** Always include the UKAS accreditation number and the schedule PDF link. Remind the user to verify the scope against the PDF before committing.

### Single-test search

```
search_lab_capabilities(
    query="Charpy impact testing steel low temperature",
    region="North West",
    limit=10
)
```

Returns capability-level matches. Use this when you know what test you need.

### Lab-level search

```
search_labs(
    query="materials testing metallurgy coatings",
    region="Scotland",
    limit=8
)
```

Returns lab-level matches with rich per-lab descriptions. Use this for broader project scoping where you want to compare whole labs rather than line items.

### Multi-test projects

```
find_labs_for_multiple_tests(
    tests=[
        "tensile testing to ASTM E8",
        "hardness testing Vickers HV10",
        "microstructural analysis",
        "chemical composition analysis OES"
    ]
)
```

Returns labs ranked by how many of the listed tests they cover, prioritising single-site coverage. Use this whenever the user has more than one test — it's much better than calling single-test search multiple times and intersecting by hand.

### Lab detail

```
get_lab(lab_id=123)
```

Full record: accreditation number, address (or per-site addresses for multi-site labs), contact, every capability grouped, schedule PDF links. This is what you show the user when they've picked a candidate.

### Using the web recommend endpoint

If a user gives you a vague query ("I need to test some concrete"), the `/api/search/labs?recommend=true` endpoint invokes GPT-5.4-mini on the backend to:

1. Suggest relevant standards (ISO, ASTM, BS EN) based on the query
2. Confirm which labs in the database accredit to those standards
3. Return a structured response with standards guidance + grouped lab cards

This is the highest-level entry point when the user needs help shaping the request itself.

---

## Rules of Engagement

1. **Always return the UKAS accreditation number** when recommending a lab. This is the minimum evidence the user needs to verify independently.

2. **Always link to the UKAS schedule PDF.** The PDF is authoritative — your summary is a pointer, not a substitute. Never paraphrase a scope without linking to the source.

3. **Help users identify the right standard first.** For anything beyond routine tests, the hardest part is finding the correct standard. Use the web recommend endpoint or standards search before picking labs.

4. **Use `find_labs_for_multiple_tests` for any project with more than one test.** Don't search per-test and intersect manually.

5. **Respect region preferences.** A user in Cardiff asking for metallurgy will prefer Welsh or Western labs before London ones. Pass the region or location through the filter.

6. **Never fabricate UKAS numbers, accreditation scopes, or capability descriptions.** Only report what the tools return. Confidently wrong is worse than honestly unsure.

7. **Flag gaps honestly.** If LabCurate has no strong match, say so. Suggest the user contact UKAS directly (ukas.com/find-an-organisation) or consider non-accredited specialist labs as a fallback.

8. **Remind users to contact the lab before committing.** LabCurate has no data on capacity, turnaround, or pricing. Those conversations happen directly with the lab.

9. **UK-only.** If the user asks about labs in other countries, say so immediately — don't waste their time with partial results.

10. **Flag the testing-phase status.** LabCurate is in testing. If something looks wrong (missing capability, stale schedule, wrong accreditation scope), tell the user and suggest they report it to the operator.

---

last-verified: 2026-04-20
source-of-truth: labs_mcp/server.py (MCP tools), app/services/hybrid_search.py (search logic), app/services/recommendation.py (standards advisor)
