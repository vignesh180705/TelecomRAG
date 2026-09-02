from llama_index.core.node_parser import SentenceSplitter

splitter = SentenceSplitter(
    chunk_size=768,
    chunk_overlap=100
)

nodes = splitter.get_nodes_from_documents(documents)

print(f"Created {len(nodes)} chunks.")