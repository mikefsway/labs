from app.database import get_supabase_anon_client
from app.services.embedding import generate_embedding


async def search_capabilities(
    query: str, limit: int = 20, region: str | None = None
) -> list[dict]:
    embedding = await generate_embedding(query)
    client = get_supabase_anon_client()
    result = client.rpc(
        "hybrid_search_capabilities",
        {
            "query_text": query,
            "query_embedding": embedding,
            "match_count": limit,
            "filter_region": region,
        },
    ).execute()
    return result.data


async def search_lab_fraglets(
    query: str, limit: int = 10, region: str | None = None
) -> list[dict]:
    embedding = await generate_embedding(query)
    client = get_supabase_anon_client()
    result = client.rpc(
        "hybrid_search_lab_fraglets",
        {
            "query_text": query,
            "query_embedding": embedding,
            "match_count": limit,
            "filter_region": region,
        },
    ).execute()
    return result.data


async def search_standards(
    query: str, limit: int = 5
) -> list[dict]:
    embedding = await generate_embedding(query)
    client = get_supabase_anon_client(schema="standards")
    result = client.rpc(
        "search_standards",
        {
            "query_text": query,
            "query_embedding": embedding,
            "match_count": limit,
        },
    ).execute()
    return result.data


async def find_multi_capability_labs(
    queries: list[str], limit: int = 10, region: str | None = None
) -> list[dict]:
    """Find labs that cover multiple capability needs."""
    lab_scores: dict[int, dict] = {}

    for query in queries:
        results = await search_capabilities(query, limit=30, region=region)
        seen_labs: set[int] = set()
        for r in results:
            lid = r["lab_id"]
            if lid in seen_labs:
                continue
            seen_labs.add(lid)
            if lid not in lab_scores:
                lab_scores[lid] = {
                    "lab_id": lid,
                    "lab_name": r["lab_name"],
                    "accreditation_number": r["accreditation_number"],
                    "address": r["address"],
                    "queries_matched": 0,
                    "total_rrf": 0.0,
                    "matches": [],
                }
            lab_scores[lid]["queries_matched"] += 1
            lab_scores[lid]["total_rrf"] += r["rrf_score"]
            lab_scores[lid]["matches"].append(
                {
                    "query": query,
                    "materials_products": r["materials_products"],
                    "test_type": r["test_type"],
                    "rrf_score": r["rrf_score"],
                }
            )

    ranked = sorted(
        lab_scores.values(),
        key=lambda x: (x["queries_matched"], x["total_rrf"]),
        reverse=True,
    )
    return ranked[:limit]
