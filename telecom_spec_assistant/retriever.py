"""Vector + property-graph retrieval for the 3GPP Specification Assistant.

The retrieval workflow is based on the user's supplied retriever script:
1. Embed the question with Ollama (nomic-embed-text).
2. Retrieve top-k Chunk nodes from the Neo4j vector index.
3. Expand connected Entity nodes and semantic relationships.
4. Ask the Groq-hosted LLM to answer using retrieved evidence.

Configuration is read from environment variables. No secrets belong in the browser.
"""

import os
from typing import Any

import requests
from dotenv import load_dotenv
from neo4j import GraphDatabase
from groq import Groq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/embed")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
VECTOR_INDEX_NAME = os.getenv("VECTOR_INDEX_NAME", "chunk_embedding_index")
NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
GRAPH_DEPTH = max(1, min(int(os.getenv("GRAPH_DEPTH", "2")), 3))
MAX_CHUNK_CHARS = max(500, int(os.getenv("MAX_CHUNK_CHARS", "3500")))
MAX_GRAPH_RELATIONSHIPS = max(1, min(int(os.getenv("MAX_GRAPH_RELATIONSHIPS", "8")), 30))

VECTOR_SEARCH_QUERY = f"""
MATCH (node)
SEARCH node IN (
    VECTOR INDEX {VECTOR_INDEX_NAME}
    FOR $query_vector
    LIMIT $top_k
)
SCORE AS score
RETURN
    node.chunk_id AS chunk_id,
    node.document AS document,
    node.page AS page,
    node.clause AS clause,
    node.section_title AS section_title,
    node.text AS text,
    score
ORDER BY score DESC
"""

GRAPH_CONTEXT_QUERY = f"""
MATCH (c:Chunk {{chunk_id: $chunk_id}})
MATCH (c)-[:MENTIONS]->(e:Entity)
MATCH path=(e)-[*0..{GRAPH_DEPTH - 1}]-(other:Entity)
UNWIND relationships(path) AS rel
WITH DISTINCT startNode(rel) AS source, rel, endNode(rel) AS target
RETURN
    source.entity_id AS source_id,
    source.canonical_name AS source_name,
    source.entity_type AS source_type,
    type(rel) AS relationship_type,
    target.entity_id AS target_id,
    target.canonical_name AS target_name,
    target.entity_type AS target_type
"""


def check_configuration() -> list[str]:
    missing = []
    for name, value in (
        ("GROQ_API_KEY", GROQ_API_KEY),
        ("NEO4J_URI", NEO4J_URI),
        ("NEO4J_USERNAME", NEO4J_USERNAME),
        ("NEO4J_PASSWORD", NEO4J_PASSWORD),
        ("NEO4J_DATABASE", NEO4J_DATABASE),
    ):
        if not value:
            missing.append(name)
    return missing


def embed_query(query: str) -> list[float]:
    response = requests.post(
        OLLAMA_URL,
        json={"model": EMBEDDING_MODEL, "input": query, "keep_alive": "10m"},
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    embeddings = data.get("embeddings")
    if not embeddings:
        raise RuntimeError(f"Ollama returned no embedding: {data}")
    return embeddings[0]


def vector_search(driver, query_vector: list[float], top_k: int = 5) -> list[dict[str, Any]]:
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(
            VECTOR_SEARCH_QUERY,
            {"top_k": top_k, "query_vector": query_vector},
        )
        return [dict(record) for record in result]


def get_graph_context(driver, chunk_id: str) -> list[dict[str, Any]]:
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(GRAPH_CONTEXT_QUERY, {"chunk_id": chunk_id})
        return [dict(record) for record in result]


def collect_graph_edges(driver, vector_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    edges = []
    seen = set()
    per_chunk_limit = MAX_GRAPH_RELATIONSHIPS
    for result in vector_results:
        for row in get_graph_context(driver, str(result.get("chunk_id", ""))):
            source_name = row.get("source_name") or ""
            relationship_type = row.get("relationship_type") or ""
            target_name = row.get("target_name") or ""
            if not (source_name and relationship_type and target_name):
                continue
            key = (source_name, relationship_type, target_name)
            if key in seen:
                continue
            seen.add(key)
            edges.append({
                "source": source_name,
                "source_type": row.get("source_type") or "",
                "relationship": relationship_type,
                "target": target_name,
                "target_type": row.get("target_type") or "",
                "chunk_id": result.get("chunk_id", ""),
            })
            # Keep returned graph context finite even with dense neighborhoods.
            if len(edges) >= max(per_chunk_limit, per_chunk_limit * len(vector_results)):
                return edges
    return edges


def build_context(
    vector_results: list[dict[str, Any]],
    graph_edges: list[dict[str, Any]],
) -> str:
    edges_by_chunk: dict[str, list[dict[str, Any]]] = {}
    for edge in graph_edges:
        edges_by_chunk.setdefault(str(edge.get("chunk_id", "")), []).append(edge)

    context_blocks = []
    for rank, result in enumerate(vector_results, start=1):
        chunk_id = str(result.get("chunk_id") or "")
        block = [f"SOURCE {rank}", f"Chunk ID: {chunk_id}"]
        block.append(f"Document: {result.get('document') or 'Not available'}")
        block.append(f"Page: {result.get('page') if result.get('page') is not None else 'Not available'}")
        block.append(f"Clause: {result.get('clause') or 'Not available'}")
        block.append(f"Section: {result.get('section_title') or 'Not available'}")
        try:
            block.append(f"Vector similarity: {float(result.get('score') or 0):.4f}")
        except (TypeError, ValueError):
            block.append("Vector similarity: Not available")
        block.extend(["", "Source content:", str(result.get("text") or "")[:MAX_CHUNK_CHARS], "", "Graph context:"])
        chunk_edges = edges_by_chunk.get(chunk_id, [])[:MAX_GRAPH_RELATIONSHIPS]
        if not chunk_edges:
            block.append("No semantic relationship rows were returned for this chunk.")
        else:
            for edge in chunk_edges:
                block.append(f"- {edge['source']} -[{edge['relationship']}]-> {edge['target']}")
        context_blocks.append("\n".join(block))
    return "\n\n".join(context_blocks)


def generate_answer(question: str, context: str, groq_api_key: str | None = None) -> str:
    api_key = groq_api_key or GROQ_API_KEY
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not configured on the server.")
    client = Groq(api_key=api_key)
    system_prompt = """You are a technical assistant for a 3GPP and telecom property-graph knowledge base.
Answer the user's question using the supplied retrieved evidence. The graph relationships provide additional context but should not override the source text.

Rules:
1. Do not invent technical facts or clauses.
2. Prefer the retrieved 3GPP evidence over general assumptions.
3. Use graph relationships only when supported by the provided context.
4. If the evidence is insufficient, say so clearly instead of guessing.
5. Cite relevant specification/document names and page numbers from the supplied context when available.
6. Give a concise, technically clear answer with readable paragraphs or bullets where useful.
7. Distinguish direct evidence from cautious inference.
"""
    user_prompt = f"Question:\n{question}\n\nRetrieved evidence and graph context:\n{context}"
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
    )
    answer = response.choices[0].message.content
    if not answer:
        raise RuntimeError("The language model returned an empty answer.")
    return answer.strip()


def retrieve_detailed(question: str, top_k: int = 5) -> dict[str, Any]:
    question = question.strip()
    if not question:
        raise ValueError("Please enter a question.")
    top_k = max(1, min(int(top_k), 10))

    missing = check_configuration()
    if missing:
        raise RuntimeError("Missing server configuration: " + ", ".join(missing))

    query_vector = embed_query(question)
    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
    )
    try:
        driver.verify_connectivity()
        results = vector_search(driver, query_vector, top_k)
        if not results:
            return {
                "answer": "I could not find relevant chunks in the configured vector index for this question. Try rephrasing it using the terminology from the 3GPP specifications.",
                "sources": [],
                "graph_relationships": [],
                "retrieved_count": 0,
            }
        graph_edges = collect_graph_edges(driver, results)
        context = build_context(results, graph_edges)
        answer = generate_answer(question, context)
        sources = []
        for result in results:
            try:
                score = float(result.get("score") or 0)
            except (TypeError, ValueError):
                score = 0.0
            sources.append({
                "chunk_id": result.get("chunk_id") or "",
                "document": result.get("document") or "Unknown document",
                "page": result.get("page"),
                "clause": result.get("clause") or "",
                "section_title": result.get("section_title") or "",
                "score": score,
                "snippet": str(result.get("text") or "")[:700],
            })
        return {
            "answer": answer,
            "sources": sources,
            "graph_relationships": graph_edges,
            "retrieved_count": len(results),
        }
    finally:
        driver.close()


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Ask the 3GPP property-graph retriever a question")
    parser.add_argument("question", nargs="+", help="Question to answer")
    parser.add_argument("--top-k", type=int, default=5, help="Number of source chunks to retrieve (1-10)")
    args = parser.parse_args()
    result = retrieve_detailed(" ".join(args.question), args.top_k)
    print(result["answer"])
    if result["sources"]:
        print("\nSources:")
        for source in result["sources"]:
            print(f"- {source['document']}, page {source['page']}, chunk {source['chunk_id']}")


if __name__ == "__main__":
    main()
