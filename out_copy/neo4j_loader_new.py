"""
Load graph_data.json + SourceMention embeddings into Neo4j Aura.

Input:
    graph_data.json
    source_mention_embeddings.json

Loads:
    Entity
    SourceMention
    semantic relationships
    RelationshipMention provenance

Adds:
    SourceMention.embedding
    Neo4j vector index
"""

import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

from neo4j import (
    GraphDatabase,
    exceptions as neo4j_exceptions,
)

from config import GRAPH_FILE
from config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE

# ============================================================
# CONFIG
# ============================================================

BATCH_SIZE = 500
MAX_RETRIES = 8
RETRY_DELAY = 3

VECTOR_SIMILARITY = "cosine"
VECTOR_INDEX_NAME = "chunk_embedding_index"

EMBEDDING_FILE = GRAPH_FILE.with_name(
    "chunk_embeddings.json"
)
# ============================================================
# NEO4J ENV
# ============================================================



# ============================================================
# RETRY
# ============================================================

RETRYABLE_ERRORS = (
    neo4j_exceptions.TransientError,
    neo4j_exceptions.ServiceUnavailable,
    neo4j_exceptions.SessionExpired,
)


def run_with_retry(session, query, parameters=None):

    parameters = parameters or {}

    for attempt in range(1, MAX_RETRIES + 1):

        try:

            return session.run(
                query,
                parameters
            ).consume()

        except RETRYABLE_ERRORS as e:

            print(
                f"Transient Neo4j error "
                f"(attempt {attempt}/{MAX_RETRIES}): "
                f"{e}"
            )

            if attempt == MAX_RETRIES:
                raise

            time.sleep(
                RETRY_DELAY * attempt
            )


# ============================================================
# BATCH HELPER
# ============================================================

def batches(items, size):

    for i in range(0, len(items), size):
        yield items[i:i + size]


# ============================================================
# LOAD JSON
# ============================================================

def load_json_files():

    if not GRAPH_FILE.exists():
        print(f"Missing graph file: {GRAPH_FILE}")
        sys.exit(1)

    if not EMBEDDING_FILE.exists():
        print(
            f"Missing embedding file: "
            f"{EMBEDDING_FILE}"
        )
        print(
            "Run embed_graph.py first."
        )
        sys.exit(1)

    with open(
        GRAPH_FILE,
        "r",
        encoding="utf-8"
    ) as f:
        graph = json.load(f)

    with open(
        EMBEDDING_FILE,
        "r",
        encoding="utf-8"
    ) as f:
        embedding_data = json.load(f)

    return graph, embedding_data


# ============================================================
# ENTITY LOADER
# ============================================================

ENTITY_QUERY = """
UNWIND $rows AS entity

MERGE (n:Entity {
    entity_id: entity.entity_id
})

SET n.canonical_name = entity.canonical_name,
    n.entity_type = entity.entity_type,
    n.description = entity.description,
    n.aliases = entity.aliases,
    n.domains = entity.domains,
    n.properties_json = entity.properties_json
"""


def prepare_entities(graph):

    rows = []

    for entity in graph.get("entities", []):

        rows.append({
            "entity_id": entity["entity_id"],
            "canonical_name": entity.get(
                "canonical_name",
                ""
            ),
            "entity_type": entity.get(
                "entity_type",
                ""
            ),
            "description": entity.get(
                "description",
                ""
            ),
            "aliases": entity.get(
                "aliases",
                []
            ),
            "domains": entity.get(
                "domains",
                []
            ),
            "properties_json": json.dumps(
                entity.get("properties", {}),
                ensure_ascii=False
            ),
        })

    return rows


def load_entities(driver, entities):

    print()
    print("Loading Entity nodes...")

    with driver.session(
        database=NEO4J_DATABASE
    ) as session:

        for batch in batches(
            entities,
            BATCH_SIZE
        ):

            run_with_retry(
                session,
                ENTITY_QUERY,
                {"rows": batch}
            )

    print(
        f"Loaded {len(entities)} entities."
    )

# ============================================================
# CHUNK
# ============================================================

CHUNK_QUERY = """
UNWIND $rows AS chunk

MERGE (c:Chunk {
    chunk_id: chunk.chunk_id
})

SET c.document = chunk.document,
    c.page = chunk.page,
    c.clause = chunk.clause,
    c.section_title = chunk.section_title,
    c.text = chunk.text,
    c.embedding = chunk.embedding
"""


def prepare_chunks(embedding_data):

    rows = []

    embedding_store = embedding_data.get(
        "embeddings",
        {}
    )

    for chunk_id, chunk in embedding_store.items():

        rows.append({
            "chunk_id": chunk["chunk_id"],
            "document": chunk.get(
                "document",
                ""
            ),
            "page": chunk.get(
                "page",
                ""
            ),
            "clause": chunk.get(
                "clause",
                ""
            ),
            "section_title": chunk.get(
                "section_title",
                ""
            ),
            "text": chunk.get(
                "text",
                ""
            ),
            "embedding": chunk["embedding"],
        })

    return rows


def load_chunks(
    driver,
    chunks
):

    print()
    print("Loading Chunk nodes...")

    with driver.session(
        database=NEO4J_DATABASE
    ) as session:

        for batch in batches(
            chunks,
            BATCH_SIZE
        ):

            run_with_retry(
                session,
                CHUNK_QUERY,
                {"rows": batch}
            )

    print(
        f"Loaded {len(chunks)} Chunk nodes."
    )

# ============================================================
# SOURCE MENTION
# ============================================================

SOURCE_MENTION_QUERY = """
UNWIND $rows AS mention

MERGE (s:SourceMention {
    chunk_id: mention.chunk_id,
    entity_id: mention.entity_id
})

SET s.document = mention.document,
    s.page = mention.page,
    s.clause = mention.clause,
    s.section_title = mention.section_title,
    s.evidence = mention.evidence,
    s.embedding = mention.embedding

WITH s, mention

MATCH (n:Entity {
    entity_id: mention.entity_id
})

MERGE (n)-[:MENTIONED_IN]->(s)
"""


def make_embedding_key(
    entity_id,
    chunk_id
):

    return f"{entity_id}::{chunk_id}"


def prepare_source_mentions(
    graph,
    embedding_data
):

    embedding_store = embedding_data.get(
        "embeddings",
        {}
    )

    rows = []

    missing_embeddings = 0

    for entity in graph.get("entities", []):

        entity_id = entity.get("entity_id")

        if not entity_id:
            continue

        for mention in entity.get(
            "source_mentions",
            []
        ):

            chunk_id = mention.get(
                "chunk_id"
            )

            if not chunk_id:
                continue

            key = make_embedding_key(
                entity_id,
                chunk_id
            )

            embedding_record = (
                embedding_store.get(key)
            )

            if not embedding_record:

                missing_embeddings += 1
                continue

            rows.append({
                "chunk_id": chunk_id,
                "entity_id": entity_id,
                "document": mention.get(
                    "document",
                    ""
                ),
                "page": mention.get(
                    "page",
                    ""
                ),
                "clause": mention.get(
                    "clause",
                    ""
                ),
                "section_title": mention.get(
                    "section_title",
                    ""
                ),
                "evidence": mention.get(
                    "evidence",
                    ""
                ),
                "embedding": embedding_record[
                    "embedding"
                ],
            })

    if missing_embeddings:
        print(
            f"WARNING: {missing_embeddings} "
            f"source mentions have no embedding."
        )

    return rows


def load_source_mentions(
    driver,
    source_mentions
):

    print()
    print("Loading SourceMention nodes...")

    with driver.session(
        database=NEO4J_DATABASE
    ) as session:

        for batch in batches(
            source_mentions,
            BATCH_SIZE
        ):

            run_with_retry(
                session,
                SOURCE_MENTION_QUERY,
                {"rows": batch}
            )

    print(
        f"Loaded {len(source_mentions)} "
        f"SourceMention nodes."
    )


# ============================================================
# RELATIONSHIPS
# ============================================================

def clean_relationship_type(value):

    value = str(value).strip().upper()

    cleaned = ""

    for char in value:

        if char.isalnum() or char == "_":
            cleaned += char
        else:
            cleaned += "_"

    return cleaned.strip("_") or "RELATED_TO"


def load_relationships(
    driver,
    relationships
):

    print()
    print("Loading semantic relationships...")

    grouped = defaultdict(list)

    for rel in relationships:

        relationship_type = clean_relationship_type(
            rel.get(
                "relationship",
                "RELATED_TO"
            )
        )

        grouped[
            relationship_type
        ].append(rel)

    total_loaded = 0

    with driver.session(
        database=NEO4J_DATABASE
    ) as session:

        for relationship_type, rels in grouped.items():

            query = f"""
            UNWIND $rows AS rel

            MATCH (a:Entity {{
                entity_id: rel.source
            }})

            MATCH (b:Entity {{
                entity_id: rel.target
            }})

            MERGE (a)-[:`{relationship_type}`]->(b)
            """

            for batch in batches(
                rels,
                BATCH_SIZE
            ):

                rows = [
                    {
                        "source": r["source"],
                        "target": r["target"],
                    }
                    for r in batch
                ]

                run_with_retry(
                    session,
                    query,
                    {"rows": rows}
                )

                total_loaded += len(rows)

    print(
        f"Loaded {total_loaded} "
        f"semantic relationships."
    )
# ============================================================
# CHUNK → ENTITY
# ============================================================

CHUNK_ENTITY_QUERY = """
UNWIND $rows AS row

MATCH (c:Chunk {
    chunk_id: row.chunk_id
})

MATCH (e:Entity {
    entity_id: row.entity_id
})

MERGE (c)-[:MENTIONS]->(e)
"""


def prepare_chunk_entity_links(graph):

    rows = []

    for entity in graph.get(
        "entities",
        []
    ):

        entity_id = entity.get(
            "entity_id"
        )

        if not entity_id:
            continue

        for mention in entity.get(
            "source_mentions",
            []
        ):

            chunk_id = mention.get(
                "chunk_id"
            )

            if not chunk_id:
                continue

            rows.append({
                "chunk_id": chunk_id,
                "entity_id": entity_id,
            })

    # Remove duplicates
    unique = {
        (
            row["chunk_id"],
            row["entity_id"]
        ): row
        for row in rows
    }

    return list(
        unique.values()
    )


def load_chunk_entity_links(
    driver,
    links
):

    print()
    print(
        "Loading Chunk → Entity links..."
    )

    with driver.session(
        database=NEO4J_DATABASE
    ) as session:

        for batch in batches(
            links,
            BATCH_SIZE
        ):

            run_with_retry(
                session,
                CHUNK_ENTITY_QUERY,
                {"rows": batch}
            )

    print(
        f"Loaded {len(links)} "
        f"Chunk → Entity links."
    )

# ============================================================
# RELATIONSHIP PROVENANCE
# ============================================================

RELATIONSHIP_MENTION_QUERY = """
UNWIND $rows AS rel

MATCH (a:Entity {
    entity_id: rel.source
})

MATCH (b:Entity {
    entity_id: rel.target
})

MERGE (s:RelationshipMention {
    mention_key: rel.mention_key
})

SET s.document = rel.document,
    s.page = rel.page,
    s.clause = rel.clause,
    s.section_title = rel.section_title,
    s.evidence = rel.evidence

MERGE (a)-[:RELATIONSHIP_MENTION]->(s)

MERGE (s)-[:RELATIONSHIP_TARGET]->(b)
"""


def prepare_relationship_mentions(
    relationships
):

    rows = []

    for index, rel in enumerate(
        relationships
    ):

        provenance_list = rel.get(
            "source_mentions",
            []
        )

        for p_index, provenance in enumerate(
            provenance_list
        ):

            rows.append({
                "mention_key": (
                    f"{rel['source']}|"
                    f"{rel.get('relationship', '')}|"
                    f"{rel['target']}|"
                    f"{index}|"
                    f"{p_index}"
                ),
                "source": rel["source"],
                "target": rel["target"],
                "document": provenance.get(
                    "document",
                    ""
                ),
                "page": provenance.get(
                    "page",
                    ""
                ),
                "clause": provenance.get(
                    "clause",
                    ""
                ),
                "section_title": provenance.get(
                    "section_title",
                    ""
                ),
                "evidence": provenance.get(
                    "evidence",
                    ""
                ),
            })

    return rows


def load_relationship_mentions(
    driver,
    mentions
):

    if not mentions:
        print(
            "No RelationshipMention nodes."
        )
        return

    print()
    print(
        "Loading RelationshipMention nodes..."
    )

    with driver.session(
        database=NEO4J_DATABASE
    ) as session:

        for batch in batches(
            mentions,
            BATCH_SIZE
        ):

            run_with_retry(
                session,
                RELATIONSHIP_MENTION_QUERY,
                {"rows": batch}
            )

    print(
        f"Loaded {len(mentions)} "
        f"RelationshipMention nodes."
    )


# ============================================================
# VECTOR INDEX
# ============================================================

def create_vector_index(
    driver,
    dimensions
):

    print()
    print(
        f"Creating/checking vector index "
        f"({dimensions} dimensions)..."
    )

    query = f"""
    CREATE VECTOR INDEX {VECTOR_INDEX_NAME}
    IF NOT EXISTS
    FOR (c:Chunk)
    ON c.embedding
    OPTIONS {{
        indexConfig: {{
            `vector.dimensions`: $dimensions,
            `vector.similarity_function`: '{VECTOR_SIMILARITY}'
        }}
    }}
    """

    with driver.session(
        database=NEO4J_DATABASE
    ) as session:

        run_with_retry(
            session,
            query,
            {
                "dimensions": dimensions
            }
        )

    print(
        f"Vector index ready: "
        f"{VECTOR_INDEX_NAME}"
    )


# ============================================================
# VALIDATION
# ============================================================

def print_counts(
    driver
):

    query = """
    MATCH (n)
    RETURN labels(n) AS labels,
           count(n) AS count
    ORDER BY labels
    """

    print()
    print("=" * 70)
    print("NEO4J NODE COUNTS")
    print("=" * 70)

    with driver.session(
        database=NEO4J_DATABASE
    ) as session:

        result = session.run(query)

        for record in result:

            print(
                f"{record['labels']}: "
                f"{record['count']}"
            )


def check_vector_index(
    driver
):

    query = """
    SHOW VECTOR INDEXES
    """

    print()
    print("=" * 70)
    print("VECTOR INDEXES")
    print("=" * 70)

    with driver.session(
        database=NEO4J_DATABASE
    ) as session:

        result = session.run(query)

        for record in result:

            print(
                f"Name: {record.get('name')}"
            )

            print(
                f"State: {record.get('state')}"
            )

            print(
                f"Population: "
                f"{record.get('populationPercent')}"
            )

            print()


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("NEO4J GRAPH LOADER")
    print("=" * 70)

    if not all([
        NEO4J_URI,
        NEO4J_USERNAME,
        NEO4J_PASSWORD,
        NEO4J_DATABASE,
    ]):

        print(
            "Missing one or more Neo4j environment variables:"
        )

        print(
            "NEO4J_URI, "
            "NEO4J_USERNAME, "
            "NEO4J_PASSWORD, "
            "NEO4J_DATABASE"
        )

        sys.exit(1)

    graph, embedding_data = load_json_files()
    chunks = prepare_chunks(
        embedding_data
    )

    chunk_entity_links = (
        prepare_chunk_entity_links(
            graph
        )
    )
    print(
        f"Chunks              : "
        f"{len(chunks)}"
    )

    print(
        f"Chunk → Entity links : "
        f"{len(chunk_entity_links)}"
    )
    entities = prepare_entities(graph)

    source_mentions = prepare_source_mentions(
        graph,
        embedding_data
    )

    relationships = graph.get(
        "relationships",
        []
    )

    relationship_mentions = (
        prepare_relationship_mentions(
            relationships
        )
    )

    dimensions = embedding_data.get(
        "dimension"
    )

    if not dimensions:

        print(
            "Embedding dimension missing."
        )

        sys.exit(1)

    print()
    print(
        f"Entities            : {len(entities)}"
    )

    print(
        f"Source mentions     : "
        f"{len(source_mentions)}"
    )

    print(
        f"Relationships       : "
        f"{len(relationships)}"
    )

    print(
        f"Relationship mentions: "
        f"{len(relationship_mentions)}"
    )

    print(
        f"Embedding dimension : {dimensions}"
    )

    print()
    print("Connecting to Neo4j...")

    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(
            NEO4J_USERNAME,
            NEO4J_PASSWORD
        )
    )

    try:

        driver.verify_connectivity()

        print("Neo4j connection successful.")

        # ----------------------------------------------------
        # Entity constraint
        # ----------------------------------------------------

        with driver.session(
            database=NEO4J_DATABASE
        ) as session:

            run_with_retry(
                session,
                """
                CREATE CONSTRAINT entity_id_unique
                IF NOT EXISTS
                FOR (n:Entity)
                REQUIRE n.entity_id IS UNIQUE
                """
            )

        # ----------------------------------------------------
        # Load
        # ----------------------------------------------------

        load_entities(
            driver,
            entities
        )

        load_chunks(
            driver,
            chunks
        )

        load_chunk_entity_links(
            driver,
            chunk_entity_links
        )

        load_source_mentions(
            driver,
            source_mentions
        )

        load_relationships(
            driver,
            relationships
        )

        load_relationship_mentions(
            driver,
            relationship_mentions
        )

        # ----------------------------------------------------
        # Vector index
        # ----------------------------------------------------

        create_vector_index(
            driver,
            dimensions
        )

        print_counts(driver)

        check_vector_index(driver)

        print()
        print("=" * 70)
        print("NEO4J LOAD COMPLETE")
        print("=" * 70)

    finally:

        driver.close()


if __name__ == "__main__":
    main()