import os
from neo4j import GraphDatabase
from dotenv import load_dotenv
import ollama


load_dotenv()

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(
        os.getenv("NEO4J_USERNAME"),
        os.getenv("NEO4J_PASSWORD"),
    ),
)

DATABASE = os.getenv("NEO4J_DATABASE")
print(DATABASE)
MODEL = "qwen2.5:14b"

SEARCH_QUERY = """
CALL db.index.fulltext.queryNodes("entitySearch", $search_text)
YIELD node, score

OPTIONAL MATCH (node)-[:MENTIONED_IN]->(m:SourceMention)

RETURN
    node.canonical_name AS entity,
    node.entity_type AS entity_type,
    score,
    collect(DISTINCT {
        document: m.document,
        page: m.page,
        evidence: m.evidence
    })[0..5] AS mentions

ORDER BY score DESC
LIMIT 15
"""

import re

def retrieve(question: str):
    terms = re.findall(r"[A-Za-z0-9-]+", question)
    results = {}

    with driver.session(database=DATABASE) as session:
        for term in terms:
            if len(term) < 2:
                continue

            query_result = session.run(
                SEARCH_QUERY,
                search_text=term
            )

            for record in query_result:
                results[record["entity"]] = record.data()

    return list(results.values())
# -----------------------------------------------------
# Build Context
# -----------------------------------------------------

def build_context(results):
    if not results:
        return "No relevant entities found."

    context = []

    for item in results:
        context.append(
            f"Entity: {item['entity']} ({item['entity_type']})"
        )

        for mention in item["mentions"]:
            context.append(
                f"- Document: {mention['document']} "
                f"(Page {mention['page']})"
            )
            context.append(
                f"  Evidence: {mention['evidence']}"
            )

        context.append("")

    return "\n".join(context)


# -----------------------------------------------------
# Ask Local LLM
# -----------------------------------------------------

def ask_llm(question, context):

    prompt = f"""
You are answering questions using a 3GPP telecom knowledge graph.

Only use the supplied graph context.
If the context is insufficient, say so.

GRAPH CONTEXT
--------------
{context}

QUESTION
--------------
{question}

ANSWER
--------------
"""

    response = ollama.chat(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )

    return response["message"]["content"]


# -----------------------------------------------------
# CLI
# -----------------------------------------------------

def main():

    print("TelecomRAG Graph Query")
    print("Type 'exit' to quit.\n")

    while True:

        question = input("Question: ")

        if question.lower() == "exit":
            break

        results = retrieve(question)

        context = build_context(results)

        print("\nRetrieved Context\n-----------------")
        print(context)

        print("\nLLM Answer\n----------")

        answer = ask_llm(question, context)

        print(answer)
        print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    main()