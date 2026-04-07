from fastapi import APIRouter, HTTPException

from app.database import get_supabase_client

router = APIRouter(prefix="/api", tags=["labs"])


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
    return {"lab": lab.data, "capabilities": caps.data}
