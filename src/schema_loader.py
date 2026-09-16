import json
from pathlib import Path


class Ontology:
    def __init__(self, schema):
        self.schema = schema

        # ------------------------------------------------------------
        # Entity types
        # ------------------------------------------------------------
        self.classes = {}

        for c in schema.get("ontology", {}).get("classes", []):
            entity_type = c.get("entity_type")
            if entity_type:
                self.classes[entity_type] = {
                    "definition": c.get("definition", ""),
                    "examples": c.get("examples", ""),
                }

        self.entity_types = set(self.classes.keys())

        # ------------------------------------------------------------
        # Relationships
        # ------------------------------------------------------------
        self.relationships = {}

        for r in schema.get("ontology", {}).get("relationships", []):
            relationship = r.get("relationship")
            if relationship:
                self.relationships[relationship] = {
                    "source_type": r.get("source_type"),
                    "target_type": r.get("target_type"),
                }

    @classmethod
    def from_file(cls, path):
        path = Path(path)

        with path.open("r", encoding="utf-8") as f:
            return cls(json.load(f))

    def valid_entity_type(self, value):
        return value in self.entity_types

    def valid_relationship(self, relationship, source_type, target_type):
        r = self.relationships.get(relationship)

        if not r:
            return False

        source_allowed = r["source_type"]
        target_allowed = r["target_type"]

        source_ok = (
            source_allowed == "*"
            or source_allowed == source_type
        )

        target_ok = (
            target_allowed == "*"
            or target_allowed == target_type
        )

        return source_ok and target_ok

    def prompt_schema(self):
        """
        Return a compact ontology description specifically for Groq.
        """

        lines = []

        lines.append("ENTITY TYPES:")

        for entity_type, info in self.classes.items():
            definition = info["definition"]
            examples = info["examples"]

            lines.append(
                f"- {entity_type}: {definition}. "
                f"Examples: {examples}"
            )

        lines.append("")
        lines.append("RELATIONSHIPS:")

        for relationship, info in self.relationships.items():
            lines.append(
                f"- {relationship}: "
                f"{info['source_type']} -> {info['target_type']}"
            )

        return "\n".join(lines)