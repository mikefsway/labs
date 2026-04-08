from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.hybrid_search import (
    find_multi_capability_labs,
    search_capabilities,
    search_lab_fraglets,
)
from app.services.recommendation import generate_recommendation

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search")
async def search(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    region: str | None = Query(None, description="Region filter (e.g. 'London')"),
):
    results = await search_capabilities(q, limit=limit, region=region)
    return {"query": q, "count": len(results), "results": results}


@router.get("/search/labs")
async def search_labs(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    region: str | None = Query(None, description="Region filter (e.g. 'London')"),
    recommend: bool = Query(False, description="Include LLM recommendation"),
):
    results = await search_lab_fraglets(q, limit=limit, region=region)
    resp = {"query": q, "count": len(results), "results": results}
    if recommend and results:
        resp["recommendation"] = await generate_recommendation(q, results, mode="labs")
    return resp


class MultiMatchRequest(BaseModel):
    queries: list[str]
    limit: int = 10
    region: str | None = None


@router.post("/match")
async def multi_match(req: MultiMatchRequest):
    results = await find_multi_capability_labs(req.queries, req.limit, req.region)
    return {"queries": req.queries, "count": len(results), "results": results}
