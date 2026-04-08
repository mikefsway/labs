"""
LLM recommendation layer — takes search results and generates
a structured, query-specific recommendation using GPT-5.4-mini.

Returns JSON groups that the frontend can interleave with result cards.
"""

import json

from openai import AsyncOpenAI

from app.config import get_settings

RECOMMENDATION_MODEL = "gpt-5.4-mini"


async def generate_recommendation(
    query: str, results: list[dict], mode: str = "labs"
) -> list[dict] | None:
    if not results:
        return None

    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    if mode == "labs":
        results_text = _format_lab_results(results)
    else:
        results_text = _format_capability_results(results)

    top_score = results[0].get("rrf_score", 0)
    bottom_score = results[-1].get("rrf_score", 0)

    prompt = f"""You are an expert advisor helping someone find UKAS-accredited testing laboratories in the UK.

The user searched for: "{query}"

Here are the top {len(results)} matching labs with their capabilities and relevance scores:

{results_text}

Score range: {top_score:.4f} (highest) to {bottom_score:.4f} (lowest)

Return a JSON array of groups. Each group has:
- "heading": a short bold heading (e.g. "Confirmed match", "Likely match", "Widely available")
- "explanation": 1-3 sentences explaining this group — why these labs match (or partially match) the query
- "lab_ids": array of lab_id integers that belong in this group

Adapt the grouping to the situation:
- If this is widely available testing (many strong matches), use a single group with heading like "Widely available" and explain it's a common test, suggest choosing by location/turnaround.
- If this is specialist testing, split into "Confirmed match" (capabilities clearly cover the query) and "Likely match" (related but user should confirm). Explain the difference.
- If matches are weak, use a group like "Possible match — contact to confirm" and advise what standards they might need.
- You may omit labs that are clearly irrelevant — not every lab needs to be in a group.

Rules:
- Return ONLY valid JSON — no markdown, no explanation outside the JSON.
- Use plain language a non-specialist can understand, but include relevant standard references where they add value.
- Do NOT describe individual labs — describe how the group relates to the query.
- Do NOT reveal that you are an AI or mention scores/algorithms.
- Keep explanations concise."""

    try:
        response = await client.chat.completions.create(
            model=RECOMMENDATION_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_completion_tokens=800,
        )
        text = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
        return json.loads(text)
    except Exception as e:
        print(f"Recommendation error: {e}")
        return None


def _format_lab_results(results: list[dict]) -> str:
    lines = []
    for i, r in enumerate(results, 1):
        tags = ", ".join(r.get("tags", [])[:8]) if r.get("tags") else ""
        lines.append(
            f"{i}. lab_id={r.get('lab_id')} — {r.get('title', r.get('lab_name', ''))}\n"
            f"   Address: {r.get('address', '')}\n"
            f"   Brief: {r.get('brief', '')}\n"
            f"   Tags: {tags}\n"
            f"   Score: {r.get('rrf_score', 0):.4f}"
        )
    return "\n\n".join(lines)


def _format_capability_results(results: list[dict]) -> str:
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(
            f"{i}. lab_id={r.get('lab_id')} — {r.get('lab_name', '')} (UKAS #{r.get('accreditation_number', '')})\n"
            f"   Address: {r.get('address', '')}\n"
            f"   Materials: {r.get('materials_products', '')}\n"
            f"   Test type: {r.get('test_type', '')}\n"
            f"   Standards: {r.get('standards', '')}\n"
            f"   Score: {r.get('rrf_score', 0):.4f}"
        )
    return "\n\n".join(lines)
