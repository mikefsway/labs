import asyncio
import math

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.geocode import geocode
from app.services.hybrid_search import (
    find_multi_capability_labs,
    search_capabilities,
    search_lab_fraglets,
    search_standards,
)
from app.services.recommendation import generate_recommendation

router = APIRouter(prefix="/api", tags=["search"])


def _haversine_km(lat1, lng1, lat2, lng2):
    """Haversine distance in km."""
    r = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return r * 2 * math.asin(math.sqrt(a))


def _add_distances(results, user_lat, user_lng):
    """Add distance_km to each result that has lat/lng."""
    for r in results:
        lat = r.get("lat")
        lng = r.get("lng")
        if lat and lng:
            r["distance_km"] = round(_haversine_km(user_lat, user_lng, lat, lng), 1)
        else:
            r["distance_km"] = None
    return results


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
    location: str | None = Query(None, description="Postcode or town for proximity"),
    recommend: bool = Query(False, description="Include LLM recommendation"),
):
    tasks = [search_lab_fraglets(q, limit=limit, region=region)]
    if recommend:
        tasks.append(search_standards(q, limit=3))
    if location:
        tasks.append(geocode(location))

    gathered = await asyncio.gather(*tasks)

    results = gathered[0]
    standards = gathered[1] if recommend else None
    user_loc = gathered[-1] if location else None

    if user_loc and results:
        results = _add_distances(results, user_loc["lat"], user_loc["lng"])

    resp = {"query": q, "count": len(results), "results": results}
    if user_loc:
        resp["location"] = user_loc
    if recommend and results:
        resp["recommendation"] = await generate_recommendation(
            q, results, standards=standards, mode="labs"
        )
    return resp


class MultiMatchRequest(BaseModel):
    queries: list[str]
    limit: int = 10
    region: str | None = None


@router.post("/match")
async def multi_match(req: MultiMatchRequest):
    results = await find_multi_capability_labs(req.queries, req.limit, req.region)
    return {"queries": req.queries, "count": len(results), "results": results}
