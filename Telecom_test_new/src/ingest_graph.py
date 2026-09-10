import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase


# ============================================================
# Configuration
# ============================================================

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "f8c380ca")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "f8c380ca")


# ============================================================
# Allowed ontology relationship types
# ============================================================

RELATIONSHIP_TYPES = {
    "CONTAINS_SECTION",
    "CONTAINS_CHUNK",
    "DEFINED_IN",
    "COMMUNICATES_WITH",
    "CONNECTS_TO",
    "USES_INTERFACE",
    "USES_PROTOCOL",
    "IMPLEMENTS",
    "PROVIDES_SERVICE",
    "EXPOSES",
    "SUPPORTS",
    "HAS_CAPABILITY",
    "HAS_PARAMETER",
    "HAS_METRIC",
    "USES_MESSAGE",
    "CONTAINS_INFORMATION_ELEMENT",
    "INVOLVES",
    "INITIATES",
    "ESTABLISHES",
    "CONTROLS",
    "CONFIGURES",
    "MONITORS",
    "REPORTS",
    "APPLIES_TO",
    "DEPENDS_ON",
    "TRIGGERS",
    "PRODUCES",
    "CONSUMES",
    "DEPLOYED_ON",
    "REQUIRES_RESOURCE",
    "HAS_DEPLOYMENT_ITEM",
    "SECURED_BY",
    "MITIGATES",
    "HAS_INDICATOR",
    "HAS_LIFECYCLE_STAGE",
    "MODULE_CONTAINS",
    "CHILD_OF",
    "HAS_TYPE",
    "HAS_ENUM_VALUE",
    "AUGMENTS",
    "USES_GROUPING",
    "IMPORTS",
    "TRACEABLE_TO",
}


# ============================================================
# Utility functions
# ============================================================

def load_json(path):
    """
    Load JSON from disk.
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def safe_list(value):
    """
    Ensure a value is always represented as a list.
    """
    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]


def safe_string(value):
    """
    Ensure a value is always represented as a string.
    """
    if value is None:
        return ""

    return str(value)


# ============================================================
# Neo4j Ingester
# ============================================================

class Neo4jIngester:

    def __init__(
        self,
        uri=NEO4J_URI,
        username=NEO4J_USERNAME,
        password=NEO4J_PASSWORD,
        database=NEO4J_DATABASE,
    ):
        if not uri:
            raise ValueError("NEO4J_URI is not configured.")

        if not username:
            raise ValueError("NEO4J_USERNAME is not configured.")

        if not password:
            raise ValueError("NEO4J_PASSWORD is not configured.")

        self.uri = uri
        self.username = username
        self.password = password
        self.database = database

        self.driver = GraphDatabase.driver(
            self.uri,
            auth=(self.username, self.password),
        )

    # ========================================================
    # Connection
    # ========================================================

    def verify_connection(self):
        """
        Verify that Neo4j is reachable and that the configured
        database actually exists.

        Important:
        Neo4j Aura may not have a database called `neo4j`.
        Therefore we explicitly use self.database.
        """

        self.driver.verify_connectivity()

        with self.driver.session(database=self.database) as session:
            session.run("RETURN 1").consume()

        print(
            f"Connected to Neo4j database '{self.database}'."
        )

    def close(self):
        """
        Close the Neo4j driver.
        """
        self.driver.close()

    # ========================================================
    # Constraints
    # ========================================================

    def create_constraints(self):
        """
        Create uniqueness constraints for the main node types.

        IMPORTANT:
        The session explicitly specifies the configured database.
        """

        with self.driver.session(database=self.database) as session:

            session.run(
                """
                CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
                FOR (e:Entity)
                REQUIRE e.entity_id IS UNIQUE
                """
            )

            session.run(
                """
                CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS
                FOR (c:Chunk)
                REQUIRE c.chunk_id IS UNIQUE
                """
            )

            session.run(
                """
                CREATE CONSTRAINT document_source_unique IF NOT EXISTS
                FOR (d:Document)
                REQUIRE d.source IS UNIQUE
                """
            )

        print("Constraints created.")

    # ========================================================
    # Entity
    # ========================================================

    @staticmethod
    def create_entity(tx, entity):
        """
        Create or update a canonical Entity node.
        """

        entity_id = safe_string(entity.get("entity_id"))
        canonical_name = safe_string(
            entity.get("canonical_name")
            or entity.get("name")
        )

        aliases = safe_list(entity.get("aliases"))
        properties = entity.get("properties") or {}

        description = safe_string(
            entity.get("description")
        )

        confidence = entity.get("confidence")

        entity_type = safe_string(
            entity.get("entity_type")
            or entity.get("type")
        )

        status = safe_string(
            entity.get("status")
        )

        extraction_methods = safe_list(
            entity.get("extraction_methods")
        )

        original_entity_ids = safe_list(
            entity.get("original_entity_ids")
        )

        tx.run(
            """
            MERGE (e:Entity {entity_id: $entity_id})

            SET
                e.name = $name,
                e.entity_type = $entity_type,
                e.description = $description,
                e.aliases = $aliases,
                e.confidence = $confidence,
                e.status = $status,
                e.extraction_methods = $extraction_methods,
                e.original_entity_ids = $original_entity_ids,
                e.properties_json = $properties_json
            """,
            entity_id=entity_id,
            name=canonical_name,
            entity_type=entity_type,
            description=description,
            aliases=aliases,
            confidence=confidence,
            status=status,
            extraction_methods=extraction_methods,
            original_entity_ids=original_entity_ids,
            properties_json=json.dumps(
                properties,
                ensure_ascii=False,
            ),
        )

    # ========================================================
    # Document
    # ========================================================

    @staticmethod
    def create_document(tx, source):
        """
        Create or update a Document node.
        """

        source = safe_string(source)

        tx.run(
            """
            MERGE (d:Document {source: $source})
            """,
            source=source,
        )

    # ========================================================
    # Chunk
    # ========================================================

    @staticmethod
    def create_chunk(tx, evidence):
        """
        Create or update a Chunk node and connect it to
        its source Document.
        """

        chunk_id = safe_string(
            evidence.get("chunk_id")
        )

        source = safe_string(
            evidence.get("source")
        )

        text = safe_string(
            evidence.get("text")
        )

        page = evidence.get("page")

        tx.run(
            """
            MERGE (c:Chunk {chunk_id: $chunk_id})

            SET
                c.text = $text,
                c.page = $page,
                c.source = $source

            WITH c

            MERGE (d:Document {source: $source})

            MERGE (d)-[:CONTAINS_CHUNK]->(c)
            """,
            chunk_id=chunk_id,
            text=text,
            page=page,
            source=source,
        )

    # ========================================================
    # Entity -> Chunk provenance
    # ========================================================

    @staticmethod
    def connect_entity_to_chunk(
        tx,
        entity_id,
        chunk_id,
    ):
        """
        Connect an Entity to a Chunk where the entity
        was mentioned.
        """

        tx.run(
            """
            MATCH (e:Entity {entity_id: $entity_id})
            MATCH (c:Chunk {chunk_id: $chunk_id})

            MERGE (e)-[:MENTIONED_IN]->(c)
            """,
            entity_id=entity_id,
            chunk_id=chunk_id,
        )

    # ========================================================
    # Semantic Relationship
    # ========================================================

    @staticmethod
    def create_relationship(
        tx,
        relationship,
    ):
        """
        Create a semantic relationship between two canonical
        entities.

        Example:

        (:Entity {entity_id: "network_entity:smo"})
            -[:DEPENDS_ON]->
        (:Entity {entity_id: "deployment_descriptor:deploymentdescriptor"})
        """

        source_entity_id = safe_string(
            relationship.get("source_entity_id")
        )

        target_entity_id = safe_string(
            relationship.get("target_entity_id")
        )

        relationship_type = safe_string(
            relationship.get("relationship_type")
        )

        confidence = relationship.get("confidence")

        # ----------------------------------------------------
        # Validate relationship type
        # ----------------------------------------------------

        if relationship_type not in RELATIONSHIP_TYPES:
            raise ValueError(
                f"Unknown relationship type: "
                f"{relationship_type}"
            )

        # ----------------------------------------------------
        # Create relationship dynamically
        # ----------------------------------------------------
        #
        # Neo4j relationship types cannot be parameterized:
        #
        # [:${relationship_type}]
        #
        # Therefore the validated ontology value is inserted
        # into the Cypher query.
        # ----------------------------------------------------

        query = f"""
            MATCH (source:Entity {{
                entity_id: $source_entity_id
            }})

            MATCH (target:Entity {{
                entity_id: $target_entity_id
            }})

            MERGE (source)-[r:{relationship_type}]->(target)

            SET
                r.confidence = $confidence
        """

        tx.run(
            query,
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            confidence=confidence,
        )

    # ========================================================
    # Relationship Evidence
    # ========================================================

    @staticmethod
    def add_relationship_evidence(
        tx,
        relationship,
    ):
        """
        Store evidence from the source document directly
        on the semantic relationship.

        The first evidence item is stored as the primary
        evidence.

        All evidence chunks are also connected through
        provenance.
        """

        source_entity_id = safe_string(
            relationship.get("source_entity_id")
        )

        target_entity_id = safe_string(
            relationship.get("target_entity_id")
        )

        relationship_type = safe_string(
            relationship.get("relationship_type")
        )

        confidence = relationship.get("confidence")

        evidence_list = safe_list(
            relationship.get("evidence")
        )

        if relationship_type not in RELATIONSHIP_TYPES:
            raise ValueError(
                f"Unknown relationship type: "
                f"{relationship_type}"
            )

        # ----------------------------------------------------
        # Primary evidence
        # ----------------------------------------------------

        primary_evidence = (
            evidence_list[0]
            if evidence_list
            else {}
        )

        evidence_text = safe_string(
            primary_evidence.get("text")
        )

        evidence_source = safe_string(
            primary_evidence.get("source")
        )

        evidence_page = primary_evidence.get("page")

        evidence_chunk_id = safe_string(
            primary_evidence.get("chunk_id")
        )

        query = f"""
            MATCH (source:Entity {{
                entity_id: $source_entity_id
            }})

            MATCH (target:Entity {{
                entity_id: $target_entity_id
            }})

            MERGE (source)-[r:{relationship_type}]->(target)

            SET
                r.confidence = $confidence,
                r.evidence = $evidence_text,
                r.source = $evidence_source,
                r.page = $evidence_page,
                r.chunk_id = $evidence_chunk_id
        """

        tx.run(
            query,
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            confidence=confidence,
            evidence_text=evidence_text,
            evidence_source=evidence_source,
            evidence_page=evidence_page,
            evidence_chunk_id=evidence_chunk_id,
        )

        # ----------------------------------------------------
        # Connect all evidence chunks
        # ----------------------------------------------------

        for evidence in evidence_list:

            chunk_id = safe_string(
                evidence.get("chunk_id")
            )

            if not chunk_id:
                continue

            tx.run(
                f"""
                MATCH (source:Entity {{
                    entity_id: $source_entity_id
                }})

                MATCH (target:Entity {{
                    entity_id: $target_entity_id
                }})

                MATCH (c:Chunk {{
                    chunk_id: $chunk_id
                }})

                MERGE (source)-[:MENTIONED_IN]->(c)

                MERGE (target)-[:MENTIONED_IN]->(c)
                """,
                source_entity_id=source_entity_id,
                target_entity_id=target_entity_id,
                chunk_id=chunk_id,
            )

    # ========================================================
    # Ingestion
    # ========================================================

    def ingest(
        self,
        entity_registry_path,
        relationship_registry_path,
    ):
        """
        Ingest:

        1. Canonical entities
        2. Documents
        3. Evidence chunks
        4. Entity -> Chunk provenance
        5. Semantic relationships
        6. Relationship evidence
        """

        print()
        print("=" * 60)
        print("Loading registries")
        print("=" * 60)

        entity_data = load_json(
            entity_registry_path
        )

        relationship_data = load_json(
            relationship_registry_path
        )

        # ----------------------------------------------------
        # Entity registry
        # ----------------------------------------------------

        if isinstance(entity_data, dict):
            entities = entity_data.get(
                "entities",
                []
            )
        else:
            entities = entity_data

        # ----------------------------------------------------
        # Relationship registry
        # ----------------------------------------------------

        if isinstance(relationship_data, dict):
            relationships = relationship_data.get(
                "relationships",
                []
            )
        else:
            relationships = relationship_data

        print(
            f"Entities loaded: {len(entities)}"
        )

        print(
            f"Relationships loaded: "
            f"{len(relationships)}"
        )

        # ====================================================
        # 1. Entities
        # ====================================================

        print()
        print("=" * 60)
        print("Ingesting entities")
        print("=" * 60)

        with self.driver.session(
            database=self.database
        ) as session:

            for entity in entities:

                session.execute_write(
                    self.create_entity,
                    entity,
                )

        print(
            f"Ingested {len(entities)} entities."
        )

        # ====================================================
        # 2. Documents + Chunks
        # ====================================================

        print()
        print("=" * 60)
        print("Ingesting evidence documents and chunks")
        print("=" * 60)

        unique_chunks = {}

        # ----------------------------------------------------
        # Gather all evidence chunks from relationships
        # ----------------------------------------------------

        for relationship in relationships:

            evidence_list = safe_list(
                relationship.get("evidence")
            )

            for evidence in evidence_list:

                chunk_id = safe_string(
                    evidence.get("chunk_id")
                )

                if not chunk_id:
                    continue

                unique_chunks[chunk_id] = evidence

        # ----------------------------------------------------
        # Create documents and chunks
        # ----------------------------------------------------

        with self.driver.session(
            database=self.database
        ) as session:

            for evidence in unique_chunks.values():

                session.execute_write(
                    self.create_chunk,
                    evidence,
                )

        print(
            f"Ingested {len(unique_chunks)} evidence chunks."
        )

        # ====================================================
        # 3. Entity -> Chunk provenance
        # ====================================================

        print()
        print("=" * 60)
        print("Creating entity provenance")
        print("=" * 60)

        provenance_count = 0

        with self.driver.session(
            database=self.database
        ) as session:

            for relationship in relationships:

                source_entity_id = safe_string(
                    relationship.get(
                        "source_entity_id"
                    )
                )

                target_entity_id = safe_string(
                    relationship.get(
                        "target_entity_id"
                    )
                )

                evidence_list = safe_list(
                    relationship.get("evidence")
                )

                for evidence in evidence_list:

                    chunk_id = safe_string(
                        evidence.get("chunk_id")
                    )

                    if not chunk_id:
                        continue

                    if source_entity_id:

                        session.execute_write(
                            self.connect_entity_to_chunk,
                            source_entity_id,
                            chunk_id,
                        )

                        provenance_count += 1

                    if target_entity_id:

                        session.execute_write(
                            self.connect_entity_to_chunk,
                            target_entity_id,
                            chunk_id,
                        )

                        provenance_count += 1

        print(
            f"Created {provenance_count} "
            f"entity-to-chunk provenance links."
        )

        # ====================================================
        # 4. Semantic relationships
        # ====================================================

        print()
        print("=" * 60)
        print("Creating semantic relationships")
        print("=" * 60)

        relationship_count = 0

        with self.driver.session(
            database=self.database
        ) as session:

            for relationship in relationships:

                session.execute_write(
                    self.create_relationship,
                    relationship,
                )

                session.execute_write(
                    self.add_relationship_evidence,
                    relationship,
                )

                relationship_count += 1

        print(
            f"Ingested {relationship_count} "
            f"semantic relationships."
        )

        # ====================================================
        # Summary
        # ====================================================

        print()
        print("=" * 60)
        print("INGESTION COMPLETE")
        print("=" * 60)

        print(
            f"Entities:       {len(entities)}"
        )

        print(
            f"Relationships:  {relationship_count}"
        )

        print(
            f"Chunks:         {len(unique_chunks)}"
        )

        print(
            f"Database:       {self.database}"
        )

        print("=" * 60)


# ============================================================
# CLI
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="Ingest TelecomRAG property graph into Neo4j."
    )

    parser.add_argument(
        "--entity-registry",
        default="output/entity_registry_v4_canonical.json",
        help="Path to canonical entity registry JSON.",
    )

    parser.add_argument(
        "--relationship-registry",
        default="output/relationship_registry_v2_source_grounded.json",
        help="Path to source-grounded relationship registry JSON.",
    )

    args = parser.parse_args()

    # --------------------------------------------------------
    # Create ingester
    # --------------------------------------------------------

    ingestor = Neo4jIngester()

    try:

        # ----------------------------------------------------
        # Connection
        # ----------------------------------------------------

        ingestor.verify_connection()

        # ----------------------------------------------------
        # Constraints
        # ----------------------------------------------------

        print("Creating constraints...")

        ingestor.create_constraints()

        # ----------------------------------------------------
        # Ingest
        # ----------------------------------------------------

        ingestor.ingest(
            entity_registry_path=args.entity_registry,
            relationship_registry_path=args.relationship_registry,
        )

    finally:

        ingestor.close()


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    main()