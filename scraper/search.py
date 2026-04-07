"""
Semantic search over lab capabilities.
Takes a natural language query, embeds it, and returns top matching labs+capabilities.
"""

import os
import sys
import json
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

MODEL = "text-embedding-3-small"
DIMENSIONS = 512


def search(query: str, limit: int = 10):
    openai = OpenAI(api_key=OPENAI_API_KEY)
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    # Embed the query
    response = openai.embeddings.create(model=MODEL, input=[query], dimensions=DIMENSIONS)
    query_vector = response.data[0].embedding

    # Cosine similarity search via pgvector
    results = supabase.rpc(
        "match_capabilities",
        {"query_embedding": query_vector, "match_count": limit},
    ).execute()

    return results.data


def main():
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "tensile testing of steel"
    print(f"Searching: {query}\n")
    results = search(query)
    for i, r in enumerate(results, 1):
        print(f"--- Result {i} (similarity: {r.get('similarity', 'N/A'):.4f}) ---")
        print(f"Lab: {r.get('lab_name', 'N/A')} (ID: {r.get('lab_id')})")
        print(f"Materials: {r.get('materials_products', '')[:120]}")
        print(f"Test type: {r.get('test_type', '')[:120]}")
        print(f"Standards: {r.get('standards', '')[:120]}")
        print()


if __name__ == "__main__":
    main()
