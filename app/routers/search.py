import asyncio
import math

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, field_validator

from app.database import get_supabase_anon_client
from app.ratelimit import limiter
from app.services.geocode import geocode
from app.services.hybrid_search import (
    find_multi_capability_labs,
    search_capabilities,
    search_lab_fraglets,
    search_standards,
)
from app.services.clarify import maybe_clarify
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
@limiter.limit("30/minute")
async def search(
    request: Request,
    q: str = Query(..., min_length=2, max_length=500, description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    region: str | None = Query(None, max_length=100, description="Region filter (e.g. 'London')"),
):
    results = await search_capabilities(q, limit=limit, region=region)
    return {"query": q, "count": len(results), "results": results}


@router.get("/search/clarify")
@limiter.limit("10/minute")
async def clarify(
    request: Request,
    q: str = Query(..., min_length=2, max_length=500, description="User query to check"),
):
    """Check if a query needs clarifying questions before searching."""
    result = await maybe_clarify(q)
    if result:
        return {"needs_clarification": True, **result}
    return {"needs_clarification": False}


@router.get("/search/labs")
@limiter.limit("10/minute")
async def search_labs(
    request: Request,
    q: str = Query(..., min_length=2, max_length=500, description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    region: str | None = Query(None, max_length=100, description="Region filter (e.g. 'London')"),
    location: str | None = Query(None, max_length=100, description="Postcode or town for proximity"),
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
        rec = await generate_recommendation(
            q, results, standards=standards, mode="labs"
        )
        if rec:
            # Fetch details for any extra labs found via standard cross-reference
            extra_ids = set()
            for g in rec.get("groups", []):
                for lid in g.get("extra_lab_ids", []):
                    extra_ids.add(lid)
            if extra_ids:
                db = get_supabase_anon_client()
                extra_labs = (
                    db.table("lab_fraglets")
                    .select("lab_id, title, brief, tags, category")
                    .in_("lab_id", list(extra_ids))
                    .execute()
                ).data
                if extra_labs:
                    # Fetch lab addresses
                    lab_details = (
                        db.table("labs")
                        .select("id, lab_name, accreditation_number, address, lat, lng")
                        .in_("id", list(extra_ids))
                        .execute()
                    ).data
                    lab_map = {l["id"]: l for l in (lab_details or [])}
                    extra_results = []
                    for lf in extra_labs:
                        lab = lab_map.get(lf["lab_id"], {})
                        entry = {**lf, **lab, "rrf_score": 0, "confirmed_by_standard": True}
                        if user_loc and entry.get("lat") and entry.get("lng"):
                            entry["distance_km"] = round(
                                _haversine_km(user_loc["lat"], user_loc["lng"], entry["lat"], entry["lng"]), 1
                            )
                        extra_results.append(entry)
                    resp["extra_results"] = extra_results
            resp["recommendation"] = rec
    return resp


class MultiMatchRequest(BaseModel):
    queries: list[str]
    limit: int = 10
    region: str | None = None

    @field_validator("queries")
    @classmethod
    def validate_queries(cls, v):
        if len(v) > 10:
            raise ValueError("Maximum 10 queries allowed")
        return [q[:500] for q in v]


@router.post("/match")
@limiter.limit("10/minute")
async def multi_match(request: Request, req: MultiMatchRequest):
    results = await find_multi_capability_labs(req.queries, req.limit, req.region)
    return {"queries": req.queries, "count": len(results), "results": results}
