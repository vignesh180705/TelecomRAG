'''
from neo4j import GraphDatabase

from config import (
    NEO4J_URI,
    NEO4J_USERNAME,
    NEO4J_PASSWORD,
)


class Neo4jSchema:

    def __init__(self):
        self.driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )

    def close(self):
        self.driver.close()

    def create_constraints(self):

        queries = [

            # Entity identity
            """
            CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
            FOR (n:Entity)
            REQUIRE n.entity_id IS UNIQUE
            """,

            # Document identity
            """
            CREATE CONSTRAINT document_id_unique IF NOT EXISTS
            FOR (n:Document)
            REQUIRE n.document_id IS UNIQUE
            """,

            # Source mention identity
            """
            CREATE CONSTRAINT mention_id_unique IF NOT EXISTS
            FOR (n:SourceMention)
            REQUIRE n.mention_id IS UNIQUE
            """,
        ]

        with self.driver.session() as session:
            for query in queries:
                session.run(query)

        print("Neo4j constraints created.")

    def create_indexes(self):

        queries = [

            """
            CREATE INDEX entity_name_index IF NOT EXISTS
            FOR (n:Entity)
            ON (n.canonical_name)
            """,

            """
            CREATE INDEX entity_type_index IF NOT EXISTS
            FOR (n:Entity)
            ON (n.entity_type)
            """,

            """
            CREATE INDEX document_filename_index IF NOT EXISTS
            FOR (n:Document)
            ON (n.filename)
            """,
        ]

        with self.driver.session() as session:
            for query in queries:
                session.run(query)

        print("Neo4j indexes created.")


if __name__ == "__main__":

    schema = Neo4jSchema()

    try:
        schema.create_constraints()
        schema.create_indexes()
    finally:
        schema.close()

        
'''

import json
from pathlib import Path


class Ontology:
    """
    Loads the 3GPP ontology from 3gpp_schema.json.

    Expected structure:

    {
        "ontology": {
            "domains": [...],
            "classes": [...],
            "relationships": [...]
        },
        "entities": [...]
    }
    """

    def __init__(self, path):
        self.path = Path(path)

        if not self.path.exists():
            raise FileNotFoundError(
                f"Ontology file not found: {self.path.resolve()}"
            )

        with self.path.open("r", encoding="utf-8") as f:
            self.data = json.load(f)

        ontology = self.data.get("ontology", {})

        if not isinstance(ontology, dict):
            raise ValueError(
                f"'ontology' must be an object in {self.path}"
            )

        self.domains = ontology.get("domains", [])
        self.classes = ontology.get("classes", [])
        self.relationship_defs = ontology.get("relationships", [])

        self.entity_types = set()
        self.entity_defs = {}

        self.relationships = {}

        self._load_classes()
        self._load_relationships()

        if not self.entity_types:
            raise ValueError(
                f"No ontology entity types found in {self.path}"
            )

        if not self.relationships:
            raise ValueError(
                f"No ontology relationships found in {self.path}"
            )

    # ================================================================
    # CLASSES
    # ================================================================

    def _load_classes(self):
        for item in self.classes:

            if not isinstance(item, dict):
                continue

            entity_type = item.get("entity_type")

            if not entity_type:
                continue

            self.entity_types.add(entity_type)
            self.entity_defs[entity_type] = item

    # ================================================================
    # RELATIONSHIPS
    # ================================================================

    def _load_relationships(self):
        for item in self.relationship_defs:

            if not isinstance(item, dict):
                continue

            relationship = (
                item.get("relationship")
                or item.get("relationship_type")
                or item.get("name")
            )

            source_type = item.get("source_type")
            target_type = item.get("target_type")

            if not relationship:
                continue

            if not source_type:
                continue

            if not target_type:
                continue

            self.relationships[relationship] = (
                source_type,
                target_type,
            )

    # ================================================================
    # VALIDATION
    # ================================================================

    def valid_entity_type(self, entity_type):
        return entity_type in self.entity_types

    def valid_relationship(
        self,
        relationship,
        source_type=None,
        target_type=None,
    ):
        """
        Validate relationship name and, when supplied,
        source/target entity types.

        '*' in the ontology means any entity type.
        """

        if relationship not in self.relationships:
            return False

        expected_source, expected_target = self.relationships[
            relationship
        ]

        if (
            source_type is not None
            and expected_source != "*"
            and expected_source != source_type
        ):
            return False

        if (
            target_type is not None
            and expected_target != "*"
            and expected_target != target_type
        ):
            return False

        return True

    # ================================================================
    # GROK PROMPT
    # ================================================================

    def prompt_schema(self):
        """
        Produce a compact ontology representation for Grok.
        """

        lines = []

        lines.append("ALLOWED ENTITY TYPES")
        lines.append("====================")

        for entity_type in sorted(self.entity_types):

            definition = self.entity_defs.get(
                entity_type,
                {},
            )

            description = (
                definition.get("definition")
                or definition.get("description")
                or ""
            )

            examples = definition.get("examples", "")

            line = f"- {entity_type}"

            if description:
                line += f": {description}"

            if examples:
                line += f" | Examples: {examples}"

            lines.append(line)

        lines.append("")
        lines.append("ALLOWED RELATIONSHIPS")
        lines.append("======================")

        for relationship in sorted(self.relationships):

            source_type, target_type = self.relationships[
                relationship
            ]

            lines.append(
                f"- {source_type} "
                f"--{relationship}--> "
                f"{target_type}"
            )

        return "\n".join(lines)

    # ================================================================
    # REPORT
    # ================================================================

    def report(self):

        return {
            "ontology_file": str(
                self.path.resolve()
            ),
            "domain_count": len(self.domains),
            "entity_type_count": len(
                self.entity_types
            ),
            "relationship_count": len(
                self.relationships
            ),
            "entity_types": sorted(
                self.entity_types
            ),
            "relationships": {
                relationship: {
                    "source_type": source_type,
                    "target_type": target_type,
                }
                for relationship, (
                    source_type,
                    target_type,
                ) in sorted(
                    self.relationships.items()
                )
            },
        }
        
