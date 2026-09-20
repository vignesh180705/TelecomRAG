import json
import re
import sys

from config import VALIDATED_EXTRACTION_FILE, GRAPH_FILE
from normalizer import entity_key, merge_entity, normalize_name


def main():
    if not VALIDATED_EXTRACTION_FILE.exists():
        print(f"Missing {VALIDATED_EXTRACTION_FILE}")
        sys.exit(1)

    payload = json.loads(
        VALIDATED_EXTRACTION_FILE.read_text(encoding="utf-8")
    )

    entities = {}
    relationships = {}

    for chunk in payload.get("chunks", []):
        provenance = {
            "chunk_id": chunk["chunk_id"],
            "document": chunk.get("document", ""),
            "document_file": chunk.get("document_file", ""),
            "page": chunk.get("page"),
            "clause": chunk.get("clause", ""),
            "section_title": chunk.get("section_title", ""),
        }

        name_to_key = {}

        for entity in chunk.get("entities", []):
            key = merge_entity(entities, entity, provenance)
            name_to_key.setdefault(
                normalize_name(entity["name"]).lower(), key
            )

        for rel in chunk.get("relationships", []):
            source_name = normalize_name(rel["source"])
            target_name = normalize_name(rel["target"])
            rtype = rel["relationship"].upper()

            source_key = name_to_key.get(source_name.lower())
            target_key = name_to_key.get(target_name.lower())

            # A relationship may mention an entity not separately extracted
            # in this chunk. We do not invent its type here, so retain the
            # relationship as a review record.
            if not source_key or not target_key:
                continue

            rel_key = f"{source_key}|{rtype}|{target_key}"

            if rel_key not in relationships:
                relationships[rel_key] = {
                    "source": source_key,
                    "relationship": rtype,
                    "target": target_key,
                    "source_mentions": [],
                }

            mention = {
                **provenance,
                "evidence": rel.get("evidence", ""),
            }

            if mention not in relationships[rel_key]["source_mentions"]:
                relationships[rel_key]["source_mentions"].append(mention)

    graph = {
        "version": "1.0",
        "entities": list(entities.values()),
        "relationships": list(relationships.values()),
        "validation_errors": payload.get("errors", []),
    }

    GRAPH_FILE.parent.mkdir(parents=True, exist_ok=True)
    GRAPH_FILE.write_text(
        json.dumps(graph, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Entities: {len(graph['entities'])}")
    print(f"Relationships: {len(graph['relationships'])}")
    print(f"Wrote {GRAPH_FILE}")


if __name__ == "__main__":
    main()
