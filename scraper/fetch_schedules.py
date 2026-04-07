"""
Step 2: Find schedule PDF URLs for each organisation via the WP media API.

Reads: data/organisations.json
Outputs: data/schedule_pdfs.json
"""

import json
import time
from pathlib import Path

import requests

API_BASE = "https://www.ukas.com/wp-json/wp/v2"

# PDF title patterns: "{accred_num}Testing-Single.pdf", "{accred_num}Calibration-Multiple.pdf"
SCHEDULE_TYPES = ["Testing", "Calibration"]


def fetch_all_schedule_pdfs(per_page: int = 100) -> list[dict]:
    """Fetch all schedule PDF media items from the WP REST API."""
    pdfs = []
    page = 1

    while True:
        print(f"  Fetching media page {page}...")
        resp = requests.get(
            f"{API_BASE}/media",
            params={
                "mime_type": "application/pdf",
                "search": "schedule",
                "per_page": per_page,
                "page": page,
            },
            timeout=30,
        )

        if resp.status_code == 400:
            break

        resp.raise_for_status()
        data = resp.json()

        if not data:
            break

        for item in data:
            title = item.get("title", {}).get("rendered", "")
            url = item.get("source_url", "")

            # Only include Testing and Calibration schedules
            if not any(t in title for t in SCHEDULE_TYPES):
                continue

            pdfs.append({
                "media_id": item["id"],
                "title": title,
                "url": url,
                "parent_post_id": item.get("post", None),
                "date": item.get("date", ""),
            })

        total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
        if page >= total_pages:
            break

        page += 1
        time.sleep(0.5)

    return pdfs


def main():
    data_dir = Path(__file__).parent.parent / "data"

    print("Fetching all schedule PDFs from media API...")
    pdfs = fetch_all_schedule_pdfs()
    print(f"Found {len(pdfs)} testing/calibration schedule PDFs")

    output_path = data_dir / "schedule_pdfs.json"
    with open(output_path, "w") as f:
        json.dump(pdfs, f, indent=2)

    print(f"Saved to {output_path}")

    # Print summary
    testing = [p for p in pdfs if "Testing" in p["title"]]
    calibration = [p for p in pdfs if "Calibration" in p["title"]]
    print(f"  Testing: {len(testing)}, Calibration: {len(calibration)}")


if __name__ == "__main__":
    main()
