from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.hybrid_search import find_multi_capability_labs, search_capabilities

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search")
async def search(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    region: str | None = Query(None, description="Region filter (e.g. 'London')"),
):
    results = await search_capabilities(q, limit=limit, region=region)
    return {"query": q, "count": len(results), "results": results}


class MultiMatchRequest(BaseModel):
    queries: list[str]
    limit: int = 10
    region: str | None = None


@router.post("/match")
async def multi_match(req: MultiMatchRequest):
    results = await find_multi_capability_labs(req.queries, req.limit, req.region)
    return {"queries": req.queries, "count": len(results), "results": results}
