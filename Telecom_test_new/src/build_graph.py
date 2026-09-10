"""Load canonical entities, chunks, and validated relationships into Neo4j."""
import argparse
import json
from pathlib import Path

try:
    from config import (
        CHUNKS_PATH, ENTITY_REGISTRY_PATH, RELATIONSHIP_REGISTRY_PATH,
        NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD,
    )
    from entity_registry import load_entities
    from graph_store import Neo4jGraphStore
except ImportError:
    from .config import CHUNKS_PATH, ENTITY_REGISTRY_PATH, RELATIONSHIP_REGISTRY_PATH, NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
    from .entity_registry import load_entities
    from .graph_store import Neo4jGraphStore


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", default=str(CHUNKS_PATH))
    parser.add_argument("--entities", default=str(ENTITY_REGISTRY_PATH))
    parser.add_argument("--relationships", default=str(RELATIONSHIP_REGISTRY_PATH))
    args = parser.parse_args()

    chunks = json.loads(Path(args.chunks).read_text(encoding="utf-8"))
    entities = load_entities(args.entities)
    rel_payload = json.loads(Path(args.relationships).read_text(encoding="utf-8"))
    relationships = rel_payload["relationship_instances"]

    graph = Neo4jGraphStore(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)
    try:
        graph.verify()
        graph.create_constraints()
        for entity in entities:
            graph.upsert_entity(entity)
        for chunk in chunks:
            graph.upsert_chunk(chunk)
        for relationship in relationships:
            graph.upsert_relationship(relationship)
    finally:
        graph.close()

    print(f"Loaded {len(entities)} entities, {len(chunks)} chunks, {len(relationships)} relationships")


if __name__ == "__main__":
    main()
