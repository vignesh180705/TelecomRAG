"""
Embed original source chunks.

Input:
    chunks.json

Output:
    chunk_embeddings.json

One embedding per chunk_id.
"""

import json
import requests
from config import ROOT


# ============================================================
# CONFIG
# ============================================================

CHUNKS_FILE = ROOT / "data" / "chunks" / "chunks.json"

OUTPUT_FILE = ROOT / "out_copy" / "chunk_embeddings.json"

OLLAMA_URL = "http://localhost:11434/api/embed"

EMBEDDING_MODEL = "nomic-embed-text"

BATCH_SIZE = 32
REQUEST_TIMEOUT = 300


# ============================================================
# LOAD CHUNKS
# ============================================================

def load_chunks():

    if not CHUNKS_FILE.exists():
        raise FileNotFoundError(
            f"Missing chunks file: {CHUNKS_FILE}"
        )

    with open(
        CHUNKS_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)

    if isinstance(data, list):

        chunks = data

    elif isinstance(data, dict):

        chunks = data.get(
            "chunks",
            []
        )

    else:

        raise ValueError(
            "Unsupported chunks.json format."
        )

    if not chunks:

        raise ValueError(
            "No chunks found."
        )

    return chunks


# ============================================================
# CHUNK HELPERS
# ============================================================

def get_chunk_id(chunk):

    chunk_id = (
        chunk.get("chunk_id")
        or chunk.get("id")
    )

    if not chunk_id:

        raise ValueError(
            f"Chunk has no chunk_id: {chunk}"
        )

    return str(chunk_id)


def get_chunk_text(chunk):

    text = (
        chunk.get("text")
        or chunk.get("content")
        or chunk.get("chunk_text")
        or ""
    )

    return str(text).strip()


def build_embedding_text(chunk):

    document = chunk.get(
        "document",
        ""
    )

    page = chunk.get(
        "page",
        ""
    )

    clause = chunk.get(
        "clause",
        ""
    )

    section_title = chunk.get(
        "section_title",
        ""
    )

    text = get_chunk_text(chunk)

    return f"""Document: {document}
Page: {page}
Clause: {clause}
Section: {section_title}

Content:
{text}""".strip()


# ============================================================
# OLLAMA
# ============================================================

def embed_batch(texts):

    payload = {
        "model": EMBEDDING_MODEL,
        "input": texts,
        "truncate": True,
        "keep_alive": "10m",
    }

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    data = response.json()

    embeddings = data.get(
        "embeddings"
    )

    if not embeddings:

        raise RuntimeError(
            f"Ollama returned no embeddings:\n{data}"
        )

    return embeddings


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("CHUNK EMBEDDING")
    print("=" * 70)

    chunks = load_chunks()

    print(
        f"Chunks loaded: {len(chunks):,}"
    )

    print(
        f"Model: {EMBEDDING_MODEL}"
    )

    print(
        f"Batch size: {BATCH_SIZE}"
    )

    # --------------------------------------------------------
    # Resume support
    # --------------------------------------------------------

    existing = {}

    if OUTPUT_FILE.exists():

        with open(
            OUTPUT_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            existing_data = json.load(f)

        existing = existing_data.get(
            "embeddings",
            {}
        )

        print(
            f"Existing embeddings: "
            f"{len(existing):,}"
        )

    # --------------------------------------------------------
    # Prepare pending chunks
    # --------------------------------------------------------

    pending = []

    for chunk in chunks:

        chunk_id = get_chunk_id(chunk)

        if chunk_id in existing:
            continue

        text = get_chunk_text(chunk)

        if not text:

            print(
                f"WARNING: Empty chunk: "
                f"{chunk_id}"
            )

            continue

        pending.append({
            "chunk_id": chunk_id,
            "document": chunk.get(
                "document",
                ""
            ),
            "page": chunk.get(
                "page"
            ),
            "clause": chunk.get(
                "clause",
                ""
            ),
            "section_title": chunk.get(
                "section_title",
                ""
            ),
            "text": text,
            "embedding_text": build_embedding_text(
                chunk
            ),
        })

    print(
        f"Pending embeddings: "
        f"{len(pending):,}"
    )

    # --------------------------------------------------------
    # Generate embeddings
    # --------------------------------------------------------

    for start in range(
        0,
        len(pending),
        BATCH_SIZE
    ):

        batch = pending[
            start:start + BATCH_SIZE
        ]

        texts = [
            item["embedding_text"]
            for item in batch
        ]

        print(
            f"\nEmbedding "
            f"{start + 1:,} - "
            f"{start + len(batch):,} "
            f"of {len(pending):,}"
        )

        vectors = embed_batch(
            texts
        )

        if len(vectors) != len(batch):

            raise RuntimeError(
                "Number of embeddings does not "
                "match number of chunks."
            )

        for item, vector in zip(
            batch,
            vectors
        ):

            existing[
                item["chunk_id"]
            ] = {
                "chunk_id": item["chunk_id"],
                "document": item["document"],
                "page": item["page"],
                "clause": item["clause"],
                "section_title": item[
                    "section_title"
                ],

                # ORIGINAL chunk text
                "text": item["text"],

                "embedding": vector,
            }

        output = {
            "model": EMBEDDING_MODEL,
            "dimension": len(vectors[0]),
            "count": len(existing),
            "embeddings": existing,
        }

        with open(
            OUTPUT_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                output,
                f,
                ensure_ascii=False
            )

        print(
            f"Saved: {len(existing):,}"
        )

    print()
    print("=" * 70)
    print("EMBEDDING COMPLETE")
    print("=" * 70)

    print(
        f"Total embeddings: "
        f"{len(existing):,}"
    )

    if existing:

        first = next(
            iter(existing.values())
        )

        print(
            f"Dimension: "
            f"{len(first['embedding'])}"
        )

    print(
        f"Output: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()