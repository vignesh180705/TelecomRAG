import os
import re

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

MODEL = "qwen2.5:14b"

MAX_ENTITIES = 15
KG_MAX_FACTS = 50

def find_entities_in_query(query):

    terms = re.findall(
        r"[A-Za-z0-9-]+",
        query
    )

    terms = [
        term
        for term in terms
        if len(term) >= 2
    ]

    if not terms:
        return []

    cypher = """
    CALL db.index.fulltext.queryNodes(
        "entitySearch",
        $search_text
    )
    YIELD node, score

    OPTIONAL MATCH
        (node)-[:MENTIONED_IN]->(m:SourceMention)

    RETURN
        node.canonical_name AS entity,
        node.entity_type AS entity_type,
        score,

        collect(DISTINCT {
            document: m.document,
            page: m.page,
            clause: m.clause,
            section_title: m.section_title,
            chunk_id: m.chunk_id,
            evidence: m.evidence
        })[0..5] AS mentions

    ORDER BY score DESC
    LIMIT 10
    """

    results = {}

    with driver.session(database=DATABASE) as session:

        for term in terms:

            records = session.run(
                cypher,
                search_text=term,
                limit=MAX_ENTITIES
            )

            for record in records:

                entity = record["entity"]

                if entity is None:
                    continue

                data = record.data()
                if (
                    entity not in results
                    or data["score"] > results[entity]["score"]
                ):
                    results[entity] = data

    final_results = sorted(
        results.values(),
        key=lambda x: x["score"],
        reverse=True
    )

    return final_results[:MAX_ENTITIES]



def retrieve_kg_by_entity(
    entity_name,
    max_facts=KG_MAX_FACTS
):

    cypher = """
    MATCH (e:Entity)
    WHERE toLower(e.canonical_name)
          = toLower($entity_name)

    MATCH (e)-[r]-(n:Entity)

    RETURN
        e.canonical_name AS source,
        e.entity_type AS source_type,

        type(r) AS relationship,

        n.canonical_name AS target,
        n.entity_type AS target_type

    LIMIT $limit
    """

    with driver.session(database=DATABASE) as session:

        records = session.run(
            cypher,
            entity_name=entity_name,
            limit=max_facts
        )

        return [
            record.data()
            for record in records
        ]


def retrieve_kg_for_entities(
    entities,
    max_facts=KG_MAX_FACTS
):

    all_facts = []

    for entity in entities:

        facts = retrieve_kg_by_entity(
            entity["entity"],
            max_facts=max_facts
        )

        all_facts.extend(facts)

    unique = []

    seen = set()

    for fact in all_facts:

        key = (
            fact["source"],
            fact["relationship"],
            fact["target"]
        )

        if key not in seen:

            seen.add(key)
            unique.append(fact)

    return unique[:max_facts]


def format_kg_context(kg_facts):

    if not kg_facts:

        return (
            "No relevant knowledge graph "
            "relationships were retrieved."
        )

    sections = []

    for fact in kg_facts:

        source = fact.get(
            "source",
            "Unknown"
        )

        source_type = fact.get(
            "source_type",
            "Unknown"
        )

        relationship = fact.get(
            "relationship",
            "Unknown"
        )

        target = fact.get(
            "target",
            "Unknown"
        )

        target_type = fact.get(
            "target_type",
            "Unknown"
        )

        sections.append(
            f"- {source} ({source_type}) "
            f"--[{relationship}]--> "
            f"{target} ({target_type})"
        )

    return "\n".join(sections)


def format_entity_evidence(entities):

    if not entities:

        return (
            "No relevant source evidence "
            "was retrieved."
        )

    sections = []

    for item in entities:

        entity = item.get(
            "entity",
            "Unknown"
        )

        entity_type = item.get(
            "entity_type",
            "Unknown"
        )

        score = item.get(
            "score",
            0
        )

        sections.append(
            f"Entity: {entity} "
            f"({entity_type})\n"
            f"Search score: {score:.4f}"
        )

        mentions = item.get(
            "mentions",
            []
        )

        valid_mentions = [
            mention
            for mention in mentions
            if mention.get("document")
        ]

        if not valid_mentions:

            sections.append(
                "- No source mention available."
            )

        else:

            for mention in valid_mentions:

                document = mention.get(
                    "document",
                    "Unknown"
                )

                page = mention.get(
                    "page",
                    "Unknown"
                )

                clause = mention.get(
                    "clause",
                    ""
                )

                section_title = mention.get(
                    "section_title",
                    ""
                )

                chunk_id = mention.get(
                    "chunk_id",
                    ""
                )

                evidence = mention.get(
                    "evidence",
                    ""
                )

                source_line = (
                    f"- Document: {document} "
                    f"(Page {page})"
                )

                if clause:
                    source_line += (
                        f", Clause {clause}"
                    )

                sections.append(source_line)

                if section_title:
                    sections.append(
                        f"  Section: {section_title}"
                    )

                if chunk_id:
                    sections.append(
                        f"  Chunk ID: {chunk_id}"
                    )

                if evidence:
                    sections.append(
                        f"  Evidence: {evidence}"
                    )

        sections.append("")

    return "\n".join(sections)


def build_prompt(
    question,
    kg_context,
    evidence_context
):

    return f"""
You are a precise technical telecommunications
question-answering system.

You are answering questions about 3GPP telecommunications
using a Neo4j knowledge graph.

Use ONLY the supplied knowledge graph and source evidence.

Do not use outside knowledge.

If the supplied context is insufficient to answer the
question, clearly state that the available graph context
is insufficient.

When answering:

- Use the knowledge graph relationships when relevant.
- Use source evidence to support the answer.
- Do not invent entities or relationships.
- Do not invent document names or page numbers.
- Do not assume information that is not present.
- Keep the answer technically precise.
- If multiple entities are involved, explain their
  relationships clearly.


KNOWLEDGE GRAPH:
{kg_context}

SOURCE EVIDENCE:
{evidence_context}

QUESTION:
{question}

ANSWER:
"""

def ask_llm(
    question,
    kg_context,
    evidence_context
):

    prompt = build_prompt(
        question,
        kg_context,
        evidence_context
    )

    response = ollama.chat(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response["message"]["content"]


def main():

    print("=" * 60)
    print("TelecomRAG Graph Query")
    print("=" * 60)

    print(
        f"Neo4j Database : {DATABASE}"
    )

    print(
        f"LLM Model      : {MODEL}"
    )

    print(
        "\nType 'exit' to quit.\n"
    )

    while True:

        question = input(
            "Question: "
        ).strip()

        if not question:
            continue

        if question.lower() == "exit":
            break

        entities = find_entities_in_query(
            question
        )

        kg_facts = retrieve_kg_for_entities(
            entities,
            max_facts=KG_MAX_FACTS
        )
        kg_context = format_kg_context(
            kg_facts
        )

        evidence_context = format_entity_evidence(
            entities
        )
        print("\n")
        print("=" * 60)
        print("RETRIEVED ENTITIES")
        print("=" * 60)

        if not entities:

            print(
                "No relevant entities found."
            )

        else:

            for entity in entities:

                print(
                    f"{entity['entity']} "
                    f"({entity['entity_type']}) "
                    f"[score={entity['score']:.4f}]"
                )


        print("\n")
        print("=" * 60)
        print("KNOWLEDGE GRAPH CONTEXT")
        print("=" * 60)

        print(kg_context)

        print("\n")
        print("=" * 60)
        print("SOURCE EVIDENCE")
        print("=" * 60)

        print(evidence_context)

        print("\n")
        print("=" * 60)
        print("LLM ANSWER")
        print("=" * 60)

        answer = ask_llm(
            question,
            kg_context,
            evidence_context
        )

        print(answer)

        print("\n")
        print("=" * 60)
        print()


if __name__ == "__main__":
    main()