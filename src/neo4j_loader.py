"""
graph_data.json -> Neo4j

This is intentionally the ONLY file that talks to Neo4j.
No LLM, PDF or extraction happens here.
"""

import json
import sys

from neo4j import GraphDatabase

from config import GRAPH_FILE, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


def cypher_safe_label(value):
    # Entity types are controlled by the schema. Backticks are still escaped.
    return str(value).replace("`", "``")


def main():
    if not GRAPH_FILE.exists():
        print(f"Missing {GRAPH_FILE}. Build graph JSON first.")
        sys.exit(1)

    if not NEO4J_PASSWORD:
        print("Set NEO4J_PASSWORD before loading.")
        sys.exit(1)

    graph = json.loads(GRAPH_FILE.read_text(encoding="utf-8"))

    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, NEO4J_PASSWORD),
    )

    try:
        driver.verify_connectivity()

        with driver.session() as session:
            session.run("""
                CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
                FOR (n:Entity)
                REQUIRE n.entity_id IS UNIQUE
            """)

            # Entity nodes
            for entity in graph["entities"]:
                label = cypher_safe_label(entity["entity_type"])

                query = f"""
                MERGE (n:Entity:`{label}` {{entity_id: $entity_id}})
                SET n.canonical_name = $canonical_name,
                    n.entity_type = $entity_type,
                    n.description = $description,
                    n.aliases = $aliases,
                    n.domains = $domains,
                    n.properties_json = $properties_json
                """

                session.run(
                    query,
                    entity_id=entity["entity_id"],
                    canonical_name=entity["canonical_name"],
                    entity_type=entity["entity_type"],
                    description=entity.get("description", ""),
                    aliases=entity.get("aliases", []),
                    domains=entity.get("domains", []),
                    properties_json=json.dumps(
                        entity.get("properties", {}),
                        ensure_ascii=False,
                    ),
                )

                # Provenance nodes
                for mention in entity.get("source_mentions", []):
                    session.run("""
                        MERGE (s:SourceMention {
                            chunk_id: $chunk_id,
                            entity_id: $entity_id
                        })
                        SET s.document = $document,
                            s.document_file = $document_file,
                            s.page = $page,
                            s.clause = $clause,
                            s.section_title = $section_title,
                            s.evidence = $evidence
                        WITH s
                        MATCH (n:Entity {entity_id: $entity_id})
                        MERGE (n)-[:MENTIONED_IN]->(s)
                    """,
                        entity_id=entity["entity_id"],
                        **mention,
                    )

            # Relationships
            for rel in graph["relationships"]:
                # Relationship names come from the validated schema/model.
                # Neo4j relationship type cannot be parameterized, so quote it.
                rtype = rel["relationship"].replace("`", "``")

                query = f"""
                MATCH (a:Entity {{entity_id: $source}})
                MATCH (b:Entity {{entity_id: $target}})
                MERGE (a)-[r:`{rtype}`]->(b)
                """

                session.run(
                    query,
                    source=rel["source"],
                    target=rel["target"],
                )

                for mention in rel.get("source_mentions", []):
                    session.run(f"""
                        MATCH (a:Entity {{entity_id: $source}})
                        MATCH (b:Entity {{entity_id: $target}})
                        MERGE (a)-[r:`{rtype}`]->(b)
                        MERGE (s:RelationshipMention {{
                            chunk_id: $chunk_id,
                            source: $source,
                            relationship: $relationship,
                            target: $target
                        }})
                        SET s.document = $document,
                            s.document_file = $document_file,
                            s.page = $page,
                            s.clause = $clause,
                            s.section_title = $section_title,
                            s.evidence = $evidence
                        MERGE (r)-[:SUPPORTED_BY]->(s)
                    """,
                        source=rel["source"],
                        target=rel["target"],
                        relationship=rel["relationship"],
                        **mention,
                    )

        print("Neo4j load completed.")

    finally:
        driver.close()


if __name__ == "__main__":
    main()
