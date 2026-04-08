"""
LLM recommendation layer — takes search results and generates
a structured, query-specific recommendation using GPT-4.1-mini.
"""

from openai import AsyncOpenAI

from app.config import get_settings

RECOMMENDATION_MODEL = "gpt-5.4-mini"


async def generate_recommendation(
    query: str, results: list[dict], mode: str = "labs"
) -> str:
    if not results:
        return ""

    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    # Build context from results
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

Based on these results, provide a concise recommendation. Adapt your response to the situation:

- If this is widely available testing (many strong matches with similar capabilities), say so briefly. Note it's a common/standardised test, suggest choosing based on location and turnaround. List lab names grouped by region if helpful.
- If this is specialist testing (few matches, varying relevance), group labs into "Confirmed match" (capabilities clearly cover the query) and "Likely match" (related capabilities, user should confirm). Briefly explain why each group matches or partially matches.
- If matches are weak or tangential, advise what testing standards they might actually need and suggest contacting the closest matches to discuss.

Rules:
- Be concise — aim for 3-8 sentences plus lab names.
- Do NOT describe the labs in detail — describe how well they match the query.
- Do NOT reveal that you are an AI or mention scores/algorithms.
- Use plain language a non-specialist can understand, but include relevant standard references where they add value.
- Format using markdown: use **bold** for group headings, bullet points for lab lists."""

    try:
        response = await client.chat.completions.create(
            model=RECOMMENDATION_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_completion_tokens=600,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Recommendation error: {e}")
        return ""


def _format_lab_results(results: list[dict]) -> str:
    lines = []
    for i, r in enumerate(results, 1):
        tags = ", ".join(r.get("tags", [])[:8]) if r.get("tags") else ""
        lines.append(
            f"{i}. {r.get('title', r.get('lab_name', ''))}\n"
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
            f"{i}. {r.get('lab_name', '')} (UKAS #{r.get('accreditation_number', '')})\n"
            f"   Address: {r.get('address', '')}\n"
            f"   Materials: {r.get('materials_products', '')}\n"
            f"   Test type: {r.get('test_type', '')}\n"
            f"   Standards: {r.get('standards', '')}\n"
            f"   Score: {r.get('rrf_score', 0):.4f}"
        )
    return "\n\n".join(lines)
