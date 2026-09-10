"""LLM-based, source-grounded relationship extraction."""

import json
import os
from typing import Any, Dict, List, Tuple

from openai import OpenAI

try:
    from .entity_matcher import find_candidates
    from .prompts import build_relationship_prompt
    from .schema import RELATIONSHIP_SCHEMA, is_valid_relationship
except ImportError:
    from entity_matcher import find_candidates
    from prompts import build_relationship_prompt
    from schema import RELATIONSHIP_SCHEMA, is_valid_relationship


class RelationshipExtractor:

    def __init__(
        self,
        entities: List[Dict[str, Any]],
        patterns: Dict[str, List[Dict[str, Any]]],
    ):
        self.entities = entities
        self.patterns = patterns

        self.model = os.getenv(
            "GROQ_MODEL",
            "openai/gpt-oss-120b",
        )

        self.client = OpenAI(
            api_key=os.environ["GROQ_API_KEY"],
            base_url=os.getenv(
                "OPENAI_BASE_URL",
                "https://api.groq.com/openai/v1",
            ),
        )

    # ---------------------------------------------------------
    # Build candidate-specific relationship schema
    # ---------------------------------------------------------

    def _allowed_relationships(
        self,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Return only relationship types that could connect
        the candidate entity types.
        """

        candidate_types = {
            entity.get("entity_type")
            for entity in candidates
            if entity.get("entity_type")
        }

        allowed = []

        for relationship_type, definition in (
            RELATIONSHIP_SCHEMA or {}
        ).items():

            if not isinstance(definition, dict):
                continue

            source_types = set(
                definition.get("source_types") or []
            )

            target_types = set(
                definition.get("target_types") or []
            )

            source_possible = (
                not source_types
                or bool(source_types & candidate_types)
            )

            target_possible = (
                not target_types
                or bool(target_types & candidate_types)
            )

            if not (
                source_possible
                and target_possible
            ):
                continue

            allowed.append(
                {
                    "relationship_type": relationship_type,
                    "description": (
                        definition.get("description") or ""
                    ),
                    "source_types": list(source_types),
                    "target_types": list(target_types),
                }
            )
        return allowed

    # ---------------------------------------------------------
    # Compact entity representation
    # ---------------------------------------------------------

    def _candidate_payload(
        self,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        result = []

        for entity in candidates:
            description = entity.get("description") or ""
            aliases = entity.get("aliases") or []

            # Defensive normalization
            if not isinstance(description, str):
                description = str(description)

            if not isinstance(aliases, list):
                aliases = [str(aliases)]

            result.append(
                {
                    "entity_id": entity.get("entity_id"),
                    "canonical_name": entity.get("canonical_name") or "",
                    "entity_type": entity.get("entity_type") or "",
                    "description": description[:500],
                    "aliases": aliases[:10],
                }
            )

        return result

    # ---------------------------------------------------------
    # LLM call
    # ---------------------------------------------------------

    def _call_llm(
        self,
        chunk: Dict[str, Any],
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        allowed_relationships = (
            self._allowed_relationships(
                candidates
            )
            or []
        )

        candidate_payload = (
            self._candidate_payload(
                candidates
            )
            or []
        )

        prompt = build_relationship_prompt(
            chunk=chunk,
            candidates=candidate_payload,
            allowed_relationships=allowed_relationships,
        )

        if not prompt:
            return []

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You extract explicit, "
                        "source-grounded relationships "
                        "from O-RAN technical documents. "
                        "Never invent entities."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0,
            max_tokens=1200,
        )

        content = response.choices[0].message.content

        if not content:
            return []

        return self._parse_json(content)

    # ---------------------------------------------------------
    # JSON parsing
    # ---------------------------------------------------------

    def _parse_json(
        self,
        content: str,
    ) -> List[Dict[str, Any]]:

        content = content.strip()

        # Remove markdown code fences if the model uses them.
        if content.startswith("```"):
            lines = content.splitlines()

            if lines:
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            content = "\n".join(lines).strip()

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return []

        if isinstance(parsed, dict):
            relationships = parsed.get(
                "relationships",
                [],
            )
        elif isinstance(parsed, list):
            relationships = parsed
        else:
            relationships = []

        if not isinstance(
            relationships,
            list,
        ):
            return []

        return relationships

    # ---------------------------------------------------------
    # Validate extracted relationships
    # ---------------------------------------------------------

    def _validate_relationships(
        self,
        raw_relationships: List[Dict[str, Any]],
        candidates: List[Dict[str, Any]],
        chunk: Dict[str, Any],
    ) -> List[Dict[str, Any]]:

        entity_map = {
            entity["entity_id"]: entity
            for entity in candidates
            if entity.get("entity_id")
        }

        accepted = []

        for relation in raw_relationships:

            source_id = relation.get(
                "source_entity_id"
            )

            target_id = relation.get(
                "target_entity_id"
            )

            relationship_type = relation.get(
                "relationship_type"
            )

            evidence = relation.get(
                "evidence",
                "",
            )

            confidence = relation.get(
                "confidence",
                0.0,
            )

            # -------------------------------------------------
            # Entity validation
            # -------------------------------------------------

            if source_id not in entity_map:
                continue

            if target_id not in entity_map:
                continue

            # -------------------------------------------------
            # Relationship validation
            # -------------------------------------------------

            if relationship_type not in RELATIONSHIP_SCHEMA:
                continue

            source_type = entity_map[
                source_id
            ].get("entity_type")

            target_type = entity_map[
                target_id
            ].get("entity_type")

            if not is_valid_relationship(
                source_type,
                relationship_type,
                target_type,
            ):
                continue

            # -------------------------------------------------
            # Evidence validation
            # -------------------------------------------------

            if not evidence:
                continue

            chunk_text = chunk.get(
                "text",
                "",
            )

            # Evidence must actually occur in the source
            # chunk. Use normalized whitespace to tolerate
            # minor formatting differences.
            if not self._evidence_exists(
                evidence,
                chunk_text,
            ):
                continue

            # -------------------------------------------------
            # Normalize confidence
            # -------------------------------------------------

            try:
                confidence = float(
                    confidence
                )
            except (
                TypeError,
                ValueError,
            ):
                confidence = 0.0

            confidence = max(
                0.0,
                min(
                    1.0,
                    confidence,
                ),
            )

            accepted.append(
                {
                    "source_entity_id": source_id,
                    "relationship_type": relationship_type,
                    "target_entity_id": target_id,
                    "evidence": evidence,
                    "confidence": confidence,
                    "source": chunk.get(
                        "source"
                    ),
                    "page": chunk.get(
                        "page"
                    ),
                    "chunk_id": chunk.get(
                        "id"
                    ),
                }
            )

        return accepted

    # ---------------------------------------------------------
    # Evidence matching
    # ---------------------------------------------------------

    @staticmethod
    def _evidence_exists(
        evidence: str,
        text: str,
    ) -> bool:

        evidence_normalized = " ".join(
            evidence.split()
        ).lower()

        text_normalized = " ".join(
            text.split()
        ).lower()

        return (
            evidence_normalized
            in text_normalized
        )

    # ---------------------------------------------------------
    # Public extraction method
    # ---------------------------------------------------------

    def extract_from_chunk(
        self,
        chunk: Dict[str, Any],
    ) -> Tuple[
        List[Dict[str, Any]],
        Dict[str, Any],
    ]:

        text = chunk.get(
            "text",
            "",
        ).strip()

        if not text:
            return [], {
                "skipped": True,
                "reason": "empty_chunk",
                "raw": 0,
            }

        # Closed-world candidate matching.
        candidates = find_candidates(
            text,
            self.patterns,
            self.entities,
        )

        # No known entities → nothing to extract.
        if len(candidates) < 2:
            return [], {
                "skipped": True,
                "reason": "fewer_than_two_entities",
                "raw": 0,
            }

        # One entity can still be useful if the relationship
        # target appears in a canonical form that the LLM can
        # resolve from the supplied registry. However, most
        # relationship extraction will naturally require
        # multiple candidates.
        print(
            "DEBUG candidates:",
            [
                {
                    "id": e.get("entity_id"),
                    "name": e.get("canonical_name"),
                    "description_type": type(e.get("description")).__name__,
                    "aliases_type": type(e.get("aliases")).__name__,
                }
                for e in candidates
            ]
        )
        raw = self._call_llm(
            chunk,
            candidates,
        )

        validated = self._validate_relationships(
            raw,
            candidates,
            chunk,
        )

        return validated, {
            "skipped": False,
            "raw": len(raw),
            "accepted": len(validated),
        }