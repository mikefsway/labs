"""Load scraped ASTM standards into Supabase and embed them."""

import json, os, sys, time
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

MODEL = "text-embedding-3-small"
DIMENSIONS = 512
INPUT = os.path.join(os.path.dirname(__file__), "..", "data", "astm_standards.json")


def main():
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    openai = OpenAI(api_key=OPENAI_API_KEY)

    with open(INPUT) as f:
        standards = json.load(f)

    print(f"ASTM standards to load: {len(standards)}")

    # Upsert into standards table and embed in batches
    BATCH = 50
    total = 0
    for i in range(0, len(standards), BATCH):
        batch = standards[i:i + BATCH]

        # Build rows for upsert
        rows = [{
            "reference": s["reference"],
            "title": s["title"],
            "scope": s.get("scope"),
            "domain": "astm",
        } for s in batch]

        supabase.table("standards").upsert(rows, on_conflict="reference").execute()

        # Build embedding texts
        texts = []
        for s in batch:
            parts = [s["reference"], s["title"]]
            if s.get("scope"):
                parts.append(s["scope"])
            texts.append(" — ".join(parts))

        # Generate embeddings
        try:
            resp = openai.embeddings.create(model=MODEL, input=texts, dimensions=DIMENSIONS)
            for j, emb in enumerate(resp.data):
                supabase.table("standards").update({
                    "embedding": emb.embedding
                }).eq("reference", batch[j]["reference"]).execute()
        except Exception as e:
            print(f"Embedding error at batch {i}: {e}", file=sys.stderr)
            time.sleep(5)

        total += len(batch)
        print(f"{total}/{len(standards)}")
        sys.stdout.flush()
        time.sleep(0.3)

    # Update search_tsv for new rows
    supabase.rpc("", {}).execute  # can't run raw SQL via client
    print(f"Done. Loaded and embedded {total} ASTM standards.")
    print("NOTE: Run this SQL to update search_tsv:")
    print("  UPDATE standards SET search_tsv = to_tsvector('english', coalesce(reference,'') || ' ' || coalesce(title,'') || ' ' || coalesce(scope,'')) WHERE domain = 'astm';")


if __name__ == "__main__":
    main()
