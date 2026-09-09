import json
import os
import re

from pydantic import BaseModel, Field
from xai_sdk import Client
from xai_sdk.chat import system, user


# ============================================================
# STRUCTURED OUTPUT SCHEMA
# ============================================================

class EntityExtraction(BaseModel):

    name: str = Field(
        description="Canonical name of the entity"
    )

    entity_type: str = Field(
        description="One of the allowed 3GPP ontology entity types"
    )

    description: str = Field(
        default="",
        description="Short description grounded in the text"
    )

    aliases: list[str] = Field(
        default_factory=list
    )

    evidence: str = Field(
        description="Exact text supporting this entity"
    )


class RelationshipExtraction(BaseModel):

    source: str

    source_type: str

    relationship: str

    target: str

    target_type: str

    evidence: str = Field(
        description="Exact text supporting this relationship"
    )


class ExtractionResult(BaseModel):

    entities: list[EntityExtraction] = Field(
        default_factory=list
    )

    relationships: list[RelationshipExtraction] = Field(
        default_factory=list
    )


# ============================================================
# NAME NORMALIZATION
# ============================================================

def normalize_name(name):

    name = name.lower().strip()

    name = re.sub(
        r"[^a-z0-9]+",
        "-",
        name
    )

    return name.strip("-")


def make_entity_id(
    entity_type,
    name
):

    return (
        f"{entity_type.lower()}:"
        f"{normalize_name(name)}"
    )


# ============================================================
# GROK EXTRACTOR
# ============================================================

class ThreeGPPExtractor:

    def __init__(
        self,
        schema,
        model=None
    ):

        self.schema = schema

        self.model = model or os.getenv(
            "GROK_MODEL",
            "grok-4.6"
        )

        api_key = os.environ[
            "XAI_API_KEY"
        ]

        self.client = Client(
            api_key=api_key
        )

    # --------------------------------------------------------
    # Extract
    # --------------------------------------------------------

    def extract(self, chunk):

        ontology = self.schema.prompt_schema()

        system_prompt = f"""
You are a specialist information-extraction system
for 3GPP technical specifications.

Your job is to extract a high-quality property graph
from the supplied 3GPP text.

You MUST obey the supplied ontology.

ONTOLOGY
========

{json.dumps(
    ontology,
    indent=2,
    ensure_ascii=False
)}

EXTRACTION RULES
================

1. Extract only entities that are explicitly supported
   by the supplied text.

2. Every entity_type MUST exactly match one of the
   ontology entity types.

3. Extract relationships only when the text explicitly
   supports the relationship.

4. Every relationship type MUST exactly match an
   ontology relationship.

5. Do NOT infer a relationship simply because the ontology
   permits it.

6. Do NOT invent entities.

7. Do NOT use outside knowledge.

8. Preserve the exact evidence text supporting every
   extracted entity and relationship.

9. Acronyms should only become entities when they have
   semantic significance in the supplied text.

10. Prefer canonical technical names.

11. If an entity is described using an acronym and its
    expanded form, use the expanded technical name as
    canonical name and put the acronym in aliases.

12. If there is insufficient evidence, do not extract it.

13. The resulting graph must be defensible directly from
    the source text.
"""

        user_prompt = f"""
SOURCE DOCUMENT:
{chunk["document"]}

PAGE:
{chunk["page_start"]}

CHUNK ID:
{chunk["chunk_id"]}

SOURCE TEXT:
--------------------
{chunk["text"]}
--------------------

Extract all supported 3GPP entities and relationships.
"""

        chat = self.client.chat.create(
            model=self.model,
            response_format=ExtractionResult
        )

        chat.append(
            system(system_prompt)
        )

        chat.append(
            user(user_prompt)
        )

        response, result = chat.parse(
            ExtractionResult
        )

        return self.validate(
            result
        )

    # --------------------------------------------------------
    # Validate against ontology
    # --------------------------------------------------------

    def validate(
        self,
        result
    ):

        valid_entity_types = set(
            self.schema.entity_types()
        )

        valid_entities = []

        for entity in result.entities:

            if (
                entity.entity_type
                not in valid_entity_types
            ):
                continue

            if not entity.name.strip():
                continue

            valid_entities.append(
                entity
            )

        valid_relationships = []

        for relationship in result.relationships:

            if not self.schema.valid_relationship(
                relationship.relationship,
                relationship.source_type,
                relationship.target_type
            ):
                continue

            valid_relationships.append(
                relationship
            )

        return {
            "entities": [
                self.entity_to_dict(e)
                for e in valid_entities
            ],

            "relationships": [
                self.relationship_to_dict(r)
                for r in valid_relationships
            ]
        }

    # --------------------------------------------------------
    # Convert entity
    # --------------------------------------------------------

    @staticmethod
    def entity_to_dict(entity):

        return {
            "entity_id": make_entity_id(
                entity.entity_type,
                entity.name
            ),

            "name": entity.name,

            "entity_type":
                entity.entity_type,

            "description":
                entity.description,

            "aliases":
                entity.aliases,

            "evidence":
                entity.evidence
        }

    # --------------------------------------------------------
    # Convert relationship
    # --------------------------------------------------------

    @staticmethod
    def relationship_to_dict(
        relationship
    ):

        return {

            "source":
                relationship.source,

            "source_type":
                relationship.source_type,

            "source_id":
                make_entity_id(
                    relationship.source_type,
                    relationship.source
                ),

            "relationship":
                relationship.relationship,

            "target":
                relationship.target,

            "target_type":
                relationship.target_type,

            "target_id":
                make_entity_id(
                    relationship.target_type,
                    relationship.target
                ),

            "evidence":
                relationship.evidence
        }