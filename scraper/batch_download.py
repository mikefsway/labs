"""
Step 4: Batch download schedule PDFs and parse them into capabilities.

Reads: data/schedule_pdfs.json (from fetch_schedules.py)
Outputs:
  - data/pdfs/*.pdf (downloaded schedule PDFs)
  - data/capabilities.json (aggregated parsed capabilities)
  - data/batch_log.json (download/parse status per PDF)
"""

import json
import time
import sys
from pathlib import Path

import requests

from parse_schedule import parse_schedule


def download_pdf(url: str, dest: Path, retries: int = 2) -> bool:
    """Download a PDF with retries. Returns True on success."""
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            return True
        except Exception as e:
            if attempt < retries:
                time.sleep(2)
            else:
                print(f"  FAIL: {e}")
                return False
    return False


def main():
    data_dir = Path(__file__).parent.parent / "data"
    pdf_dir = data_dir / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    schedule_path = data_dir / "schedule_pdfs.json"
    if not schedule_path.exists():
        print("ERROR: data/schedule_pdfs.json not found. Run fetch_schedules.py first.")
        sys.exit(1)

    with open(schedule_path) as f:
        pdfs = json.load(f)

    print(f"Found {len(pdfs)} schedule PDFs to process")

    # Load existing log to allow resuming
    log_path = data_dir / "batch_log.json"
    if log_path.exists():
        with open(log_path) as f:
            log = json.load(f)
    else:
        log = {}

    all_capabilities = []
    downloaded = 0
    parsed = 0
    skipped = 0
    failed = 0

    for i, pdf_info in enumerate(pdfs):
        url = pdf_info["url"]
        title = pdf_info["title"]
        media_id = str(pdf_info["media_id"])

        # Use media_id as filename to avoid collisions
        filename = f"{media_id}_{title}"
        # Sanitise filename
        filename = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
        if not filename.endswith(".pdf"):
            filename += ".pdf"
        dest = pdf_dir / filename

        # Skip if already successfully processed
        if media_id in log and log[media_id].get("status") == "ok":
            # Load cached capabilities
            if log[media_id].get("capabilities_count", 0) > 0:
                cached_path = dest.with_suffix(".json")
                if cached_path.exists():
                    with open(cached_path) as f:
                        result = json.load(f)
                    all_capabilities.append(result)
                    parsed += 1
            skipped += 1
            continue

        print(f"[{i+1}/{len(pdfs)}] {title}")

        # Download
        if not dest.exists():
            ok = download_pdf(url, dest)
            if not ok:
                log[media_id] = {"title": title, "url": url, "status": "download_failed"}
                failed += 1
                continue
            downloaded += 1
            time.sleep(1)  # Rate limit: ~1 req/sec
        else:
            print(f"  Already downloaded")

        # Parse
        try:
            result = parse_schedule(str(dest))
            caps_count = len(result["capabilities"])
            print(f"  Parsed: {caps_count} capabilities")

            # Save individual result
            json_path = dest.with_suffix(".json")
            with open(json_path, "w") as f:
                json.dump(result, f, indent=2)

            all_capabilities.append(result)
            parsed += 1
            log[media_id] = {
                "title": title,
                "url": url,
                "status": "ok",
                "capabilities_count": caps_count,
                "file": str(dest.name),
            }

        except Exception as e:
            print(f"  PARSE ERROR: {e}")
            log[media_id] = {"title": title, "url": url, "status": "parse_failed", "error": str(e)}
            failed += 1

        # Save log periodically (every 50)
        if (i + 1) % 50 == 0:
            with open(log_path, "w") as f:
                json.dump(log, f, indent=2)
            print(f"  --- Progress: {i+1}/{len(pdfs)}, parsed={parsed}, failed={failed} ---")

    # Save final log
    with open(log_path, "w") as f:
        json.dump(log, f, indent=2)

    # Aggregate all capabilities
    output = {
        "total_labs": len(all_capabilities),
        "total_capabilities": sum(len(r["capabilities"]) for r in all_capabilities),
        "labs": all_capabilities,
    }

    caps_path = data_dir / "capabilities.json"
    with open(caps_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nDone!")
    print(f"  Downloaded: {downloaded}")
    print(f"  Parsed: {parsed}")
    print(f"  Skipped (already done): {skipped}")
    print(f"  Failed: {failed}")
    print(f"  Total capabilities: {output['total_capabilities']}")
    print(f"  Saved to {caps_path}")


if __name__ == "__main__":
    main()
