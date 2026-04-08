"""
Generate embeddings for standards using OpenAI text-embedding-3-small (512 dims).
Embeds: reference + title + scope (where scope exists).
Resumable: only processes rows where embedding IS NULL and scope IS NOT NULL.
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

BATCH_SIZE = 200
MODEL = "text-embedding-3-small"
DIMENSIONS = 512


def build_embed_text(row: dict) -> str:
    parts = [row.get("reference") or "", row.get("title") or ""]
    if row.get("scope"):
        parts.append(row["scope"])
    return " — ".join(p for p in parts if p)


def main():
    openai = OpenAI(api_key=OPENAI_API_KEY)
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    total_updated = 0

    while True:
        rows = (
            supabase.table("standards")
            .select("id, reference, title, scope")
            .is_("embedding", "null")
            .not_.is_("scope", "null")
            .order("id")
            .limit(BATCH_SIZE)
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
            supabase.table("standards").update(
                {"embedding": emb_data.embedding}
            ).eq("id", ids[i]).execute()

        total_updated += len(rows)
        if total_updated % 1000 == 0:
            print(f"Embedded {total_updated} standards")

        time.sleep(0.3)

    print(f"Done. Total: {total_updated}")


if __name__ == "__main__":
    main()
