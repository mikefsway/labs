"""Scrape ASTM standards that lack year suffixes by guessing recent years descending."""

import json, re, time, sys
import httpx

INPUT = "data/astm_to_scrape.json"
OUTPUT = "data/astm_standards.json"
YEARS = ["25", "24", "23", "22", "21", "20", "19", "18", "17", "16", "15"]

with open(INPUT) as f:
    entries = json.load(f)

# Load existing results
try:
    with open(OUTPUT) as f:
        results = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    results = []

done_refs = {r["reference"] for r in results}

# Find entries that have no year (slug doesn't contain a dash after the number)
no_year = [e for e in entries if "-" not in e["slug"] and e["ref"] not in done_refs]
# Deduplicate slugs
seen = {}
unique = []
for e in no_year:
    if e["slug"] not in seen:
        seen[e["slug"]] = e["ref"]
        unique.append(e)

print(f"Standards without years to guess: {len(unique)}")
print(f"Already have: {len(done_refs)}")

client = httpx.Client(
    timeout=10.0,
    headers={"User-Agent": "LabScope/1.0 (research; lab-capability-index)"},
    follow_redirects=True,
)

errors = []
for i, entry in enumerate(unique):
    found = False
    for year in YEARS:
        slug_with_year = f"{entry['slug']}-{year}"
        url = f"https://store.astm.org/{slug_with_year}.html"
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
                    found = True
                    break
        except Exception:
            pass
        time.sleep(1)  # Shorter delay for 404s

    if not found:
        errors.append(entry["ref"])

    time.sleep(1)  # Extra delay between standards

    if (i + 1) % 10 == 0:
        with open(OUTPUT, "w") as f:
            json.dump(results, f, indent=2)
        print(f"{i+1}/{len(unique)} — {len(results)} total titles, {len(errors)} unfound")
        sys.stdout.flush()

with open(OUTPUT, "w") as f:
    json.dump(results, f, indent=2)
print(f"\nDone. Total titles: {len(results)}, Unfound: {len(errors)}")
if errors:
    print(f"Unfound: {errors[:20]}")
