import json
from pathlib import Path

from config import CHUNKS_FILE, SCHEMA_FILE
from schema_loader import Ontology
from grok_extractor import GrokExtractor


def find_chunk():
    with Path(CHUNKS_FILE).open("r", encoding="utf-8") as f:
        for line in f:
            chunk = json.loads(line)

            if (
                chunk["filename"] == "TR_22.870.pdf"
                and chunk["page_start"] == 35
            ):
                return chunk

    return None


def main():
    print("=" * 70)
    print("TESTING TR_22.870.pdf - PDF PAGE 35")
    print("=" * 70)

    chunk = find_chunk()

    if not chunk:
        raise RuntimeError(
            "Could not find TR_22.870.pdf page 35 in chunks.jsonl"
        )

    print(f"Chunk ID : {chunk['chunk_id']}")
    print(f"Document : {chunk['filename']}")
    print(f"PDF page : {chunk['page_start']}")
    print()
    print("TEXT:")
    print("-" * 70)
    print(chunk["text"])
    print("-" * 70)

    ontology = Ontology.from_file(SCHEMA_FILE)
    extractor = GrokExtractor(ontology)

    print()
    print("Calling Groq...")
    print()

    result = extractor.extract(chunk)

    print("=" * 70)
    print("EXTRACTION RESULT")
    print("=" * 70)

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()