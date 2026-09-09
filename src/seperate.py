import os
import json

from dotenv import load_dotenv

from llama_index.core import Document
from llama_index.core.indices.property_graph import SchemaLLMPathExtractor
from llama_index.llms.groq import Groq

from schema import (
    EntityType,
    RelationType,
    validation_schema,
)


load_dotenv()

LLM_API = os.getenv("LLM_API")

if not LLM_API:
    raise ValueError("LLM_API is not set.")


# =========================================================
# LOAD CHUNKS
# =========================================================

CHUNKS_PATH = "../output/chunks.json"

with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
    chunks_data = json.load(f)

print(f"Loaded {len(chunks_data)} chunks.")


# =========================================================
# FIND A TECHNICAL PROSE CHUNK
# =========================================================

keywords = [
    "AMF",
    "SMF",
    "UPF",
    "PDU Session",
    "QoS Flow",
    "gNB",
    "N2",
    "N3",
]


selected_chunk = None
selected_index = None

for i, chunk in enumerate(chunks_data):

    text = chunk["text"]

    # Ignore obvious TOC chunks
    toc_indicators = [
        "................................................................",
        "Table of Contents",
        "Contents",
    ]

    if any(indicator in text for indicator in toc_indicators):
        continue

    keyword_count = sum(
        keyword.lower() in text.lower()
        for keyword in keywords
    )

    if keyword_count >= 2 and len(text) > 500:
        selected_chunk = chunk
        selected_index = i
        break


if selected_chunk is None:
    raise RuntimeError(
        "Could not find a suitable technical prose chunk."
    )


print()
 
print(f"SELECTED CHUNK: {selected_index}")
 

print(selected_chunk["text"][:5000])


# =========================================================
# CREATE DOCUMENT
# =========================================================

document = Document(
    text=selected_chunk["text"],
    metadata=selected_chunk.get("metadata", {}),
)


# =========================================================
# CREATE GROQ LLM
# =========================================================

llm = Groq(
    model="openai/gpt-oss-120b",
    api_key=LLM_API,
    temperature=0.0,
)


# =========================================================
# CREATE SCHEMA EXTRACTOR
# =========================================================

kg_extractor = SchemaLLMPathExtractor(
    llm=llm,
    possible_entities=EntityType,
    possible_relations=RelationType,
    kg_validation_schema=validation_schema,
    strict=False,
)

print()
print("RUNNING SCHEMA EXTRACTION")

result_nodes = kg_extractor([document])


print()
print("RESULT")
 

print("Returned nodes:", len(result_nodes))

for i, node in enumerate(result_nodes):

    print()
    print("-" * 80)
    print(f"NODE {i}")
    print("-" * 80)

    print("Type:")
    print(type(node))

    print()
    print("Metadata keys:")
    print(node.metadata.keys())

    print()
    print("Full metadata:")

    print(node.metadata)

    print()
    print("KG relations:")

    relations = node.metadata.get("kg_relations")

    if relations:
        print("FOUND RELATIONS:")
        for relation in relations:
            print(relation)
    else:
        print("NO KG RELATIONS FOUND")