import json
from pathlib import Path
import uuid
import os
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct
)


# ============================================================
# CONFIG
# ============================================================

load_dotenv()

CHUNKS_FILE = (
    "vector_data/chunks/all_chunks.json"
)

QDRANT_PATH = (
    "vector_data/qdrant"
)

COLLECTION_NAME = (
    "3gpp_knowledge"
)

EMBEDDING_MODEL = (
    "sentence-transformers/all-MiniLM-L6-v2"
)

BATCH_SIZE = 32

QDRANT_API=os.getenv("QDRANT_API")
QDRANT_URL=os.getenv("QDRANT_URL")

def qdrant_point_id(chunk_id):
    """
    Convert our application-level chunk_id into a deterministic UUID
    accepted by Qdrant.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


# ============================================================
# LOAD CHUNKS
# ============================================================

with open(
    CHUNKS_FILE,
    "r",
    encoding="utf-8"
) as f:

    chunks = json.load(f)


print(
    f"Loaded {len(chunks)} chunks"
)


# ============================================================
# EMBEDDING MODEL
# ============================================================

model = SentenceTransformer(
    EMBEDDING_MODEL
)

VECTOR_SIZE = (
    model.get_sentence_embedding_dimension()
)

print(
    f"Vector dimension: "
    f"{VECTOR_SIZE}"
)


# ============================================================
# QDRANT
# ============================================================

client = QdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_API,
    timeout=300
)

if client.collection_exists(COLLECTION_NAME):
    print(f"Deleting existing collection: {COLLECTION_NAME}")
    client.delete_collection(COLLECTION_NAME)


# ============================================================
# CREATE COLLECTION
# ============================================================

collections = (
    client
    .get_collections()
    .collections
)

existing = [
    collection.name
    for collection in collections
]


if COLLECTION_NAME not in existing:

    client.create_collection(

        collection_name=
            COLLECTION_NAME,

        vectors_config=
            VectorParams(

                size=VECTOR_SIZE,

                distance=
                    Distance.COSINE
            )
    )

    print(
        "Created collection"
    )

else:

    print(
        "Collection already exists"
    )


# ============================================================
# INSERT
# ============================================================

for start in range(
    0,
    len(chunks),
    BATCH_SIZE
):

    batch = chunks[
        start:start + BATCH_SIZE
    ]

    texts = [
        chunk[
            "embedding_text"
        ]
        for chunk in batch
    ]

    vectors = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False
    )

    points = []

    for chunk, vector in zip(
        batch,
        vectors
    ):

        payload = {

            "chunk_id":
                chunk["chunk_id"],

            "document_id":
                chunk["document_id"],

            "filename":
                chunk["filename"],

            "document_number":
                chunk["document_number"],

            "document_type":
                chunk["document_type"],

            "release":
                chunk["release"],

            "version":
                chunk["version"],

            "section_number":
                chunk["section_number"],

            "section_title":
                chunk["section_title"],

            "section_level":
                chunk["section_level"],

            "parent_section":
                chunk["parent_section"],

            "section_path":
                chunk["section_path"],

            "annex":
                chunk["annex"],

            "annex_letter":
                chunk["annex_letter"],

            "annex_type":
                chunk["annex_type"],

            "page_start":
                chunk["page_start"],

            "page_end":
                chunk["page_end"],

            "chunk_index":
                chunk["chunk_index"],

            "global_chunk_index":
                chunk["global_chunk_index"],

            "chunk_type":
                chunk["chunk_type"],

            "token_count":
                chunk["token_count"],

            "text":
                chunk["text"]
        }

        points.append(
            PointStruct(

                id=qdrant_point_id(chunk[
                    "chunk_id"
                ]),

                vector=vector.tolist(),

                payload=payload
            )
        )

    client.upsert(

        collection_name=
            COLLECTION_NAME,

        points=points
    )

    end = min(
        start + BATCH_SIZE,
        len(chunks)
    )

    print(
        f"Inserted "
        f"{end}/{len(chunks)}"
    )


print(
    "\nQdrant database ready."
)