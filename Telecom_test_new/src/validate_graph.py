"""Basic Neo4j graph validation queries."""
from config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
from graph_store import Neo4jGraphStore


def run():
    graph = Neo4jGraphStore(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)
    queries = {
        "entities": "MATCH (n:Entity) RETURN count(n) AS count",
        "documents": "MATCH (n:Document) RETURN count(n) AS count",
        "chunks": "MATCH (n:Chunk) RETURN count(n) AS count",
        "relationships": "MATCH (:Entity)-[r]->(:Entity) RETURN count(r) AS count",
        "relationship_types": "MATCH (:Entity)-[r]->(:Entity) RETURN type(r) AS type, count(r) AS count ORDER BY count DESC",
        "orphan_entities": "MATCH (n:Entity) WHERE NOT (n)--() RETURN count(n) AS count",
    }
    try:
        with graph.driver.session() as session:
            for name, query in queries.items():
                print(f"\n{name}")
                for row in session.run(query):
                    print(dict(row))
    finally:
        graph.close()


if __name__ == "__main__":
    run()
