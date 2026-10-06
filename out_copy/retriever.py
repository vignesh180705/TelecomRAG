import os
import sys
from collections import OrderedDict
import dotenv
import requests
from neo4j import GraphDatabase
from groq import Groq

GROQ_API_KEY = os.getenv("GROQ_API_KEY")



# ============================================================
# CONFIG
# ============================================================

OLLAMA_URL = "http://localhost:11434/api/embed"
EMBEDDING_MODEL = "nomic-embed-text"

VECTOR_INDEX_NAME = "chunk_embedding_index"

TOP_K = 4

MAX_CHUNK_CHARS = 3500
MAX_GRAPH_RELATIONSHIPS = 8

GROQ_MODEL = "openai/gpt-oss-120b"
GRAPH_HOPS = 1


# ============================================================
# ENV
# ============================================================

NEO4J_URI=os.getenv("NEO4J_URI")
NEO4J_USERNAME=os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD=os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE=os.getenv("NEO4J_DATABASE")


# ============================================================
# EMBEDDING
# ============================================================

def embed_query(query):

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": EMBEDDING_MODEL,
            "input": query,
            "keep_alive": "10m",
        },
        timeout=120,
    )

    response.raise_for_status()

    data = response.json()

    embeddings = data.get(
        "embeddings"
    )

    if not embeddings:
        raise RuntimeError(
            f"Ollama returned no embedding:\n{data}"
        )

    return embeddings[0]


# ============================================================
# VECTOR SEARCH
# ============================================================

VECTOR_SEARCH_QUERY = """
CALL db.index.vector.queryNodes(
    $index_name,
    $top_k,
    $query_vector
)
YIELD node, score

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


def vector_search(
    driver,
    query_vector
):

    with driver.session(
        database=NEO4J_DATABASE
    ) as session:

        result = session.run(
            VECTOR_SEARCH_QUERY,
            {
                "index_name":
                    VECTOR_INDEX_NAME,

                "top_k":
                    TOP_K,

                "query_vector":
                    query_vector,
            }
        )

        return [
            dict(record)
            for record in result
        ]


# ============================================================
# GRAPH EXPANSION
# ============================================================

GRAPH_CONTEXT_QUERY = """
MATCH (c:Chunk {
    chunk_id: $chunk_id
})

OPTIONAL MATCH (c)-[:MENTIONS]->(e:Entity)

OPTIONAL MATCH (e)-[r]-(other:Entity)

RETURN
    e.entity_id AS entity_id,
    e.canonical_name AS entity_name,
    e.entity_type AS entity_type,
    e.description AS entity_description,
    type(r) AS relationship_type,
    other.entity_id AS other_entity_id,
    other.canonical_name AS other_entity_name,
    other.entity_type AS other_entity_type
"""

def get_graph_context(
    driver,
    chunk_id
):

    with driver.session(
        database=NEO4J_DATABASE
    ) as session:

        result = session.run(
            GRAPH_CONTEXT_QUERY,
            {
                "chunk_id": chunk_id
            }
        )

        return [
            dict(record)
            for record in result
        ]


# ============================================================
# CONTEXT BUILDING
# ============================================================

def build_context(
    driver,
    vector_results
):

    context_blocks = []

    for rank, result in enumerate(
        vector_results,
        start=1
    ):

        chunk_id = result[
            "chunk_id"
        ]

        graph_rows = get_graph_context(
            driver,
            chunk_id
        )

        block = []

        block.append(
            f"===== SOURCE {rank} ====="
        )

        block.append(
            f"Chunk ID: {chunk_id}"
        )

        block.append(
            f"Document: "
            f"{result.get('document', '')}"
        )

        block.append(
            f"Page: "
            f"{result.get('page', '')}"
        )

        block.append(
            f"Clause: "
            f"{result.get('clause', '')}"
        )

        block.append(
            f"Section: "
            f"{result.get('section_title', '')}"
        )

        block.append(
            f"Vector similarity: "
            f"{result.get('score', 0):.4f}"
        )

        block.append("")

        # ----------------------------------------------------
        # ORIGINAL SOURCE CONTENT
        # ----------------------------------------------------

        block.append(
            "Source content:"
        )

        text = result.get(
            "text",
            ""
        )

        text = text[
            :MAX_CHUNK_CHARS
        ]

        block.append(text)

        # ----------------------------------------------------
        # GRAPH
        # ----------------------------------------------------

        block.append("")

        block.append(
            "Graph context:"
        )

        seen_relationships = set()

        relationship_count = 0

        for row in graph_rows:

            entity_name = (
                row.get(
                    "entity_name"
                )
                or ""
            )

            relationship_type = (
                row.get(
                    "relationship_type"
                )
                or ""
            )

            other_name = (
                row.get(
                    "other_entity_name"
                )
                or ""
            )

            if (
                entity_name
                and relationship_type
                and other_name
            ):

                relationship = (
                    f"{entity_name} "
                    f"-[{relationship_type}]-> "
                    f"{other_name}"
                )

                if (
                    relationship
                    not in seen_relationships
                ):

                    block.append(
                        f"- {relationship}"
                    )

                    seen_relationships.add(
                        relationship
                    )

                    relationship_count += 1

                    if (
                        relationship_count
                        >= MAX_GRAPH_RELATIONSHIPS
                    ):
                        break

        context_blocks.append(
            "\n".join(block)
        )

    return "\n\n".join(
        context_blocks
    )
# ============================================================
# LLM
# ============================================================

SYSTEM_PROMPT = """
You are a technical assistant for a 3GPP/telecom
knowledge base.

Answer the user's question using ONLY the supplied
retrieved evidence and graph context.

Rules:

1. Do not invent technical facts.
2. Prefer the retrieved 3GPP evidence over assumptions.
3. Use graph relationships to connect concepts when
   they are supported by the supplied context.
4. If the evidence is insufficient, explicitly say so.
5. Mention the relevant specification, page, clause,
   or section when available.
6. Give a concise but technically clear answer.
"""


def generate_answer(
    question,
    context
):

    if not GROQ_API_KEY:

        raise RuntimeError(
            "GROQ_API_KEY is not set"
        )

    client = Groq(
        api_key=GROQ_API_KEY
    )

    user_prompt = f"""
Question:
{question}

Retrieved knowledge:

{context}

Answer the question using only the retrieved
source content and graph context.
"""

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content

# ============================================================
# MAIN
# ============================================================

def main():

    if len(sys.argv) < 2:

        print(
            'Usage:\n'
            'python retriever.py '
            '"your question here"'
        )

        sys.exit(1)

    question = " ".join(
        sys.argv[1:]
    )

    if not all([
        NEO4J_URI,
        NEO4J_USERNAME,
        NEO4J_PASSWORD,
        NEO4J_DATABASE,
    ]):

        print(
            "Missing Neo4j environment variables."
        )

        sys.exit(1)

    print()
    print("=" * 70)
    print("TELECOMRAG")
    print("=" * 70)

    print()
    print(
        f"Question: {question}"
    )

    # --------------------------------------------------------
    # Query embedding
    # --------------------------------------------------------

    print()
    print(
        "1. Generating query embedding..."
    )

    query_vector = embed_query(
        question
    )

    print(
        f"   Dimension: "
        f"{len(query_vector)}"
    )

    # --------------------------------------------------------
    # Neo4j
    # --------------------------------------------------------

    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(
            NEO4J_USERNAME,
            NEO4J_PASSWORD
        )
    )

    try:

        driver.verify_connectivity()

        # ----------------------------------------------------
        # Vector search
        # ----------------------------------------------------

        print()
        print(
            "2. Searching Neo4j vector index..."
        )

        results = vector_search(
            driver,
            query_vector
        )

        if not results:

            print(
                "No vector results found."
            )

            return

        print(
            f"Retrieved {len(results)} Chunk nodes."
        )

        # ----------------------------------------------------
        # Display retrieved evidence
        # ----------------------------------------------------

        print()
        print(
            "3. Retrieved evidence:"
        )

        for i, result in enumerate(
            results,
            start=1
        ):

            print()
            print(
                f"[{i}] "
                f"{result['document']} "
                f"| page {result['page']} "
                f"| score "
                f"{result['score']:.4f}"
            )

            print(
                f"    chunk: "
                f"{result['chunk_id']}"
            )

            print(
                f"    {result['text'][:300]}"
            )

        # ----------------------------------------------------
        # Graph expansion
        # ----------------------------------------------------

        print()
        print(
            "4. Expanding graph context..."
        )
        
        context = build_context(
            driver,
            results
        )
        print("\n================ GRAPH CONTEXT ================")
        print(context)
        print("================================================")
        # LLM
        # ----------------------------------------------------

        print()
        print(
            "5. Generating answer with "
            f"{GROQ_MODEL}..."
        )

        answer = generate_answer(
            question,
            context
        )
        print("\n================ FINAL LLM CONTEXT ================")
        print(context)
        print("====================================================")
        # ----------------------------------------------------
        # Output
        # ----------------------------------------------------

        print()
        print("=" * 70)
        print("ANSWER")
        print("=" * 70)
        print()
        print(answer)

        print()
        print("=" * 70)

    finally:

        driver.close()


if __name__ == "__main__":
    main()