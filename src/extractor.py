import os
import json

from dotenv import load_dotenv

from llama_index.core import Document, PropertyGraphIndex
from llama_index.core.indices.property_graph import SchemaLLMPathExtractor
from llama_index.llms.ollama import Ollama
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore

from schema import (
    EntityType,
    RelationType,
    validation_schema,
)


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")

if not NEO4J_URI:
    raise ValueError("NEO4J_URI is not set.")

if not NEO4J_USERNAME:
    raise ValueError("NEO4J_USERNAME is not set.")

if not NEO4J_PASSWORD:
    raise ValueError("NEO4J_PASSWORD is not set.")


# ============================================================
# LOAD CHUNKS
# ============================================================

CHUNKS_PATH = "../output/chunks.json"

with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
    chunks_data = json.load(f)

print(f"Loaded {len(chunks_data)} chunks.")


# ============================================================
# CONVERT CHUNKS TO LLAMAINDEX DOCUMENTS
# ============================================================

documents = []

for chunk in chunks_data:

    text = chunk["text"]

    metadata = chunk.get("metadata", {})

    documents.append(
        Document(
            text=text,
            metadata=metadata,
        )
    )


# ============================================================
# TEST WITH FIRST 10 CHUNKS
# ============================================================

test_documents = documents[:10]

print(f"Using {len(test_documents)} chunks for extraction.")


# ============================================================
# LOCAL LLM
# ============================================================

llm = Ollama(
    model="llama3.1:8b",
    request_timeout=120.0,
)


# ============================================================
# SCHEMA-GUIDED KNOWLEDGE GRAPH EXTRACTOR
# ============================================================

kg_extractor = SchemaLLMPathExtractor(
    llm=llm,

    possible_entities=EntityType,

    possible_relations=RelationType,

    kg_validation_schema=validation_schema,

    strict=True,
)


# ============================================================
# NEO4J
# ============================================================

NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")

if not NEO4J_DATABASE:
    raise ValueError("NEO4J_DATABASE is not set.")

print(f"Using Neo4j database: {NEO4J_DATABASE}")

graph_store = Neo4jPropertyGraphStore(
    username=NEO4J_USERNAME,
    password=NEO4J_PASSWORD,
    url=NEO4J_URI,
    database=NEO4J_DATABASE,
)


# ============================================================
# BUILD KNOWLEDGE GRAPH
# ============================================================

index = PropertyGraphIndex.from_documents(
    test_documents,

    property_graph_store=graph_store,

    kg_extractors=[
        kg_extractor,
    ],

    llm=llm,

    embed_kg_nodes=False,

    show_progress=True,
)


print()
print("=" * 60)
print("EXTRACTION COMPLETE")
print("=" * 60)