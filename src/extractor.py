import os
import json

from dotenv import load_dotenv

from llama_index.core import Document, PropertyGraphIndex
from llama_index.core.indices.property_graph import SchemaLLMPathExtractor
from llama_index.llms.groq import Groq
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore

from schema import (
    EntityType,
    RelationType,
    validation_schema,
)


load_dotenv()

LLM_API = os.getenv("LLM_API")

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")

print("Environment variables loaded.")
print(f"Using Neo4j database: {NEO4J_DATABASE}")


CHUNKS_PATH = "../output/chunks.json"

with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
    chunks_data = json.load(f)

print(f"Loaded {len(chunks_data)} chunks.")

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

keywords = [
    "AMF",
    "SMF",
    "UPF",
    "PDU Session",
    "QoS Flow",
    "gNB",
    "N2",
    "N3",
    "Network Slice",
]

technical_documents = []

for i, doc in enumerate(documents):
    text_upper = doc.text.upper()

    if any(keyword.upper() in text_upper for keyword in keywords):
        technical_documents.append((i, doc))

    if len(technical_documents) >= 5:
        break

print("SELECTED TECHNICAL CHUNKS")

for original_index, doc in technical_documents:
    print()
    print(f"CHUNK {original_index}")
    print("-" * 80)
    print(doc.text[:1500])

test_documents = [doc for _, doc in technical_documents]

print()
print(f"Using {len(test_documents)} technical chunks for extraction.")



llm = Groq(
    model="openai/gpt-oss-120b",
    api_key=LLM_API,
    temperature=0.0,
)


kg_extractor = SchemaLLMPathExtractor(
    llm=llm,

    possible_entities=EntityType,

    possible_relations=RelationType,

    kg_validation_schema=validation_schema,

    strict=True,
)


graph_store = Neo4jPropertyGraphStore(
    username=NEO4J_USERNAME,
    password=NEO4J_PASSWORD,
    url=NEO4J_URI,
    database=NEO4J_DATABASE,
)


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
print("EXTRACTION COMPLETE")