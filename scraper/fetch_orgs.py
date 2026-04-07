"""
Step 1: Fetch all testing and calibration lab organisations from the UKAS REST API.

Outputs: data/organisations.json
"""

import json
import time
from pathlib import Path

import requests

API_BASE = "https://www.ukas.com/wp-json/wp/v2"

# Organisation type IDs from the UKAS taxonomy
ORG_TYPES = {
    274: "Testing Laboratories",
    273: "Calibration Laboratories",
}


def fetch_organisations(org_type_id: int, per_page: int = 100) -> list[dict]:
    """Fetch all organisations of a given type via paginated REST API calls."""
    orgs = []
    page = 1

    while True:
        print(f"  Fetching page {page} for type {org_type_id}...")
        resp = requests.get(
            f"{API_BASE}/organisation",
            params={
                "organisation_type": org_type_id,
                "per_page": per_page,
                "page": page,
            },
            timeout=30,
        )

        if resp.status_code == 400:
            # Past last page
            break

        resp.raise_for_status()
        data = resp.json()

        if not data:
            break

        for org in data:
            orgs.append({
                "id": org["id"],
                "slug": org["slug"],
                "name": org["title"]["rendered"],
                "org_type_id": org_type_id,
                "country": org.get("country", []),
                "region": org.get("region", []),
                "organisation_subtype": org.get("organisation_subtype", []),
                "schedule_categories": org.get("schedule_categories", []),
                "link": org.get("link", ""),
            })

        total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
        if page >= total_pages:
            break

        page += 1
        time.sleep(0.5)  # Be polite

    return orgs


def main():
    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(exist_ok=True)

    all_orgs = []
    for type_id, type_name in ORG_TYPES.items():
        print(f"Fetching {type_name} (type={type_id})...")
        orgs = fetch_organisations(type_id)
        print(f"  Found {len(orgs)} organisations")
        all_orgs.extend(orgs)

    output_path = data_dir / "organisations.json"
    with open(output_path, "w") as f:
        json.dump(all_orgs, f, indent=2)

    print(f"\nTotal: {len(all_orgs)} organisations saved to {output_path}")


if __name__ == "__main__":
    main()
