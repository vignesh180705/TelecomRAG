import json
from pathlib import Path

from config import CHUNKS_FILE, SCHEMA_FILE, validate_config
from grok_extractor import (
    GrokExtractor,
    ExtractionResult,
)
from schema_loader import Ontology


def main():
    validate_config(require_groq=True)

    with Path(CHUNKS_FILE).open("r", encoding="utf-8") as f:
        chunk = json.loads(next(line for line in f if line.strip()))

    ontology = Ontology.from_file(SCHEMA_FILE)
    extractor = GrokExtractor(ontology)

    print("=" * 70)
    print("GROQ SINGLE-CHUNK DIAGNOSTIC")
    print("=" * 70)
    print(f"Chunk ID : {chunk['chunk_id']}")
    print(f"Document : {chunk['filename']}")
    print(f"PDF page : {chunk['page_start']}")

    print("\nTEXT")
    print("-" * 70)
    print(chunk["text"])
    print("-" * 70)

    response = extractor.client.chat.completions.create(
        model=extractor.model,
        messages=[
            {
                "role": "system",
                "content": (
                    "Return only structured JSON matching the supplied schema. "
                    "Do not add commentary."
                ),
            },
            {
                "role": "user",
                "content": extractor._prompt(chunk),
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "three_gpp_extraction",
                "strict": False,
                "schema": ExtractionResult.model_json_schema(),
            },
        },
        temperature=0,
    )

    raw = response.choices[0].message.content or "{}"

    print("\n" + "=" * 70)
    print("RAW GROQ RESPONSE")
    print("=" * 70)
    print(raw)

    print("\n" + "=" * 70)
    print("PARSED RESULT")
    print("=" * 70)

    try:
        result = ExtractionResult.model_validate(json.loads(raw))

        print(f"Entities returned     : {len(result.entities)}")
        print(f"Relationships returned: {len(result.relationships)}")

        print("\nENTITIES:")
        for e in result.entities:
            print(f"  name       : {e.name}")
            print(f"  type       : {e.entity_type}")
            print(f"  evidence   : {e.evidence!r}")
            print()

        print("RELATIONSHIPS:")
        for r in result.relationships:
            print(
                f"  {r.source} "
                f"--[{r.relationship}]--> "
                f"{r.target}"
            )
            print(f"  evidence: {r.evidence!r}")
            print()

    except Exception as exc:
        print("PARSING ERROR:")
        print(exc)


if __name__ == "__main__":
    main()