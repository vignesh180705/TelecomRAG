import json
from pathlib import Path
from config import DOCUMENTS_FILE, CHUNKS_FILE, EXTRACTIONS_FILE, validate_config
from graph_loader import GraphLoader

def read_jsonl(path):
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)

def main():
    validate_config(require_neo4j=True)
    for p in (DOCUMENTS_FILE, CHUNKS_FILE, EXTRACTIONS_FILE):
        if not p.exists():
            raise RuntimeError(f"Missing {p}. Run earlier stages first.")

    loader = GraphLoader()
    try:
        print("=" * 70)
        print("STAGE 3: JSONL -> NEO4J")
        print("=" * 70)
        loader.verify_connectivity()
        loader.init_schema()

        documents = list(read_jsonl(DOCUMENTS_FILE))
        chunks = list(read_jsonl(CHUNKS_FILE))
        chunk_map = {c["chunk_id"]: c for c in chunks}

        for d in documents:
            loader.load_document(d)
        print(f"[OK] Documents loaded: {len(documents)}")

        for c in chunks:
            loader.load_chunk(c)
        print(f"[OK] Chunks loaded: {len(chunks)}")

        entities = mentions = relationships = 0
        for x in read_jsonl(EXTRACTIONS_FILE):
            c = chunk_map.get(x["chunk_id"])
            if not c:
                print(f"[WARN] Missing chunk {x['chunk_id']}")
                continue
            for e in x.get("entities", []):
                loader.load_entity(e)
                loader.load_source_mention(e, c)
                entities += 1
                mentions += 1
            for r in x.get("relationships", []):
                loader.load_relationship(r, c)
                relationships += 1

        print(f"[OK] Entities: {entities}")
        print(f"[OK] Source mentions: {mentions}")
        print(f"[OK] Relationships: {relationships}")
        print("Stage 3 complete.")
    finally:
        loader.close()

if __name__ == "__main__":
    main()
