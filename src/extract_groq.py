import json
from pathlib import Path
from config import CHUNKS_FILE, EXTRACTIONS_FILE, SCHEMA_FILE, MAX_CHUNKS, validate_config
from grok_extractor import GrokExtractor, load_checkpoint, append_checkpoint
from schema_loader import Ontology

def read_jsonl(path):
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)

def main():
    validate_config(require_groq=True)
    if not CHUNKS_FILE.exists():
        raise RuntimeError(f"{CHUNKS_FILE} does not exist. Run Stage 1 first.")

    extractor = GrokExtractor(Ontology.from_file(SCHEMA_FILE))
    chunks = list(read_jsonl(CHUNKS_FILE))
    checkpoint = load_checkpoint(EXTRACTIONS_FILE)
    if MAX_CHUNKS > 0:
        chunks = chunks[:MAX_CHUNKS]

    print("=" * 70)
    print("STAGE 2: CHUNKS -> GROQ")
    print("=" * 70)
    print(f"Chunks: {len(chunks)} | checkpointed: {len(checkpoint)} | model: {extractor.model}")

    processed = skipped = 0
    for i, chunk in enumerate(chunks, 1):
        if chunk["chunk_id"] in checkpoint:
            skipped += 1
            print(f"[CHECKPOINT] {i}/{len(chunks)} {chunk['filename']} p.{chunk['page_start']}")
            continue

        print(f"[GROQ] {i}/{len(chunks)} {chunk['filename']} p.{chunk['page_start']}")
        extraction = extractor.extract(chunk)
        append_checkpoint(EXTRACTIONS_FILE, chunk["chunk_id"], extraction)
        processed += 1
        print(f"       entities={len(extraction['entities'])} relationships={len(extraction['relationships'])}")

    print(f"[OK] processed={processed} checkpointed={skipped}")
    print(f"[OK] {EXTRACTIONS_FILE}")

if __name__ == "__main__":
    main()
