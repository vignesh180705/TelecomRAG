import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API")

COLLECTION_NAME = "3gpp_knowledge"

client = QdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY,
    timeout=60,
)

model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2"
)

query = "How is PDU session establishment performed in the 5G core network?"

query_vector = model.encode(
    query,
    normalize_embeddings=True
).tolist()

results = client.query_points(
    collection_name=COLLECTION_NAME,
    query=query_vector,
    limit=5,
    with_payload=True
).points

print("\n" + "=" * 80)
print("QUERY")
print("=" * 80)
print(query)

print("\n" + "=" * 80)
print("RESULTS")
print("=" * 80)

for i, result in enumerate(results, 1):

    payload = result.payload

    print(f"\n--- Result {i} ---")
    print(f"Score       : {result.score}")
    print(f"Chunk ID    : {payload.get('chunk_id')}")
    print(f"Document    : {payload.get('document_number')}")
    print(f"Release     : {payload.get('release')}")
    print(f"Version     : {payload.get('version')}")
    print(f"Section     : {payload.get('section_number')} "
          f"{payload.get('section_title')}")
    print(f"Section Path: {payload.get('section_path')}")
    print(f"Pages       : {payload.get('page_start')} - "
          f"{payload.get('page_end')}")
    print(f"Chunk Type  : {payload.get('chunk_type')}")

    print("\nText:")
    print(payload.get("text", "")[:2000])