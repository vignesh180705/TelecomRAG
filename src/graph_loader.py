import hashlib
from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE

class GraphLoader:
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    def close(self):
        self.driver.close()

    def verify_connectivity(self):
        self.driver.verify_connectivity()
        print("Neo4j connectivity: OK")

    def init_schema(self):
        queries = [
            "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE",
            "CREATE CONSTRAINT document_id_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.document_id IS UNIQUE",
            "CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE",
            "CREATE CONSTRAINT mention_id_unique IF NOT EXISTS FOR (m:SourceMention) REQUIRE m.mention_id IS UNIQUE",
            "CREATE CONSTRAINT relation_mention_id_unique IF NOT EXISTS FOR (m:RelationshipMention) REQUIRE m.relation_mention_id IS UNIQUE",
        ]
        with self.driver.session(database=NEO4J_DATABASE) as s:
            for q in queries:
                s.run(q)
        print("Neo4j schema: OK")

    def load_document(self, d):
        q = """
        MERGE (d:Document {document_id:$document_id})
        SET d.filename=$filename, d.page_count=$page_count,
            d.pages_loaded=$pages_loaded, d.chunks_created=$chunks_created
        """
        with self.driver.session(database=NEO4J_DATABASE) as s:
            s.run(q, **d)

    def load_chunk(self, c):
        q = """
        MATCH (d:Document {document_id:$document_id})
        MERGE (c:Chunk {chunk_id:$chunk_id})
        SET c.document_id=$document_id, c.filename=$filename,
            c.page_start=$page_start, c.page_end=$page_end,
            c.chunk_index=$chunk_index, c.text=$text
        MERGE (c)-[:FROM_DOCUMENT]->(d)
        """
        with self.driver.session(database=NEO4J_DATABASE) as s:
            s.run(q, **c)

    def load_entity(self, e):
        q = """
        MERGE (e:Entity {entity_id:$entity_id})
        SET e.canonical_name=$canonical_name,
            e.entity_type=$entity_type,
            e.aliases=$aliases
        FOREACH (x IN CASE WHEN $description <> '' THEN [1] ELSE [] END |
            SET e.description=$description)
        """
        with self.driver.session(database=NEO4J_DATABASE) as s:
            s.run(q, **e)

    def load_source_mention(self, e, c):
        raw = f"{e['entity_id']}|{c['document_id']}|{c['chunk_id']}|{c['page_start']}|{e['evidence']}"
        mention_id = hashlib.sha256(raw.encode()).hexdigest()
        q = """
        MATCH (e:Entity {entity_id:$entity_id})
        MATCH (c:Chunk {chunk_id:$chunk_id})
        MERGE (m:SourceMention {mention_id:$mention_id})
        SET m.document_id=$document_id, m.document=$document,
            m.page=$page, m.chunk_id=$chunk_id, m.evidence=$evidence
        MERGE (e)-[:HAS_MENTION]->(m)
        MERGE (m)-[:FROM_CHUNK]->(c)
        """
        with self.driver.session(database=NEO4J_DATABASE) as s:
            s.run(q, entity_id=e["entity_id"], chunk_id=c["chunk_id"],
                  mention_id=mention_id, document_id=c["document_id"],
                  document=c["filename"], page=c["page_start"], evidence=e["evidence"])

    def load_relationship(self, r, c):
        sid, tid, rt = r.get("source_id"), r.get("target_id"), r.get("relationship","").strip()
        if not sid or not tid or not rt or not rt.replace("_","").isalnum():
            return

        raw = f"{sid}|{rt}|{tid}|{c['document_id']}|{c['chunk_id']}|{c['page_start']}|{r['evidence']}"
        rid = hashlib.sha256(raw.encode()).hexdigest()

        q = f"""
        MATCH (s:Entity {{entity_id:$source_id}})
        MATCH (t:Entity {{entity_id:$target_id}})
        MATCH (c:Chunk {{chunk_id:$chunk_id}})
        MERGE (s)-[:{rt}]->(t)
        MERGE (rm:RelationshipMention {{relation_mention_id:$relation_mention_id}})
        SET rm.relationship=$relationship, rm.document_id=$document_id,
            rm.document=$document, rm.page=$page, rm.chunk_id=$chunk_id,
            rm.evidence=$evidence, rm.source_name=$source_name,
            rm.source_type=$source_type, rm.target_name=$target_name,
            rm.target_type=$target_type
        MERGE (s)-[:HAS_RELATION_MENTION]->(rm)
        MERGE (rm)-[:TARGET]->(t)
        MERGE (rm)-[:FROM_CHUNK]->(c)
        """
        with self.driver.session(database=NEO4J_DATABASE) as s:
            s.run(q, source_id=sid, target_id=tid, chunk_id=c["chunk_id"],
                  relation_mention_id=rid, relationship=rt,
                  document_id=c["document_id"], document=c["filename"],
                  page=c["page_start"], evidence=r["evidence"],
                  source_name=r.get("source_name",""), source_type=r.get("source_type",""),
                  target_name=r.get("target_name",""), target_type=r.get("target_type",""))
