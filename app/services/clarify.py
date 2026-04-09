"""
Clarification layer — uses GPT-5.4-mini to decide whether a user query
is specific enough for a good lab search, or whether 1-3 quick clarifying
questions would meaningfully improve the results.
"""

import json

from openai import AsyncOpenAI

from app.config import get_settings

CLARIFY_MODEL = "gpt-5.4-mini"


async def maybe_clarify(query: str) -> dict | None:
    """Return clarifying questions if the query is too vague, else None.

    Returns:
        None if query is already specific enough.
        {"questions": [{"text": str, "options": [str]}]} if clarification needed.
    """
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    prompt = f"""You help users find UKAS-accredited UK testing laboratories.

A user has submitted this query:
"{query}"

Decide whether the query is specific enough to produce good lab recommendations, or whether 1-3 short clarifying questions would meaningfully improve the results.

A query is SPECIFIC ENOUGH if it already mentions:
- A specific product/material AND a clear testing need, OR
- A named standard or test method (e.g. "ISO 7173", "EMC testing"), OR
- A well-defined industry scenario (e.g. "asbestos surveying for building refurbishment")

A query NEEDS CLARIFICATION if it is vague about:
- What the product/material actually is
- What market, regulation, or certification it targets
- Whether they need compliance testing vs R&D/exploratory testing
- The industry or application (when the material could span multiple sectors)

If clarification is needed, return JSON:
{{"needs_clarification": true, "questions": [{{"text": "question text", "options": ["option1", "option2", "option3"]}}]}}

Rules for questions:
- Maximum 3 questions, prefer fewer
- Each question MUST have 2-4 short tap-friendly options (under 6 words each)
- Questions should be conversational, not interrogative
- Focus on what would most change the search results
- Never ask about location (handled separately)

If the query is already specific enough, return:
{{"needs_clarification": false}}"""

    try:
        response = await client.chat.completions.create(
            model=CLARIFY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_completion_tokens=300,
        )
        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
        result = json.loads(text)

        if result.get("needs_clarification") and result.get("questions"):
            return {"questions": result["questions"]}
        return None
    except Exception as e:
        print(f"Clarification error: {e}")
        return None
