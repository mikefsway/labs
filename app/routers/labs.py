import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.database import get_supabase_client

router = APIRouter(prefix="/api", tags=["labs"])

# Load PDF URL mapping once at startup
_pdf_map: dict[str, list[str]] = {}
_pdf_file = Path(__file__).resolve().parent.parent.parent / "data" / "schedule_pdfs.json"
if _pdf_file.exists():
    import re as _re
    with open(_pdf_file) as _f:
        for _p in json.load(_f):
            _m = _re.search(r"/(\d+)(Testing|Calibration)", _p["url"])
            if _m:
                _pdf_map.setdefault(_m.group(1), []).append(_p["url"])


@router.get("/labs/{lab_id}")
async def get_lab(lab_id: int):
    client = get_supabase_client()
    lab = client.table("labs").select("*").eq("id", lab_id).single().execute()
    if not lab.data:
        raise HTTPException(404, "Lab not found")
    caps = (
        client.table("capabilities")
        .select("id, materials_products, test_type, standards, page")
        .eq("lab_id", lab_id)
        .order("page")
        .execute()
    )
    fraglet = (
        client.table("lab_fraglets")
        .select("title, brief, additional, category, tags")
        .eq("lab_id", lab_id)
        .maybe_single()
        .execute()
    )
    sites = (
        client.table("lab_sites")
        .select("site_name, address, postcode, capabilities_summary, is_testing_site, site_code")
        .eq("lab_id", lab_id)
        .order("is_testing_site", desc=True)
        .execute()
    )

    # Look up UKAS schedule PDF URLs
    accred = lab.data.get("accreditation_number", "")
    schedule_pdfs = _pdf_map.get(accred, [])

    return {
        "lab": lab.data,
        "capabilities": caps.data,
        "fraglet": fraglet.data if fraglet else None,
        "sites": sites.data if sites else [],
        "schedule_pdfs": schedule_pdfs,
    }
