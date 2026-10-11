import os
from dotenv import load_dotenv
import sys
from collections import OrderedDict
import dotenv
import requests
from neo4j import GraphDatabase
from groq import Groq
load_dotenv()
GROQ_API_KEY=os.getenv("GROQ_API_KEY")

OLLAMA_URL="http://localhost:11434/api/embed"
EMBEDDING_MODEL="nomic-embed-text"
VECTOR_INDEX_NAME="chunk_embedding_index"

MAX_CHUNK_CHARS=3500
MAX_GRAPH_RELATIONSHIPS=8

GROQ_MODEL="openai/gpt-oss-120b"
GRAPH_DEPTH=2

NEO4J_URI=os.getenv("NEO4J_URI")
NEO4J_USERNAME=os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD=os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE=os.getenv("NEO4J_DATABASE")
VECTOR_SEARCH_QUERY="""
MATCH (node)
SEARCH node IN (
    VECTOR INDEX chunk_embedding_index
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

GRAPH_CONTEXT_QUERY=f"""
MATCH (c:Chunk {{chunk_id: $chunk_id}})
MATCH (c)-[:MENTIONS]->(e:Entity)

MATCH path=(e)-[*0..{GRAPH_DEPTH - 1}]-(other:Entity)

UNWIND relationships(path) AS rel

WITH DISTINCT
    startNode(rel) AS source,
    rel,
    endNode(rel) AS target

RETURN
    source.entity_id AS source_id,
    source.canonical_name AS source_name,
    source.entity_type AS source_type,
    type(rel) AS relationship_type,
    target.entity_id AS target_id,
    target.canonical_name AS target_name,
    target.entity_type AS target_type
"""

def embed_query(query):
    response=requests.post(
        OLLAMA_URL,
        json={
            "model": EMBEDDING_MODEL,
            "input": query,
            "keep_alive": "10m",
        },
        timeout=120,
    )

    response.raise_for_status()
    data=response.json()
    embeddings=data.get("embeddings")
    if not embeddings:
        raise RuntimeError(f"Ollama returned no embedding:\n{data}")
    return embeddings[0]

def vector_search(driver,query_vector,TOP_K=5):
    with driver.session(database=NEO4J_DATABASE) as session:
        result=session.run(
            VECTOR_SEARCH_QUERY,
            {
                "top_k":TOP_K,
                "query_vector":query_vector
            }
        )
        return [dict(record) for record in result]

def get_graph_context(driver,chunk_id):
    with driver.session(database=NEO4J_DATABASE) as session:
        result=session.run(
            GRAPH_CONTEXT_QUERY,
            {
                "chunk_id": chunk_id
            }
        )
        return [dict(record) for record in result]

def build_context(driver,vector_results):
    context_blocks=[]
    for rank, result in enumerate(vector_results,start=1):
        chunk_id=result["chunk_id"]
        #print(chunk_id)
        graph_rows=get_graph_context(driver,chunk_id)
        block=[]
        block.append(f"=====SOURCE {rank} =====")
        block.append(f"Chunk ID: {chunk_id}")
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
        block.append("Source content:")
        text=result.get("text","")
        text=text[:MAX_CHUNK_CHARS]
        block.append(text)
        block.append("")
        block.append("Graph context:")
        seen_relationships=set()
        relationship_count=0
        for row in graph_rows:
            #print(row)
            source_name=row.get("source_name") or ""
            relationship_type=row.get("relationship_type") or ""
            target_name=row.get("target_name") or ""

            if not (source_name and relationship_type and target_name):
                continue

            relationship=(
                f"{source_name} "
                f"-[{relationship_type}]-> "
                f"{target_name}"
            )

            if relationship in seen_relationships:
                continue

            block.append(f"- {relationship}")
            seen_relationships.add(relationship)

            relationship_count+=1
            if relationship_count >=MAX_GRAPH_RELATIONSHIPS:
                break
        context_blocks.append("\n".join(block))
    #print(context_blocks)
    return "\n\n".join(context_blocks)

def generate_answer(question,options,context,GROQ_API_KEY=GROQ_API_KEY):
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set")

    client=Groq(api_key=GROQ_API_KEY)
    if not options:
        user_prompt=f"""
        Question:
        {question}

        Retrieved knowledge:

        {context}
        """

        SYSTEM_PROMPT="""
        You are a technical assistant for a 3GPP/telecom
        knowledge base.

        Answer the user's question using the supplied retrieved evidence and graph context as additional knowledge.

        Rules:

        1. Do not invent technical facts.
        2. Prefer the retrieved 3GPP evidence over assumptions.
        3. Use graph relationships to connect concepts when they are supported by the supplied context.
        4. If the evidence is insufficient, explicitly say so.
        5. Mention the relevant specification, page, clause,
        or section when available.
        6. Give a concise but technically clear answer.
        """

    else:
        user_prompt=f"""
        Question:
        {question}

        Options:
        1. {options[0]}
        2. {options[1]}
        3. {options[2]}
        4. {options[3]}
        
        Retrieved knowledge:

        {context}


        """

        SYSTEM_PROMPT="""
        You are a technical assistant for a 3GPP/telecom
        knowledge base.

        Answer the user's question using the supplied retrieved evidence and graph context as additional knowledge.


        Rules:

        1. Do not invent technical facts.
        2. Use graph relationships to connect concepts when they are supported by the supplied context.
        3. Answer only with the option choice
        """
    response=client.chat.completions.create(
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

def retrieve(question,top_k,options=None,groq_api_key=GROQ_API_KEY):
    '''print()
    print("=" * 70)
    print("TELECOMRAG")
    print("=" * 70)

    print()
    print(f"Question: {question}")

    print()'''
    #print("1. Generating query embedding...")

    query_vector=embed_query(question)

    '''print(
        f"   Dimension: "
        f"{len(query_vector)}"
    )'''

    driver=GraphDatabase.driver(
        NEO4J_URI,
        auth=(
            NEO4J_USERNAME,
            NEO4J_PASSWORD
        )
    )
    answer=""
    try:
        driver.verify_connectivity()
        #print()
        #print("2. Searching Neo4j vector index...")
        results=vector_search(driver,query_vector,top_k)
        if not results:
            print("No vector results found.")
            return
        '''print(f"Retrieved {len(results)} Chunk nodes.")
        print()'''
        #print("3. Retrieved evidence:")
        '''for i, result in enumerate(results,start=1):
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
            print(f"    {result['text'][:300]}")
        print()'''
        #print("4. Expanding graph context...")
        context=build_context(driver,results)
        '''print("\n================GRAPH CONTEXT ================")
        print(context)
        print("================================================")'''
        '''print()
        print(
            "5. Generating answer with "
            f"{GROQ_MODEL}..."
        )'''

        answer=generate_answer(question,options,context,groq_api_key)

    except Exception as e:
        print(e)

    finally:
        driver.close()
    return answer,context

def main():
    if len(sys.argv)<2:
        print(
            'Usage:\n'
            'python retriever.py '
            '"your question here"'
        )
        sys.exit(1)

    question=" ".join(sys.argv[1:])
    answer=retrieve(question)
    print(answer)
    '''print("\n================FINAL LLM CONTEXT ================")
    print("ANSWER")
    print("=" * 70)
    print()
    print(answer)

    print()
    print("=" * 70)'''
    if not all([NEO4J_URI,NEO4J_USERNAME,NEO4J_PASSWORD,NEO4J_DATABASE,]):
        print("Missing Neo4j environment variables.")
        sys.exit(1)

if __name__ =="__main__":
    main()