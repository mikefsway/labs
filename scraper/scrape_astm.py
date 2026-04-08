"""Scrape ASTM standard titles from store.astm.org. Resumable — saves after each batch."""

import json, re, time, sys
import httpx

INPUT = "data/astm_to_scrape.json"
OUTPUT = "data/astm_standards.json"

with open(INPUT) as f:
    entries = json.load(f)

# Deduplicate slugs
seen_slugs = {}
unique = []
for e in entries:
    if e["slug"] not in seen_slugs:
        seen_slugs[e["slug"]] = e["ref"]
        unique.append(e)

# Load existing results to resume
try:
    with open(OUTPUT) as f:
        results = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    results = []

done_refs = {r["reference"] for r in results}
remaining = [e for e in unique if e["ref"] not in done_refs]
print(f"Total: {len(unique)}, Already done: {len(done_refs)}, Remaining: {len(remaining)}")

client = httpx.Client(
    timeout=10.0,
    headers={"User-Agent": "LabScope/1.0 (research; lab-capability-index)"},
    follow_redirects=True,
)

errors = []
for i, entry in enumerate(remaining):
    url = f"https://store.astm.org/{entry['slug']}.html"
    try:
        r = client.get(url)
        if r.status_code == 200:
            text = r.text
            title_match = re.search(r"<h1[^>]*>(.*?)</h1>", text, re.DOTALL)
            if not title_match:
                title_match = re.search(r"<title>(.*?)</title>", text)
            if title_match:
                title = re.sub(r"<[^>]+>", "", title_match.group(1)).strip()
                title = re.sub(r"^ASTM\s+\S+\s*-\s*\d+[a-z]?\d?\s*", "", title).strip()
                scope = ""
                scope_match = re.search(
                    r'<div[^>]*class="[^"]*abstract[^"]*"[^>]*>(.*?)</div>', text, re.DOTALL
                )
                if scope_match:
                    scope = re.sub(r"<[^>]+>", "", scope_match.group(1)).strip()
                results.append({
                    "reference": entry["ref"],
                    "title": title,
                    "scope": scope if scope else None,
                })
            else:
                errors.append((entry["ref"], "no title"))
        elif r.status_code == 404:
            errors.append((entry["ref"], "404"))
        else:
            errors.append((entry["ref"], f"HTTP {r.status_code}"))
    except Exception as e:
        errors.append((entry["ref"], str(e)))

    if (i + 1) % 10 == 0:
        # Save progress
        with open(OUTPUT, "w") as f:
            json.dump(results, f, indent=2)
        print(f"{i+1}/{len(remaining)} — {len(results)} titles, {len(errors)} errors")
        sys.stdout.flush()

    time.sleep(2)

# Final save
with open(OUTPUT, "w") as f:
    json.dump(results, f, indent=2)
print(f"\nDone. Titles: {len(results)}, Errors: {len(errors)}")
if errors:
    print(f"Sample errors: {errors[:10]}")
