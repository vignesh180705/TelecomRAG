import json
import sys

from config import (
    RAW_EXTRACTION_FILE,
    VALIDATED_EXTRACTION_FILE,
    SCHEMA_FILE,
    ALLOWED_ENTITY_TYPES,
)


def load_schema():
    return json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))


def relationship_types(schema):
    return {
        r["relationship_type"]
        for r in schema.get("ontology", {}).get("relationships", [])
        if isinstance(r, dict) and r.get("relationship_type")
    }


def main():
    if not RAW_EXTRACTION_FILE.exists():
        print(f"Missing {RAW_EXTRACTION_FILE}")
        sys.exit(1)

    raw = json.loads(RAW_EXTRACTION_FILE.read_text(encoding="utf-8"))
    schema = load_schema()

    schema_classes = {
        c["entity_type"]
        for c in schema.get("ontology", {}).get("classes", [])
        if isinstance(c, dict) and c.get("entity_type")
    }

    allowed_types = set(ALLOWED_ENTITY_TYPES) | schema_classes
    allowed_relationships = relationship_types(schema)

    validated = {
        "version": "1.0",
        "chunk_count": 0,
        "chunks": [],
        "errors": [],
    }

    for chunk in raw.get("chunks", []):
        clean = {
            "chunk_id": chunk["chunk_id"],
            "document": chunk.get("document", ""),
            "document_file": chunk.get("document_file", ""),
            "page": chunk.get("page"),
            "clause": chunk.get("clause", ""),
            "section_title": chunk.get("section_title", ""),
            "entities": [],
            "relationships": [],
        }

        for entity in chunk.get("entities", []):
            et = str(entity.get("entity_type", "")).strip().upper()
            name = str(entity.get("name", "")).strip()

            if not name:
                validated["errors"].append(
                    {"chunk_id": chunk["chunk_id"], "error": "empty entity name"}
                )
                continue

            if et not in allowed_types:
                validated["errors"].append({
                    "chunk_id": chunk["chunk_id"],
                    "error": f"unknown entity type: {et}",
                    "entity": entity,
                })
                continue

            clean["entities"].append({
                "name": name,
                "entity_type": et,
                "description": entity.get("description", ""),
                "evidence": entity.get("evidence", ""),
            })

        for rel in chunk.get("relationships", []):
            source = str(rel.get("source", "")).strip()
            target = str(rel.get("target", "")).strip()
            rtype = str(rel.get("relationship", "")).strip().upper()

            if not source or not target or not rtype:
                validated["errors"].append({
                    "chunk_id": chunk["chunk_id"],
                    "error": "incomplete relationship",
                    "relationship": rel,
                })
                continue

            # Unknown relationship names are retained for review rather than
            # silently changing model output.
            if allowed_relationships and rtype not in allowed_relationships:
                validated["errors"].append({
                    "chunk_id": chunk["chunk_id"],
                    "error": f"relationship not in schema: {rtype}",
                    "relationship": rel,
                })

            clean["relationships"].append({
                "source": source,
                "relationship": rtype,
                "target": target,
                "evidence": rel.get("evidence", ""),
            })

        validated["chunks"].append(clean)

    validated["chunk_count"] = len(validated["chunks"])

    VALIDATED_EXTRACTION_FILE.parent.mkdir(parents=True, exist_ok=True)
    VALIDATED_EXTRACTION_FILE.write_text(
        json.dumps(validated, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Validated chunks: {validated['chunk_count']}")
    print(f"Validation errors: {len(validated['errors'])}")
    print(f"Wrote {VALIDATED_EXTRACTION_FILE}")


if __name__ == "__main__":
    main()
