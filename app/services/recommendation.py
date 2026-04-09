"""
LLM recommendation layer — takes search results + relevant standards
and generates a structured, query-specific recommendation using GPT-5.4-mini.

Two-phase approach:
1. LLM identifies relevant standards and groups labs
2. If standards identified, cross-reference against capabilities for confirmed matches
"""

import json

from openai import AsyncOpenAI

from app.config import get_settings
from app.database import get_supabase_client

RECOMMENDATION_MODEL = "gpt-5.4-mini"


async def generate_recommendation(
    query: str,
    results: list[dict],
    standards: list[dict] | None = None,
    mode: str = "labs",
) -> dict | None:
    if not results:
        return None

    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    results_text = _format_results(results, mode)
    standards_text = _format_standards(standards) if standards else ""

    prompt = f"""Advise a user searching for UKAS-accredited UK testing labs.

Query: "{query}"
{standards_text}
Matching labs:
{results_text}

Return JSON: {{"standards_advice": string|null, "key_standards": [string]|null, "groups": [{{"heading": string, "explanation": string, "lab_ids": [int]}}]}}

standards_advice: if the query is about a product/problem (not a specific test), briefly note which standards apply (2 sentences max). Null if query already names a standard. Write as direct advice to the user — do NOT reference your internal data, "listed standards", "the other standards", or "matching labs". The user cannot see the raw data you were given.
key_standards: array of the 1-3 most relevant standard reference codes you identified (e.g. ["ISO 7173", "BS EN 1021-1"]). Null if none identified. Use the short reference form without year.
groups: categorise labs into groups. IMPORTANT: Before including any lab, check its tags and title for domain-specific terms. DROP any lab serving a clearly wrong industry — e.g. "medical-implants" is wrong for furniture, "aircraft-interior" is wrong for food, "veterinary" is wrong for construction. Material overlap alone (e.g. both test "plastics") is NOT enough — the application must be relevant. Explain match quality per group. Be concise."""

    try:
        response = await client.chat.completions.create(
            model=RECOMMENDATION_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_completion_tokens=600,
        )
        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
        rec = json.loads(text)

        # Phase 2: if key standards identified, find labs that explicitly list them
        key_stds = rec.get("key_standards")
        if key_stds:
            confirmed_ids = await _find_labs_with_standards(key_stds)
            if confirmed_ids:
                # Add or merge a "Confirmed — accredited for this standard" group
                existing_grouped = set()
                for g in rec.get("groups", []):
                    existing_grouped.update(g.get("lab_ids", []))

                # Only include confirmed labs that are in our result set
                result_lab_ids = {r.get("lab_id") for r in results}
                confirmed_in_results = [lid for lid in confirmed_ids if lid in result_lab_ids]

                # Also check for confirmed labs NOT in search results
                confirmed_not_in_results = [lid for lid in confirmed_ids if lid not in result_lab_ids]

                if confirmed_in_results or confirmed_not_in_results:
                    std_names = ", ".join(key_stds)
                    confirmed_group = {
                        "heading": f"Accredited for {std_names}",
                        "explanation": f"These labs are specifically UKAS-accredited to test against {std_names}.",
                        "lab_ids": confirmed_in_results,
                    }
                    if confirmed_not_in_results:
                        confirmed_group["extra_lab_ids"] = confirmed_not_in_results
                    # Insert as first group
                    rec["groups"].insert(0, confirmed_group)
                    # Remove these labs from other groups to avoid duplication
                    confirmed_set = set(confirmed_in_results)
                    for g in rec["groups"][1:]:
                        g["lab_ids"] = [lid for lid in g.get("lab_ids", []) if lid not in confirmed_set]
                    # Remove empty groups
                    rec["groups"] = [g for g in rec["groups"] if g.get("lab_ids") or g.get("extra_lab_ids")]

        return rec
    except Exception as e:
        print(f"Recommendation error: {e}")
        return None


async def _find_labs_with_standards(standard_refs: list[str]) -> list[int]:
    """Find lab_ids that have capabilities explicitly listing these standards."""
    db = get_supabase_client()
    lab_ids = set()
    for ref in standard_refs:
        # Strip "ISO " or "BS EN " prefix variations for flexible matching
        # Search for the numeric part which is most distinctive
        search_term = ref.strip()
        result = db.rpc("find_labs_by_standard", {"standard_ref": search_term}).execute()
        if result.data:
            for row in result.data:
                lab_ids.add(row["lab_id"])
    return list(lab_ids)


def _format_results(results: list[dict], mode: str) -> str:
    lines = []
    for r in results:
        if mode == "labs":
            brief = r.get("brief", "")
            tags = ", ".join(r.get("tags", [])[:6]) if r.get("tags") else ""
            lines.append(f"- lab_id={r.get('lab_id')} {r.get('title', r.get('lab_name', ''))}: {brief} [{tags}]")
        else:
            lines.append(
                f"- lab_id={r.get('lab_id')} {r.get('lab_name', '')} | "
                f"{r.get('materials_products', '')[:60]} | {r.get('test_type', '')[:60]}"
            )
    return "\n".join(lines)


def _format_standards(standards: list[dict]) -> str:
    lines = ["\nRelevant standards:"]
    for s in standards[:3]:
        scope = (s.get("scope") or "")[:100]
        lines.append(f"- {s['reference']}: {s['title']}" + (f" — {scope}" if scope else ""))
    return "\n".join(lines)
