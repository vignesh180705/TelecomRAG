import pymupdf
from pathlib import Path
from llama_index.core import Document

pdf_dir = Path("../data/pdfs")

documents = []

for pdf_path in pdf_dir.glob("*.pdf"):
    print(f"Processing {pdf_path.name}...")

    pdf = pymupdf.open(pdf_path)

    for page_number, page in enumerate(pdf, start=1):
        text = page.get_text()

        if not text.strip():
            continue

        documents.append(
            Document(
                text=text,
                metadata={
                    "source": pdf_path.name,
                    "page": page_number
                }
            )
        )

print(f"Created {len(documents)} page documents.")
print(documents[0].metadata)


from llama_index.core.node_parser import SentenceSplitter

splitter = SentenceSplitter(
    chunk_size=768,
    chunk_overlap=100
)

nodes = splitter.get_nodes_from_documents(documents)

print(f"Created {len(nodes)} chunks.")


import json

chunk_data = []

for node in nodes:
    chunk_data.append({
        "id": node.node_id,
        "source": node.metadata["source"],
        "page": node.metadata["page"],
        "text": node.text
    })

with open("../output/chunks.json", "w", encoding="utf-8") as f:
    json.dump(chunk_data, f, indent=2, ensure_ascii=False)

print(f"Saved {len(chunk_data)} chunks to output/chunks.json")

from collections import Counter

counts = Counter(node.metadata["source"] for node in nodes)

print("\nChunks per PDF:")
for source, count in sorted(counts.items()):
    print(f"{source}: {count}")