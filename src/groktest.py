import os
import json

from dotenv import load_dotenv
from llama_index.llms.groq import Groq


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
# SELECT TECHNICAL CHUNK
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

    if "................................................................" in text:
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
    raise RuntimeError("No suitable technical chunk found.")


text = selected_chunk["text"]

print()
print("=" * 80)
print(f"SELECTED CHUNK: {selected_index}")
print("=" * 80)
print(text[:4000])


# =========================================================
# LLAMAINDEX GROQ
# =========================================================

llm = Groq(
    model="openai/gpt-oss-120b",
    api_key=LLM_API,
    temperature=0.0,
)


# =========================================================
# TEST NORMAL LLAMAINDEX COMPLETION
# =========================================================

prompt = f"""
You are extracting information from a 3GPP telecommunications
specification.

Identify the important entities and relationships in this text.

TEXT:

{text}

Give a concise description of:
1. Important entities
2. Relationships between those entities
"""

print()
print("=" * 80)
print("TESTING LLAMAINDEX GROQ")
print("=" * 80)

response = llm.complete(prompt)

print()
print("LLM RESPONSE:")
print(response.text)