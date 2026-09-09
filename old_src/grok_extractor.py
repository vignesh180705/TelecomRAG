import json
import time
import hashlib
from pathlib import Path
from typing import List

from groq import Groq
from pydantic import BaseModel, Field, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

from config import GROQ_API_KEY, GROQ_MODEL, REQUEST_DELAY_SECONDS
from schema_loader import Ontology


class EntityExtraction(BaseModel):
    name: str
    entity_type: str
    description: str = ""
    aliases: List[str] = Field(default_factory=list)
    evidence: str


class RelationshipExtraction(BaseModel):
    source: str
    source_type: str
    relationship: str
    target: str
    target_type: str
    evidence: str


class ExtractionResult(BaseModel):
    entities: List[EntityExtraction] = Field(default_factory=list)
    relationships: List[RelationshipExtraction] = Field(default_factory=list)


def entity_id(entity_type, name):
    normalized = " ".join(name.lower().split())
    return f"{entity_type.lower()}:{hashlib.sha1(normalized.encode('utf-8')).hexdigest()[:16]}"


class GrokExtractor:
    """
    Extracts ontology-constrained entities and explicit semantic relationships
    from PDF chunks using a Groq-hosted LLM.

    The LLM only returns structured extraction. Python performs validation,
    deterministic IDs, provenance handling, checkpointing, and Neo4j loading.
    """

    def __init__(self, ontology: Ontology):
        if not GROQ_API_KEY:
            raise RuntimeError(
                "GROQ_API_KEY is not configured. "
                "Add GROQ_API_KEY=... to D:\\TelecomRAG\\.env"
            )

        self.client = Groq(api_key=GROQ_API_KEY)
        self.model = GROQ_MODEL
        self.ontology = ontology

    def _prompt(self, chunk):
        return f"""You are extracting a defensible knowledge graph from a 3GPP standards corpus.

ONTOLOGY:
{self.ontology.prompt_schema()}

STRICT RULES:
1. Extract only entities explicitly supported by the supplied text.
2. entity_type MUST exactly match one of the ontology entity types.
3. Extract only relationships explicitly stated or directly expressed by the supplied text.
4. relationship MUST exactly match an ontology relationship type.
5. The relationship source_type and target_type must match the ontology signature.
6. Do not infer a relationship merely because the ontology permits it.
7. Do not use outside knowledge.
8. Do not invent entities, aliases, descriptions, or evidence.
9. Evidence MUST be a short exact quotation copied from the supplied chunk.
10. Prefer canonical technical names; put acronyms in aliases only when the text explicitly associates them.
11. If evidence is insufficient, do not extract the item.
12. Keep names technically precise and avoid generic nouns unless the ontology clearly supports them.
13. Do not merge two similar names unless the supplied text explicitly establishes that they are the same entity.
14. Do not create semantic edges from ontology definitions alone.
15. The PDF page number and document below are provenance metadata; do not invent different values.

DOCUMENT: {chunk["filename"]}
PDF PAGE: {chunk["page_start"]}
CHUNK ID: {chunk["chunk_id"]}

TEXT:
---BEGIN CHUNK---
{chunk["text"]}
---END CHUNK---
"""

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=8, max=60),
        reraise=True,
    )
    def extract(self, chunk):
        schema = ExtractionResult.model_json_schema()

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Return only structured JSON matching the supplied JSON schema. "
                        "Every extracted item must be defensible from the supplied text. "
                        "Do not add commentary outside the JSON object."
                    ),
                },
                {
                    "role": "user",
                    "content": self._prompt(chunk),
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "three_gpp_extraction",
                    "strict": False,
                    "schema": schema,
                },
            },
            temperature=0,
        )

        content = response.choices[0].message.content or "{}"

        try:
            result = ExtractionResult.model_validate(json.loads(content))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise RuntimeError(
                f"Groq returned invalid structured extraction: {exc}\n"
                f"Raw response: {content[:4000]}"
            ) from exc

        valid_entities = []
        for e in result.entities:
            if not self.ontology.valid_entity_type(e.entity_type):
                continue
            if not e.name.strip() or not e.evidence.strip():
                continue

            valid_entities.append({
                "entity_id": entity_id(e.entity_type, e.name),
                "canonical_name": e.name.strip(),
                "entity_type": e.entity_type,
                "aliases": sorted(
                    set(a.strip() for a in e.aliases if a.strip())
                ),
                "description": e.description.strip(),
                "evidence": e.evidence.strip(),
                "chunk_id": chunk["chunk_id"],
                "document": chunk["filename"],
                "page": chunk["page_start"],
            })

        valid_relationships = []
        for r in result.relationships:
            if not r.source.strip() or not r.target.strip():
                continue
            if not r.evidence.strip():
                continue

            if not self.ontology.valid_relationship(
                r.relationship,
                r.source_type,
                r.target_type,
            ):
                continue

            if r.relationship == "RELATED_TO":
                continue
            if e.evidence.strip() not in chunk["text"]:
                continue
            if r.evidence.strip() not in chunk["text"]:
                continue

            valid_relationships.append({
                "source_id": entity_id(r.source_type, r.source),
                "source_name": r.source.strip(),
                "source_type": r.source_type,
                "relationship": r.relationship,
                "target_id": entity_id(r.target_type, r.target),
                "target_name": r.target.strip(),
                "target_type": r.target_type,
                "evidence": r.evidence.strip(),
                "chunk_id": chunk["chunk_id"],
                "document": chunk["filename"],
                "page": chunk["page_start"],
            })

        if REQUEST_DELAY_SECONDS:
            time.sleep(REQUEST_DELAY_SECONDS)

        return {
            "entities": valid_entities,
            "relationships": valid_relationships,
        }


def checkpoint_path(output_dir):
    return Path(output_dir) / "extractions.jsonl"


def load_checkpoint(path):
    done = {}
    p = Path(path)

    if not p.exists():
        return done

    with p.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            obj = json.loads(line)
            done[obj["chunk_id"]] = obj

    return done



def append_checkpoint(path, chunk_id, extraction):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "chunk_id": chunk_id,
        **extraction,
    }

    with path.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(record, ensure_ascii=False) + "\n"
        )