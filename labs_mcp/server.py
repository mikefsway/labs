"""MCP server for UKAS lab capability search."""

import sys
from pathlib import Path

# Ensure app is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server.fastmcp import FastMCP

from app.services.hybrid_search import find_multi_capability_labs, search_capabilities

mcp = FastMCP(
    "ukas-lab-search",
    instructions=(
        "Search UKAS-accredited laboratory testing capabilities. "
        "Covers 1,524 labs and 14,298 capabilities across all testing domains "
        "including mechanical, chemical, environmental, calibration, EMC, "
        "food safety, asbestos, and more. "
        "Use search_capabilities for natural language queries, get_lab for "
        "full lab details, and find_multi_capability_labs when a project "
        "requires multiple types of testing from a single lab."
    ),
)


@mcp.tool()
async def search_lab_capabilities(
    query: str, limit: int = 10, region: str | None = None
) -> str:
    """Search for lab testing capabilities using natural language.

    Examples: "tensile testing of steel", "asbestos air sampling",
    "microbiological testing of water", "EMC testing electronics",
    "pressure gauge calibration"

    Args:
        query: Natural language description of the testing capability needed
        limit: Maximum number of results (1-50, default 10)
        region: Optional geographic filter (e.g. "London", "Manchester", "Wales")
    """
    results = await search_capabilities(query, limit=min(limit, 50), region=region)
    if not results:
        return "No matching capabilities found."

    lines = [f"Found {len(results)} matching capabilities:\n"]
    for i, r in enumerate(results, 1):
        materials = (r.get("materials_products") or "").replace("\n", " ").strip()[:100]
        test_type = (r.get("test_type") or "").replace("\n", " ").strip()[:100]
        lines.append(
            f"{i}. **{r['lab_name']}** (UKAS #{r['accreditation_number']})\n"
            f"   Materials: {materials}\n"
            f"   Test: {test_type}\n"
            f"   Address: {r.get('address', 'N/A')}\n"
            f"   Lab ID: {r['lab_id']}\n"
        )
    return "\n".join(lines)


@mcp.tool()
async def get_lab(lab_id: int) -> str:
    """Get full details for a specific UKAS-accredited lab.

    Returns lab contact info, accreditation number, and all capabilities.

    Args:
        lab_id: The lab's database ID (from search results)
    """
    from app.database import get_supabase_client

    client = get_supabase_client()
    lab = client.table("labs").select("*").eq("id", lab_id).single().execute()
    if not lab.data:
        return f"Lab with ID {lab_id} not found."

    caps = (
        client.table("capabilities")
        .select("materials_products, test_type, standards")
        .eq("lab_id", lab_id)
        .order("page")
        .execute()
    )

    l = lab.data
    lines = [
        f"# {l['lab_name']}",
        f"**UKAS Accreditation:** #{l['accreditation_number']}",
        f"**Standard:** {l.get('standard', 'N/A')}",
        f"**Address:** {l.get('address', 'N/A')}",
        f"**Contact:** {l.get('contact', 'N/A')}",
        f"**Phone:** {l.get('phone', 'N/A')}",
        f"**Email:** {l.get('email', 'N/A')}",
        f"**Website:** {l.get('website', 'N/A')}",
        f"\n## Capabilities ({len(caps.data)})\n",
    ]

    for i, c in enumerate(caps.data, 1):
        materials = (c.get("materials_products") or "").replace("\n", " ").strip()[:120]
        test_type = (c.get("test_type") or "").replace("\n", " ").strip()[:120]
        standards = (c.get("standards") or "").replace("\n", " ").strip()[:120]
        lines.append(
            f"{i}. **Materials:** {materials}\n"
            f"   **Test:** {test_type}\n"
            f"   **Standards:** {standards}\n"
        )

    return "\n".join(lines)


@mcp.tool()
async def find_labs_for_multiple_tests(
    queries: list[str], limit: int = 5, region: str | None = None
) -> str:
    """Find labs that can handle multiple testing needs from a single facility.

    Pass a list of capability descriptions. Returns labs ranked by how many
    of the requested capabilities they cover.

    Args:
        queries: List of capability descriptions (e.g. ["tensile testing steel", "chemical composition"])
        limit: Maximum labs to return (default 5)
        region: Optional geographic filter
    """
    results = await find_multi_capability_labs(queries, limit=min(limit, 20), region=region)
    if not results:
        return "No labs found matching all requested capabilities."

    lines = [f"Found {len(results)} labs covering your {len(queries)} requirements:\n"]
    for i, lab in enumerate(results, 1):
        lines.append(
            f"{i}. **{lab['lab_name']}** (UKAS #{lab['accreditation_number']})\n"
            f"   Matched {lab['queries_matched']}/{len(queries)} requirements\n"
            f"   Address: {lab.get('address', 'N/A')}\n"
            f"   Lab ID: {lab['lab_id']}\n"
        )
        for m in lab["matches"]:
            materials = (m.get("materials_products") or "").replace("\n", " ").strip()[:80]
            lines.append(f"   - [{m['query']}] {materials}\n")
        lines.append("")

    return "\n".join(lines)
