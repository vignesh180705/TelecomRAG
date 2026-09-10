"""Neo4j persistence layer. Extraction is deliberately outside this module."""
from neo4j import GraphDatabase


class Neo4jGraphStore:
    def __init__(self, uri, username, password):
        if not uri or not password:
            raise RuntimeError("NEO4J_URI and NEO4J_PASSWORD must be set")
        self.driver = GraphDatabase.driver(uri, auth=(username, password))

    def close(self):
        self.driver.close()

    def verify(self):
        with self.driver.session() as session:
            return session.run("RETURN 1 AS ok").single()["ok"] == 1

    def create_constraints(self):
        queries = [
            "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (n:Entity) REQUIRE n.entity_id IS UNIQUE",
            "CREATE CONSTRAINT document_id_unique IF NOT EXISTS FOR (n:Document) REQUIRE n.document_id IS UNIQUE",
            "CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS FOR (n:Chunk) REQUIRE n.chunk_id IS UNIQUE",
        ]
        with self.driver.session() as session:
            for query in queries:
                session.run(query).consume()

    def upsert_entity(self, entity):
        query = """
        MERGE (n:Entity {entity_id: $entity_id})
        SET n.canonical_name = $canonical_name,
            n.entity_type = $entity_type,
            n.description = $description,
            n.aliases = $aliases,
            n.confidence = $confidence,
            n.status = $status
        """
        params = {
            "entity_id": entity["entity_id"],
            "canonical_name": entity["canonical_name"],
            "entity_type": entity["entity_type"],
            "description": entity.get("description", ""),
            "aliases": entity.get("aliases") or [],
            "confidence": float(entity.get("confidence", 0)),
            "status": entity.get("status", "candidate"),
        }
        with self.driver.session() as session:
            session.run(query, **params).consume()

    def upsert_document(self, document_id, filename):
        query = """
        MERGE (d:Document {document_id: $document_id})
        SET d.filename = $filename
        """
        with self.driver.session() as session:
            session.run(query, document_id=document_id, filename=filename).consume()

    def upsert_chunk(self, chunk):
        document_id = chunk["source"]
        query = """
        MERGE (c:Chunk {chunk_id: $chunk_id})
        SET c.text = $text,
            c.page = $page,
            c.source = $source,
            c.chunk_index = $chunk_index
        MERGE (d:Document {document_id: $document_id})
        SET d.filename = $source
        MERGE (c)-[:PART_OF]->(d)
        """
        with self.driver.session() as session:
            session.run(
                query,
                chunk_id=chunk["id"], text=chunk["text"], page=chunk["page"],
                source=chunk["source"], chunk_index=chunk.get("chunk_index", 0),
                document_id=document_id,
            ).consume()

    def upsert_relationship(self, relationship):
        # Relationship type has already been validated against the ontology.
        # Backticks are used only after validation; no user text is inserted here.
        rel_type = relationship["relationship_type"]
        query = f"""
        MATCH (s:Entity {{entity_id: $source_id}})
        MATCH (t:Entity {{entity_id: $target_id}})
        MERGE (s)-[r:`{rel_type}`]->(t)
        SET r.relationship_id = $relationship_id,
            r.confidence = $confidence,
            r.status = $status,
            r.evidence_count = $evidence_count,
            r.source_count = $source_count,
            r.properties_json = $properties_json
        """
        import json
        with self.driver.session() as session:
            session.run(
                query,
                source_id=relationship["source_entity_id"],
                target_id=relationship["target_entity_id"],
                relationship_id=relationship["relationship_id"],
                confidence=float(relationship.get("confidence", 0)),
                status=relationship.get("status", "candidate"),
                evidence_count=int(relationship.get("evidence_count", 0)),
                source_count=int(relationship.get("source_count", 0)),
                properties_json=json.dumps(relationship.get("properties", {}), ensure_ascii=False),
            ).consume()

            for evidence in relationship.get("evidence", []):
                self.upsert_evidence_link(
                    relationship["source_entity_id"],
                    relationship["target_entity_id"],
                    rel_type,
                    evidence,
                )

    def upsert_evidence_link(self, source_id, target_id, rel_type, evidence):
        query = f"""
        MATCH (s:Entity {{entity_id: $source_id}})
        MATCH (t:Entity {{entity_id: $target_id}})
        MATCH (c:Chunk {{chunk_id: $chunk_id}})
        MERGE (s)-[:SUPPORTED_BY {{relationship_type: $rel_type, evidence: $evidence}}]->(c)
        MERGE (t)-[:MENTIONED_IN]->(c)
        """
        with self.driver.session() as session:
            session.run(
                query,
                source_id=source_id,
                target_id=target_id,
                chunk_id=evidence["chunk_id"],
                rel_type=rel_type,
                evidence=evidence["evidence"],
            ).consume()
