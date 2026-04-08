"""
Generate embeddings for lab_fraglets using OpenAI text-embedding-3-small (512 dims).
Concatenates title + brief + detail + tags for embedding text.
Resumable: only processes rows where embedding IS NULL.
"""

import os
import sys
import time
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

BATCH_SIZE = 50
EMBED_BATCH_SIZE = 50
MODEL = "text-embedding-3-small"
DIMENSIONS = 512


def build_embed_text(row: dict) -> str:
    """Concatenate the searchable fields into a single embedding input."""
    parts = [
        row.get("title") or "",
        row.get("brief") or "",
        row.get("detail") or "",
    ]
    tags = row.get("tags")
    if tags:
        parts.append(", ".join(tags))
    return "\n".join(p for p in parts if p)


def main():
    limit = None
    if len(sys.argv) > 1 and sys.argv[1] == "--limit":
        limit = int(sys.argv[2])

    openai = OpenAI(api_key=OPENAI_API_KEY)
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    total_updated = 0

    while True:
        if limit and total_updated >= limit:
            break

        fetch_count = min(BATCH_SIZE, limit - total_updated) if limit else BATCH_SIZE

        rows = (
            supabase.table("lab_fraglets")
            .select("id, title, brief, detail, tags")
            .is_("embedding", "null")
            .order("lab_id")
            .limit(fetch_count)
            .execute()
        ).data

        if not rows:
            break

        texts = [build_embed_text(r) for r in rows]
        ids = [r["id"] for r in rows]

        try:
            response = openai.embeddings.create(
                model=MODEL, input=texts, dimensions=DIMENSIONS
            )
        except Exception as e:
            print(f"OpenAI API error: {e}", file=sys.stderr)
            time.sleep(5)
            continue

        for i, emb_data in enumerate(response.data):
            supabase.table("lab_fraglets").update(
                {"embedding": emb_data.embedding}
            ).eq("id", ids[i]).execute()

        total_updated += len(rows)
        print(f"Embedded {total_updated} fraglets (batch: {len(rows)})")

        time.sleep(0.5)

    print(f"Done. Total: {total_updated}")


if __name__ == "__main__":
    main()
