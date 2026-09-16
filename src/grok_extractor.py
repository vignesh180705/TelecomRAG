import hashlib
import json
import time
from pathlib import Path
from typing import List
from groq import Groq
from pydantic import BaseModel, Field, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential
from config import GROQ_API_KEY, GROQ_MODEL, REQUEST_DELAY_SECONDS
from schema_loader import Ontology

class EntityExtraction(BaseModel):
    name: str = Field(description="Exact entity name appearing in the source text")
    entity_type: str = Field(description="Must exactly match an ontology entity_type")
    description: str = Field(default="", description="Description supported only by source text")
    aliases: List[str] = Field(default_factory=list)
    evidence: str = Field(description="Exact substring copied from source text")


class RelationshipExtraction(BaseModel):
    source: str
    source_type: str
    relationship: str
    target: str
    target_type: str
    evidence: str = Field(description="Exact substring copied from source text")


class ExtractionResult(BaseModel):
    entities: List[EntityExtraction] = Field(default_factory=list)
    relationships: List[RelationshipExtraction] = Field(default_factory=list)

def entity_id(entity_type, name):
    normalized = " ".join(name.lower().split())
    return f"{entity_type.lower()}:{hashlib.sha1(normalized.encode('utf-8')).hexdigest()[:16]}"

class GrokExtractor:
    def __init__(self, ontology):
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not configured in .env")
        self.client = Groq(api_key=GROQ_API_KEY)
        self.model = GROQ_MODEL
        self.ontology = ontology

    def _prompt(self, chunk):

        ontology_text = self.ontology.prompt_schema()

        return f"""
You are an information extraction system processing 3GPP technical
specifications and technical reports.

Your task is to extract a HIGH-QUALITY, DEFENSIBLE knowledge graph
from ONLY the supplied PDF text.

You MUST follow the ontology below.

============================================================
ONTOLOGY
============================================================

{ontology_text}

============================================================
ENTITY EXTRACTION
============================================================

Extract entities explicitly mentioned or explicitly described
in the supplied text.

An entity is a meaningful 3GPP technical concept that belongs
to one of the ontology classes.

Examples of useful entities include:

- network functions
- network entities
- interfaces/reference points
- protocols
- procedures
- states
- parameters
- information elements
- QoS concepts
- security concepts
- network slices
- services
- use cases
- requirements
- performance metrics
- resources
- applications
- analytics/AI concepts

DO NOT restrict extraction only to the examples listed in the ontology.
The examples are guidance for classification.

Every entity MUST have:

name
entity_type
description
aliases
evidence

============================================================
IMPORTANT CLASSIFICATION GUIDANCE
============================================================

NETWORK_FUNCTION
Use for a logical network function.

Examples:
AMF, SMF, UPF, PCF, NWDAF, NEF.

NETWORK_ENTITY
Use for a physical/logical network node, device, gateway,
or network-side entity.

Examples:
UE, gNB, DN.

INTERFACE
Use for an interface or reference point.

Examples:
N1, N2, N3, N4, N7, Xn.

PROTOCOL
Use for a protocol or protocol layer.

Examples:
RRC, PDCP, RLC, MAC, SDAP, NGAP.

PROCEDURE
Use for an explicitly described procedure or process.

Examples:
Registration, PDU Session Establishment,
Data Collection Procedure.

STATE
Use for an explicitly named protocol/network/UE state.

Examples:
RRC_IDLE, RRC_CONNECTED, CM-IDLE.

PARAMETER
Use for a configuration, capability, or control parameter.

INFORMATION_ELEMENT
Use for signalling information or information elements.

QOS_CONCEPT
Use for explicitly described QoS concepts.

SECURITY_CONCEPT
Use for security, privacy, identity, authentication,
authorization, trust, confidentiality, integrity, etc.

NETWORK_SLICE
Use for explicit network slice concepts.

SERVICE
Use for a service or service capability.

USE_CASE
Use for an explicitly identified use case.

REQUIREMENT
Use for explicit requirements, especially statements
identified with [PR ...].

PERFORMANCE_METRIC
Use for explicit performance/KPI concepts.

RESOURCE
Use for radio/network resources.

APPLICATION
Use for application/application functions.

ANALYTICS_CONCEPT
Use for analytics, AI/ML, NWDAF analytics,
digital twin, etc.

============================================================
REQUIREMENT HANDLING
============================================================

When the text contains a requirement such as:

[PR 5.5.5.3-1] ...

extract it as a REQUIREMENT when appropriate.

The canonical name may be the requirement identifier,
for example:

"PR 5.5.5.3-1"

The description should summarize the requirement using
ONLY the supplied text.

The evidence MUST be copied exactly from the supplied text.

============================================================
EVIDENCE RULE
============================================================

THIS IS CRITICAL.

Every entity MUST have an evidence quotation.

The evidence must be an EXACT substring of the supplied text.

Do not paraphrase evidence.

Do not rewrite evidence.

Do not correct spelling.

Do not use information outside the supplied chunk.

For example, if the supplied text says:

"Data Anonymisation, Aggregation or Normalization"

then evidence may be:

"Data Anonymisation, Aggregation or Normalization"

but must NOT be:

"Data anonymization and aggregation are used to protect privacy."

============================================================
RELATIONSHIP EXTRACTION
============================================================

Extract relationships ONLY when the supplied text explicitly
states the relationship.

The ontology merely tells you which relationship types are allowed.

It does NOT mean that every allowed relationship should be created.

For example:

If the text explicitly says:

"AMF and SMF are separate Network Functions"

do NOT automatically create COMMUNICATES_WITH.

If the text explicitly says:

"AMF sends ... to SMF"

then a relationship may be extracted if the ontology
permits that relationship.

Never infer relationships from general 3GPP knowledge.

Do not create RELATED_TO relationships.

Every relationship MUST contain:

source
source_type
relationship
target
target_type
evidence

Relationship evidence must also be an exact substring
of the supplied text.

============================================================
NO OUTSIDE KNOWLEDGE
============================================================

Do not use knowledge from other 3GPP specifications.

Do not assume what an abbreviation means unless the supplied
text establishes it.

Do not invent missing entities.

Do not infer unstated relationships.

When uncertain, omit the extraction.

============================================================
PROVENANCE
============================================================

The following metadata identifies the exact source:

DOCUMENT:
{chunk["filename"]}

PDF PHYSICAL PAGE:
{chunk["page_start"]}

CHUNK ID:
{chunk["chunk_id"]}

Do not put provenance information into evidence.

============================================================
SOURCE TEXT
============================================================

--- BEGIN SOURCE TEXT ---

{chunk["text"]}

--- END SOURCE TEXT ---

============================================================
FINAL INSTRUCTION
============================================================

Return ONLY JSON matching the supplied extraction schema.

Do not return explanations.

Do not return markdown.

Do not return commentary.

Extract all well-supported entities from the supplied text,
not merely one or two examples.

If there are genuinely no extractable entities, return empty lists.
"""

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=8, max=60), reraise=True)
    def extract(self, chunk):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "Return only structured JSON matching the supplied schema. Do not add commentary."},
                {"role": "user", "content": self._prompt(chunk)},
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

        content = response.choices[0].message.content or "{}"
        try:
            result = ExtractionResult.model_validate(json.loads(content))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise RuntimeError(f"Invalid Groq extraction: {exc}\nRaw: {content[:4000]}") from exc

        text = chunk["text"]
        entities, relationships = [], []

        for e in result.entities:
            evidence = e.evidence.strip()
            if not self.ontology.valid_entity_type(e.entity_type):
                continue
            if not e.name.strip() or not evidence or evidence not in text:
                continue
            entities.append({
                "entity_id": entity_id(e.entity_type, e.name),
                "canonical_name": e.name.strip(),
                "entity_type": e.entity_type,
                "aliases": sorted(set(a.strip() for a in e.aliases if a.strip())),
                "description": e.description.strip(),
                "evidence": evidence,
                "chunk_id": chunk["chunk_id"],
                "document": chunk["filename"],
                "document_id": chunk["document_id"],
                "page": chunk["page_start"],
            })

        for r in result.relationships:
            evidence = r.evidence.strip()
            if r.relationship == "RELATED_TO":
                continue
            if not r.source.strip() or not r.target.strip() or not evidence:
                continue
            if evidence not in text:
                continue
            if not self.ontology.valid_relationship(r.relationship, r.source_type, r.target_type):
                continue
            relationships.append({
                "source_id": entity_id(r.source_type, r.source),
                "source_name": r.source.strip(),
                "source_type": r.source_type,
                "relationship": r.relationship,
                "target_id": entity_id(r.target_type, r.target),
                "target_name": r.target.strip(),
                "target_type": r.target_type,
                "evidence": evidence,
                "chunk_id": chunk["chunk_id"],
                "document": chunk["filename"],
                "document_id": chunk["document_id"],
                "page": chunk["page_start"],
            })

        if REQUEST_DELAY_SECONDS:
            time.sleep(REQUEST_DELAY_SECONDS)

        return {"entities": entities, "relationships": relationships}

def load_checkpoint(path):
    done = {}
    p = Path(path)
    if not p.exists():
        return done
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                obj = json.loads(line)
                done[obj["chunk_id"]] = obj
    return done

def append_checkpoint(path, chunk_id, extraction):
    with Path(path).open("a", encoding="utf-8") as f:
        f.write(json.dumps({"chunk_id": chunk_id, **extraction}, ensure_ascii=False) + "\n")
        f.flush()
