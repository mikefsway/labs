"""
LLM recommendation layer — takes search results + relevant standards
and generates a structured, query-specific recommendation using GPT-5.4-mini.
"""

import json

from openai import AsyncOpenAI

from app.config import get_settings

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

Return JSON: {{"standards_advice": string|null, "groups": [{{"heading": string, "explanation": string, "lab_ids": [int]}}]}}

standards_advice: if the query is about a product/problem (not a specific test), briefly note which standards apply (2 sentences max). Null if query already names a standard.
groups: categorise labs as "Confirmed match", "Likely match", or "Widely available". Omit irrelevant labs. Explain match quality per group, not per lab. Be concise."""

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
        return json.loads(text)
    except Exception as e:
        print(f"Recommendation error: {e}")
        return None


def _format_results(results: list[dict], mode: str) -> str:
    lines = []
    for r in results:
        if mode == "labs":
            tags = ", ".join(r.get("tags", [])[:6]) if r.get("tags") else ""
            lines.append(f"- lab_id={r.get('lab_id')} {r.get('title', r.get('lab_name', ''))} [{tags}]")
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
