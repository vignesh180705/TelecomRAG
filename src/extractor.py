"""
Chunk JSON -> local LLM -> extraction_raw.json

No Grok/API is used here.
The LLM is local through Ollama and accessed through LlamaIndex.
"""

import json
import re
import sys
from pathlib import Path

from llama_index.core import Settings
from llama_index.llms.ollama import Ollama

from config import (
    CHUNKS_FILE,
    RAW_EXTRACTION_FILE,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    ALLOWED_ENTITY_TYPES,
)

SYSTEM_PROMPT = f"""
You extract technical knowledge from 3GPP specification text.

Allowed entity types:
{", ".join(ALLOWED_ENTITY_TYPES)}

Rules:
1. Extract only entities explicitly supported by the supplied chunk.
2. Do not invent entities or facts.
3. entity_type MUST be one of the allowed entity types.
4. Use CONCEPT only when the concept genuinely does not fit a more specific type.
5. Extract relationships only when the chunk explicitly supports the relationship.
6. Do not use page numbers or clause numbers from your own knowledge. Provenance is supplied by the caller.
7. Evidence must be a short exact or near-exact span from the supplied chunk.
8. Keep names canonical and concise.
9. Return JSON only with:
{{
  "chunk_id": "...",
  "entities": [
    {{
      "name": "...",
      "entity_type": "...",
      "description": "...",
      "evidence": "..."
    }}
  ],
  "relationships": [
    {{
      "source": "...",
      "relationship": "...",
      "target": "...",
      "evidence": "..."
    }}
  ]
}}
"""


def strip_code_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def build_prompt(chunk):
    return f"""
{SYSTEM_PROMPT}

CHUNK ID:
{chunk["chunk_id"]}

DOCUMENT:
{chunk["document"]}

PAGE:
{chunk["page"]}

CLAUSE:
{chunk.get("clause", "")}

TEXT:
{chunk["text"]}
"""


def create_llm():
    llm = Ollama(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        request_timeout=300.0,
        temperature=0.0,
    )
    Settings.llm = llm
    return llm


def load_existing():
    if not RAW_EXTRACTION_FILE.exists():
        return {"version": "1.0", "chunk_count": 0, "chunks": []}

    return json.loads(RAW_EXTRACTION_FILE.read_text(encoding="utf-8"))


def main():
    if not CHUNKS_FILE.exists():
        print(f"Missing {CHUNKS_FILE}. Run create_chunks.py first.")
        sys.exit(1)

    payload = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
    chunks = payload["chunks"]

    output = load_existing()
    done = {x["chunk_id"] for x in output.get("chunks", [])}

    llm = create_llm()

    for index, chunk in enumerate(chunks, start=1):
        if chunk["chunk_id"] in done:
            print(f"[{index}/{len(chunks)}] skip {chunk['chunk_id']}")
            continue

        print(f"[{index}/{len(chunks)}] extracting {chunk['chunk_id']}")

        response = llm.complete(build_prompt(chunk))
        raw = strip_code_fences(str(response))

        try:
            extracted = json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"  JSON parse failure: {exc}")
            print("  Chunk is NOT marked complete.")
            continue

        extracted["chunk_id"] = chunk["chunk_id"]
        extracted["document"] = chunk["document"]
        extracted["document_file"] = chunk["document_file"]
        extracted["page"] = chunk["page"]
        extracted["clause"] = chunk.get("clause", "")
        extracted["section_title"] = chunk.get("section_title", "")

        output["chunks"].append(extracted)
        output["chunk_count"] = len(output["chunks"])

        RAW_EXTRACTION_FILE.parent.mkdir(parents=True, exist_ok=True)
        RAW_EXTRACTION_FILE.write_text(
            json.dumps(output, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print(f"Extraction finished: {RAW_EXTRACTION_FILE}")


if __name__ == "__main__":
    main()
