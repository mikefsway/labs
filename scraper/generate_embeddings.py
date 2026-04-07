"""
Generate embeddings for capabilities.search_text using OpenAI text-embedding-3-small (512 dims).
Reads from Supabase in batches, calls the embedding API, and updates the embedding column.
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

BATCH_SIZE = 100  # rows to fetch at a time
EMBED_BATCH_SIZE = 100  # texts per OpenAI API call (max 2048)
MODEL = "text-embedding-3-small"
DIMENSIONS = 512


def main():
    openai = OpenAI(api_key=OPENAI_API_KEY)
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    total_updated = 0

    while True:
        # Fetch a batch of rows without embeddings
        rows = (
            supabase.table("capabilities")
            .select("id, search_text")
            .is_("embedding", "null")
            .order("id")
            .limit(BATCH_SIZE)
            .execute()
        ).data

        if not rows:
            break

        # Filter out rows with empty search_text
        valid_rows = [r for r in rows if r["search_text"] and r["search_text"].strip()]
        if not valid_rows:
            # Mark empty ones so we don't loop forever
            for r in rows:
                supabase.table("capabilities").update(
                    {"embedding": [0.0] * DIMENSIONS}
                ).eq("id", r["id"]).execute()
            continue

        texts = [r["search_text"] for r in valid_rows]
        ids = [r["id"] for r in valid_rows]

        # Call OpenAI embeddings API
        try:
            response = openai.embeddings.create(
                model=MODEL, input=texts, dimensions=DIMENSIONS
            )
        except Exception as e:
            print(f"OpenAI API error: {e}", file=sys.stderr)
            time.sleep(5)
            continue

        # Update each row with its embedding
        for i, emb_data in enumerate(response.data):
            vector = emb_data.embedding
            supabase.table("capabilities").update(
                {"embedding": vector}
            ).eq("id", ids[i]).execute()

        total_updated += len(valid_rows)
        print(f"Updated {total_updated} rows (last batch: ids {ids[0]}-{ids[-1]})")

        # Respect rate limits
        time.sleep(0.5)

    print(f"Done. Total embeddings generated: {total_updated}")


if __name__ == "__main__":
    main()
