"""
graph_data.json -> Neo4j Aura

Loads the normalized graph into Neo4j using batched writes
and retries transient cluster errors.

No LLM, PDF or extraction happens here.
"""

import json
import sys
import time

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, SessionExpired, TransientError

from config import GRAPH_FILE, NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD


# ============================================================
# SETTINGS
# ============================================================

BATCH_SIZE = 500
MAX_RETRIES = 8
RETRY_DELAY = 3


# ============================================================
# HELPERS
# ============================================================

def cypher_safe_label(value):
    return str(value).replace("`", "``")


def run_with_retry(session, query, **parameters):
    """
    Execute a Cypher query and retry transient Aura/cluster errors.
    """

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = session.run(query, **parameters)
            result.consume()
            return

        except (TransientError, ServiceUnavailable, SessionExpired) as exc:

            if attempt == MAX_RETRIES:
                raise

            delay = RETRY_DELAY * attempt

            print(
                f"Transient Neo4j error "
                f"(attempt {attempt}/{MAX_RETRIES}). "
                f"Retrying in {delay}s..."
            )
            print(f"  {exc}")

            time.sleep(delay)


def chunks(items, size):
    """
    Yield lists of at most `size` elements.
    """
    for i in range(0, len(items), size):
        yield items[i:i + size]


# ============================================================
# ENTITY LOADING
# ============================================================

ENTITY_QUERY = """
UNWIND $rows AS entity

MERGE (n:Entity {entity_id: entity.entity_id})

SET n.canonical_name = entity.canonical_name,
    n.entity_type = entity.entity_type,
    n.description = entity.description,
    n.aliases = entity.aliases,
    n.domains = entity.domains,
    n.properties_json = entity.properties_json
"""


def load_entities(session, entities):

    total = len(entities)

    print(f"\nLoading {total:,} entities...")

    for batch_number, batch in enumerate(
        chunks(entities, BATCH_SIZE),
        start=1,
    ):

        rows = []

        for entity in batch:

            rows.append({
                "entity_id": entity["entity_id"],
                "canonical_name": entity["canonical_name"],
                "entity_type": entity["entity_type"],
                "description": entity.get("description", ""),
                "aliases": entity.get("aliases", []),
                "domains": entity.get("domains", []),
                "properties_json": json.dumps(
                    entity.get("properties", {}),
                    ensure_ascii=False,
                ),
            })

        run_with_retry(
            session,
            ENTITY_QUERY,
            rows=rows,
        )

        processed = min(
            batch_number * BATCH_SIZE,
            total,
        )

        print(
            f"  Entities: {processed:,}/{total:,}"
        )


# ============================================================
# ENTITY PROVENANCE
# ============================================================

SOURCE_MENTION_QUERY = """
UNWIND $rows AS mention

MERGE (s:SourceMention {
    chunk_id: mention.chunk_id,
    entity_id: mention.entity_id
})

SET s.document = mention.document,
    s.document_file = mention.document_file,
    s.page = mention.page,
    s.clause = mention.clause,
    s.section_title = mention.section_title,
    s.evidence = mention.evidence

WITH s, mention

MATCH (n:Entity {
    entity_id: mention.entity_id
})

MERGE (n)-[:MENTIONED_IN]->(s)
"""


def load_source_mentions(session, entities):

    mentions = []

    for entity in entities:

        for mention in entity.get("source_mentions", []):

            mentions.append({
                "chunk_id": mention.get("chunk_id", ""),
                "entity_id": entity["entity_id"],
                "document": mention.get("document", ""),
                "document_file": mention.get("document_file", ""),
                "page": mention.get("page"),
                "clause": mention.get("clause", ""),
                "section_title": mention.get(
                    "section_title",
                    "",
                ),
                "evidence": mention.get(
                    "evidence",
                    "",
                ),
            })

    total = len(mentions)

    print(
        f"\nLoading {total:,} entity source mentions..."
    )

    if total == 0:
        print("  No entity source mentions found.")
        return

    for batch_number, batch in enumerate(
        chunks(mentions, BATCH_SIZE),
        start=1,
    ):

        run_with_retry(
            session,
            SOURCE_MENTION_QUERY,
            rows=batch,
        )

        processed = min(
            batch_number * BATCH_SIZE,
            total,
        )

        print(
            f"  Source mentions: "
            f"{processed:,}/{total:,}"
        )


# ============================================================
# RELATIONSHIPS
# ============================================================

def load_relationship_batch(
    session,
    relationship_type,
    relationships,
):
    """
    Load one relationship type at a time.

    Relationship types cannot be passed as Cypher parameters,
    so the validated relationship type is inserted into the query.
    """

    rtype = relationship_type.replace("`", "``")

    query = f"""
    UNWIND $rows AS rel

    MATCH (a:Entity {{
        entity_id: rel.source
    }})

    MATCH (b:Entity {{
        entity_id: rel.target
    }})

    MERGE (a)-[:`{rtype}`]->(b)
    """

    run_with_retry(
        session,
        query,
        rows=relationships,
    )


def load_relationships(session, relationships):

    total = len(relationships)

    print(
        f"\nLoading {total:,} relationships..."
    )

    if total == 0:
        print("  No relationships found.")
        return

    # Group by relationship type.
    grouped = {}

    for rel in relationships:

        rtype = rel["relationship"].upper()

        grouped.setdefault(
            rtype,
            [],
        ).append({
            "source": rel["source"],
            "target": rel["target"],
        })

    print(
        f"  Relationship types: {len(grouped)}"
    )

    processed = 0

    for rtype, rels in sorted(grouped.items()):

        print(
            f"  {rtype}: {len(rels):,}"
        )

        for batch in chunks(
            rels,
            BATCH_SIZE,
        ):

            load_relationship_batch(
                session,
                rtype,
                batch,
            )

            processed += len(batch)

            print(
                f"    Progress: "
                f"{processed:,}/{total:,}"
            )


# ============================================================
# RELATIONSHIP PROVENANCE
# ============================================================

def load_relationship_mentions(
    session,
    relationships,
):

    mentions = []

    for rel in relationships:

        for mention in rel.get(
            "source_mentions",
            [],
        ):

            mentions.append({
                "chunk_id": mention.get(
                    "chunk_id",
                    "",
                ),
                "source": rel["source"],
                "relationship": rel["relationship"].upper(),
                "target": rel["target"],
                "document": mention.get(
                    "document",
                    "",
                ),
                "document_file": mention.get(
                    "document_file",
                    "",
                ),
                "page": mention.get(
                    "page"
                ),
                "clause": mention.get(
                    "clause",
                    "",
                ),
                "section_title": mention.get(
                    "section_title",
                    "",
                ),
                "evidence": mention.get(
                    "evidence",
                    "",
                ),
            })

    total = len(mentions)

    print(
        f"\nLoading {total:,} relationship "
        f"source mentions..."
    )

    if total == 0:
        print(
            "  No relationship source mentions found."
        )
        return

    # Group by relationship type because the
    # relationship type is part of the Cypher.
    grouped = {}

    for mention in mentions:

        grouped.setdefault(
            mention["relationship"],
            [],
        ).append(mention)

    processed = 0

    for rtype, rel_mentions in sorted(
        grouped.items()
    ):

        safe_rtype = rtype.replace(
            "`",
            "``",
        )

        query = f"""
        UNWIND $rows AS mention

        MATCH (a:Entity {{
            entity_id: mention.source
        }})

        MATCH (b:Entity {{
            entity_id: mention.target
        }})

        MATCH (a)-[:`{safe_rtype}`]->(b)

        MERGE (s:RelationshipMention {{
            chunk_id: mention.chunk_id,
            source: mention.source,
            relationship: mention.relationship,
            target: mention.target
        }})

        SET s.document = mention.document,
            s.document_file = mention.document_file,
            s.page = mention.page,
            s.clause = mention.clause,
            s.section_title = mention.section_title,
            s.evidence = mention.evidence

        MERGE (a)-[:RELATIONSHIP_MENTION]->(s)
        MERGE (s)-[:RELATIONSHIP_TARGET]->(b)
        """

        for batch in chunks(
            rel_mentions,
            BATCH_SIZE,
        ):

            run_with_retry(
                session,
                query,
                rows=batch,
            )

            processed += len(batch)

            print(
                f"  Relationship mentions: "
                f"{processed:,}/{total:,}"
            )



def relationship_stage_complete(session, relationships):
    """Return True only when all expected relationship types/counts exist."""
    if not relationships:
        return True

    expected = {}
    for rel in relationships:
        rtype = rel["relationship"].upper()
        expected[rtype] = expected.get(rtype, 0) + 1

    result = session.run("""
        MATCH ()-[r]->()
        WHERE type(r) IN $types
        RETURN type(r) AS relationship_type, count(r) AS count
    """, types=list(expected.keys()))

    actual = {record["relationship_type"]: record["count"] for record in result}

    return all(actual.get(rtype, 0) >= count for rtype, count in expected.items())


def node_count(session, label):
    result = session.run(
        f"MATCH (n:`{label}`) RETURN count(n) AS count"
    )
    return result.single()["count"]

# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("Neo4j Aura Graph Loader")
    print("=" * 60)

    # --------------------------------------------------------
    # Validate configuration
    # --------------------------------------------------------

    if not GRAPH_FILE.exists():

        print(
            f"\nMissing graph file:\n"
            f"{GRAPH_FILE}"
        )

        print(
            "\nRun graph_loader.py first."
        )

        sys.exit(1)

    if not NEO4J_URI:

        print(
            "\nNEO4J_URI is not configured."
        )

        sys.exit(1)

    if not NEO4J_USERNAME:

        print(
            "\nNEO4J_USERNAME is not configured."
        )

        sys.exit(1)

    if not NEO4J_PASSWORD:

        print(
            "\nNEO4J_PASSWORD is not configured."
        )

        sys.exit(1)

    # --------------------------------------------------------
    # Load graph JSON
    # --------------------------------------------------------

    print(
        f"\nGraph file:\n{GRAPH_FILE}"
    )

    graph = json.loads(
        GRAPH_FILE.read_text(
            encoding="utf-8"
        )
    )

    entities = graph.get(
        "entities",
        [],
    )

    relationships = graph.get(
        "relationships",
        [],
    )

    print(
        f"\nGraph contents:"
        f"\n  Entities:      {len(entities):,}"
        f"\n  Relationships: {len(relationships):,}"
    )

    # --------------------------------------------------------
    # Connect to Aura
    # --------------------------------------------------------

    print(
        f"\nConnecting to:\n{NEO4J_URI}"
    )

    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(
            NEO4J_USERNAME,
            NEO4J_PASSWORD,
        ),
        max_connection_lifetime=3600,
    )

    try:

        driver.verify_connectivity()

        print(
            "\nNeo4j connection successful."
        )

        with driver.session() as session:

            # ------------------------------------------------
            # Constraint
            # ------------------------------------------------

            print(
                "\nChecking entity constraint..."
            )

            run_with_retry(
                session,
                """
                CREATE CONSTRAINT entity_id_unique
                IF NOT EXISTS
                FOR (n:Entity)
                REQUIRE n.entity_id IS UNIQUE
                """,
            )

            print(
                "Constraint ready."
            )

            # ------------------------------------------------
            # Entities
            # ------------------------------------------------

            existing_entities = node_count(session, "Entity")

            if existing_entities >= len(entities):
                print(
                    f"\nEntities already loaded ({existing_entities:,}). Skipping entity load."
                )
            else:
                load_entities(
                    session,
                    entities,
                )

            # ------------------------------------------------
            # Entity provenance
            # ------------------------------------------------

            expected_source_mentions = sum(
                len(entity.get("source_mentions", []))
                for entity in entities
            )
            existing_source_mentions = node_count(
                session,
                "SourceMention",
            )

            if existing_source_mentions >= expected_source_mentions:
                print(
                    f"Entity source mentions already loaded "
                    f"({existing_source_mentions:,}). Skipping source mentions."
                )
            else:
                load_source_mentions(
                    session,
                    entities,
                )

            # ------------------------------------------------
            # Relationships
            # ------------------------------------------------

            if relationship_stage_complete(session, relationships):
                print(
                    f"\nRelationships already loaded ({len(relationships):,}). "
                    f"Skipping relationship load."
                )
            else:
                load_relationships(
                    session,
                    relationships,
                )

            # ------------------------------------------------
            # Relationship provenance
            # ------------------------------------------------

            expected_relationship_mentions = sum(
                len(rel.get("source_mentions", []))
                for rel in relationships
            )
            existing_relationship_mentions = node_count(
                session,
                "RelationshipMention",
            )

            if existing_relationship_mentions >= expected_relationship_mentions:
                print(
                    f"Relationship source mentions already loaded "
                    f"({existing_relationship_mentions:,}). "
                    f"Skipping relationship mentions."
                )
            else:
                load_relationship_mentions(
                    session,
                    relationships,
                )

        print(
            "\n" + "=" * 60
        )
        print(
            "Neo4j Aura load completed successfully."
        )
        print(
            "=" * 60
        )

    except Exception as exc:

        print(
            "\n" + "=" * 60
        )
        print(
            "NEO4J LOAD FAILED"
        )
        print(
            "=" * 60
        )
        print(
            f"\n{type(exc).__name__}: {exc}"
        )

        sys.exit(1)

    finally:

        driver.close()


if __name__ == "__main__":
    main()