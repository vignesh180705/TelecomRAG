import hashlib

from neo4j import GraphDatabase

from config import (
    NEO4J_URI,
    NEO4J_USERNAME,
    NEO4J_PASSWORD,
    NEO4J_DATABASE,
)


class GraphLoader:

    def __init__(self):

        self.driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(
                NEO4J_USERNAME,
                NEO4J_PASSWORD,
            ),
        )

    def close(self):

        self.driver.close()

    def verify_connectivity(self):

        self.driver.verify_connectivity()

        print(
            "Neo4j connectivity: OK"
        )

    def init_schema(self):

        queries = [

            """
            CREATE CONSTRAINT entity_id_unique
            IF NOT EXISTS
            FOR (e:Entity)
            REQUIRE e.entity_id IS UNIQUE
            """,

            """
            CREATE CONSTRAINT document_id_unique
            IF NOT EXISTS
            FOR (d:Document)
            REQUIRE d.document_id IS UNIQUE
            """,

            """
            CREATE CONSTRAINT chunk_id_unique
            IF NOT EXISTS
            FOR (c:Chunk)
            REQUIRE c.chunk_id IS UNIQUE
            """,

            """
            CREATE CONSTRAINT mention_id_unique
            IF NOT EXISTS
            FOR (m:SourceMention)
            REQUIRE m.mention_id IS UNIQUE
            """,

            """
            CREATE CONSTRAINT relation_mention_id_unique
            IF NOT EXISTS
            FOR (m:RelationshipMention)
            REQUIRE m.relation_mention_id IS UNIQUE
            """,
        ]

        with self.driver.session(
            database=NEO4J_DATABASE
        ) as session:

            for query in queries:

                session.run(query)

        print(
            "Neo4j schema: OK"
        )

    def load_document_and_chunk(
        self,
        document,
        chunk,
    ):

        query = """

        MERGE (d:Document {
            document_id: $document_id
        })

        SET
            d.filename = $filename,
            d.page_count = $page_count

        MERGE (c:Chunk {
            chunk_id: $chunk_id
        })

        SET
            c.document_id = $document_id,
            c.filename = $filename,
            c.page_start = $page_start,
            c.page_end = $page_end,
            c.chunk_index = $chunk_index,
            c.text = $text

        MERGE (c)-[:FROM_DOCUMENT]->(d)

        """

        with self.driver.session(
            database=NEO4J_DATABASE
        ) as session:

            session.run(
                query,
                document_id=
                    document["document_id"],
                filename=
                    document["filename"],
                page_count=
                    document["page_count"],
                chunk_id=
                    chunk["chunk_id"],
                page_start=
                    chunk["page_start"],
                page_end=
                    chunk["page_end"],
                chunk_index=
                    chunk["chunk_index"],
                text=
                    chunk["text"],
            )

    def load_extraction(
        self,
        extraction,
        chunk,
        document,
    ):

        entity_map = {}

        for entity in extraction[
            "entities"
        ]:

            self.load_entity(
                entity
            )

            self.load_source_mention(
                entity,
                chunk,
                document,
            )

            entity_map[
                (
                    entity["canonical_name"],
                    entity["entity_type"],
                )
            ] = entity["entity_id"]

        for relationship in extraction[
            "relationships"
        ]:

            self.load_relationship(
                relationship,
                chunk,
                document,
                entity_map,
            )

    def load_entity(self, entity):

        query = """

        MERGE (e:Entity {
            entity_id: $entity_id
        })

        SET
            e.canonical_name =
                $canonical_name,

            e.entity_type =
                $entity_type,

            e.aliases =
                $aliases

        FOREACH (
            x IN CASE
                WHEN $description <> ''
                THEN [1]
                ELSE []
            END |
            SET e.description =
                $description
        )

        """

        with self.driver.session(
            database=NEO4J_DATABASE
        ) as session:

            session.run(
                query,
                **entity,
            )

    def load_source_mention(
        self,
        entity,
        chunk,
        document,
    ):

        raw = (
            f"{entity['entity_id']}|"
            f"{document['filename']}|"
            f"{chunk['page_start']}|"
            f"{entity['evidence']}"
        )

        mention_id = hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest()

        query = """

        MATCH (e:Entity {
            entity_id: $entity_id
        })

        MATCH (c:Chunk {
            chunk_id: $chunk_id
        })

        MERGE (m:SourceMention {
            mention_id: $mention_id
        })

        SET
            m.document =
                $document,

            m.page =
                $page,

            m.evidence =
                $evidence

        MERGE (e)-[:HAS_MENTION]->(m)

        MERGE (m)-[:FROM_CHUNK]->(c)

        """

        with self.driver.session(
            database=NEO4J_DATABASE
        ) as session:

            session.run(
                query,
                entity_id=
                    entity["entity_id"],
                chunk_id=
                    chunk["chunk_id"],
                mention_id=
                    mention_id,
                document=
                    document["filename"],
                page=
                    chunk["page_start"],
                evidence=
                    entity["evidence"],
            )
    def load_relationship(
        self,
        relationship,
        chunk,
        document,
        entity_map,
    ):

        source_id = relationship.get("source_id")
        target_id = relationship.get("target_id")

        if not source_id or not target_id:
            return

        rel_type = relationship.get(
            "relationship",
            ""
        ).strip()

        if not rel_type:
            return

        if not rel_type.replace(
            "_", ""
        ).isalnum():

            return

        query = f"""

        MATCH (s:Entity {{
            entity_id: $source_id
        }})

        MATCH (t:Entity {{
            entity_id: $target_id
        }})

        MERGE (s)-[:{rel_type}]->(t)

        MERGE (rm:RelationshipMention {{
            relation_mention_id:
                $relation_mention_id
        }})

        SET
            rm.relationship =
                $relationship,

            rm.source_name =
                $source_name,

            rm.target_name =
                $target_name,

            rm.document =
                $document,

            rm.page =
                $page,

            rm.evidence =
                $evidence,

            rm.chunk_id =
                $chunk_id

        MERGE (s)-[
            :HAS_RELATION_MENTION
        ]->(rm)

        MERGE (rm)-[
            :TARGET
        ]->(t)

        """

        raw = (
            f"{source_id}|"
            f"{rel_type}|"
            f"{target_id}|"
            f"{document['filename']}|"
            f"{chunk['page_start']}|"
            f"{relationship['evidence']}"
        )

        relation_mention_id = hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest()

        with self.driver.session(
            database=NEO4J_DATABASE
        ) as session:

            session.run(
                query,
                source_id=source_id,
                target_id=target_id,
                relation_mention_id=
                    relation_mention_id,
                relationship=rel_type,
                source_name=
                    relationship.get(
                        "source_name",
                        ""
                    ),
                target_name=
                    relationship.get(
                        "target_name",
                        ""
                    ),
                document=
                    document["filename"],
                page=
                    chunk["page_start"],
                evidence=
                    relationship["evidence"],
                chunk_id=
                    chunk["chunk_id"],
            )
    '''def load_relationship(
        self,
        relationship,
        chunk,
        document,
        entity_map,
    ):

        source_key = (
            relationship["source"],
            relationship["source_type"],
        )

        target_key = (
            relationship["target"],
            relationship["target_type"],
        )

        source_id = entity_map.get(
            source_key
        )

        target_id = entity_map.get(
            target_key
        )

        if not source_id or not target_id:
            return

        rel_type = relationship[
            "relationship"
        ]

        if not rel_type.replace(
            "_", ""
        ).isalnum():

            return

        query = f"""

        MATCH (s:Entity {{
            entity_id: $source_id
        }})

        MATCH (t:Entity {{
            entity_id: $target_id
        }})

        MERGE (s)-[:{rel_type}]->(t)

        MERGE (rm:RelationshipMention {{
            relation_mention_id:
                $relation_mention_id
        }})

        SET
            rm.relationship =
                $relationship,

            rm.document =
                $document,

            rm.page =
                $page,

            rm.evidence =
                $evidence,

            rm.chunk_id =
                $chunk_id

        MERGE (s)-[
            :HAS_RELATION_MENTION
        ]->(rm)

        MERGE (rm)-[
            :TARGET
        ]->(t)

        """

        raw = (
            f"{source_id}|"
            f"{rel_type}|"
            f"{target_id}|"
            f"{document['filename']}|"
            f"{chunk['page_start']}|"
            f"{relationship['evidence']}"
        )

        relation_mention_id = hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest()

        with self.driver.session(
            database=NEO4J_DATABASE
        ) as session:

            session.run(
                query,
                source_id=
                    source_id,
                target_id=
                    target_id,
                relation_mention_id=
                    relation_mention_id,
                relationship=
                    rel_type,
                document=
                    document["filename"],
                page=
                    chunk["page_start"],
                evidence=
                    relationship["evidence"],
                chunk_id=
                    chunk["chunk_id"],
            )'''