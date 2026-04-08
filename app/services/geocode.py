"""Geocode UK postcodes and place names via postcodes.io (free, no key)."""

import httpx

_client = httpx.AsyncClient(timeout=5.0)


async def geocode(query: str) -> dict | None:
    """Return {"lat": float, "lng": float} or None."""
    query = query.strip().upper()
    # Try as postcode first
    r = await _client.get(f"https://api.postcodes.io/postcodes/{query}")
    if r.status_code == 200:
        data = r.json().get("result")
        if data:
            return {"lat": data["latitude"], "lng": data["longitude"]}
    # Try as place name
    r = await _client.get(f"https://api.postcodes.io/places", params={"q": query, "limit": 1})
    if r.status_code == 200:
        results = r.json().get("result")
        if results:
            return {"lat": results[0]["latitude"], "lng": results[0]["longitude"]}
    return None
