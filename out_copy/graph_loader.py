"""
graph_extraction_with_relationships.json -> graph_data.json

Builds the final normalized graph representation.

No Neo4j, LLM, PDF or extraction happens here.
"""

import json
import sys

from config import VALIDATED_EXTRACTION_FILE, GRAPH_FILE
from normalizer import merge_entity, normalize_name


def main():
    if not VALIDATED_EXTRACTION_FILE.exists():
        print(f"Missing {VALIDATED_EXTRACTION_FILE}")
        sys.exit(1)

    payload = json.loads(
        VALIDATED_EXTRACTION_FILE.read_text(encoding="utf-8")
    )

    # ---------------------------------------------------------------
    # Support both possible extraction formats:
    #
    # 1. {
    #       "chunks": [...]
    #    }
    #
    # 2. [
    #       {...},
    #       {...}
    #    ]
    # ---------------------------------------------------------------

    if isinstance(payload, list):
        chunks = payload
        validation_errors = []
    elif isinstance(payload, dict):
        chunks = payload.get("chunks", [])
        validation_errors = payload.get("errors", [])
    else:
        print(
            "Invalid extraction format. Expected a JSON list "
            "or an object containing 'chunks'."
        )
        sys.exit(1)

    print(f"Input chunks: {len(chunks)}")

    entities = {}
    relationships = {}

    # Global normalized entity-name index.
    #
    # Example:
    #
    # "amf" -> {"network_function:abc123"}
    # "smf" -> {"network_function:def456"}
    #
    # This is deliberately built across ALL chunks before
    # relationships are processed.
    global_name_index = {}

    # ===============================================================
    # PASS 1
    # Extract and merge ALL entities globally
    # ===============================================================

    for chunk in chunks:
        provenance = {
            "chunk_id": chunk.get("chunk_id", ""),
            "document": chunk.get(
                "document",
                chunk.get("doc", "")
            ),
            "document_file": chunk.get("document_file", ""),
            "page": chunk.get("page"),
            "clause": chunk.get("clause", ""),
            "section_title": chunk.get("section_title", ""),
        }

        for entity in chunk.get("entities", []):
            if not entity.get("name") and not entity.get("canonical_name"):
                continue

            key = merge_entity(
                entities,
                entity,
                provenance,
            )

            normalized_name = normalize_name(
                entity.get("name") or entity.get("canonical_name", "")
            ).lower()

            global_name_index.setdefault(
                normalized_name,
                set(),
            ).add(key)

    print(f"Entities discovered: {len(entities)}")

    # ===============================================================
    # PASS 2
    # Resolve ALL relationships using the GLOBAL entity index
    # ===============================================================

    skipped_relationships = []

    for chunk in chunks:
        provenance = {
            "chunk_id": chunk.get("chunk_id", ""),
            "document": chunk.get(
                "document",
                chunk.get("doc", "")
            ),
            "document_file": chunk.get("document_file", ""),
            "page": chunk.get("page"),
            "clause": chunk.get("clause", ""),
            "section_title": chunk.get("section_title", ""),
        }

        for rel in chunk.get("relationships", []):

            if not rel.get("source"):
                continue

            if not rel.get("target"):
                continue

            if not rel.get("relationship"):
                continue

            source_name = normalize_name(
                rel["source"]
            )

            target_name = normalize_name(
                rel["target"]
            )

            rtype = rel["relationship"].upper().strip()

            source_candidates = global_name_index.get(
                source_name.lower(),
                set(),
            )

            target_candidates = global_name_index.get(
                target_name.lower(),
                set(),
            )

            # -------------------------------------------------------
            # Do not invent entities.
            #
            # If one endpoint genuinely cannot be resolved anywhere
            # in the extraction, retain it in the skipped list so
            # we can inspect it rather than silently losing it.
            # -------------------------------------------------------

            if not source_candidates or not target_candidates:

                reason_parts = []

                if not source_candidates:
                    reason_parts.append(
                        "source entity not found"
                    )

                if not target_candidates:
                    reason_parts.append(
                        "target entity not found"
                    )

                skipped_relationships.append({
                    "chunk_id": chunk.get("chunk_id", ""),
                    "source": rel["source"],
                    "relationship": rtype,
                    "target": rel["target"],
                    "reason": "; ".join(reason_parts),
                })

                continue

            # -------------------------------------------------------
            # Resolve every valid source/target combination.
            #
            # In normal cases each set contains exactly one entity.
            # -------------------------------------------------------

            for source_key in source_candidates:
                for target_key in target_candidates:

                    rel_key = (
                        f"{source_key}|"
                        f"{rtype}|"
                        f"{target_key}"
                    )

                    if rel_key not in relationships:
                        relationships[rel_key] = {
                            "source": source_key,
                            "relationship": rtype,
                            "target": target_key,
                            "source_mentions": [],
                        }

                    mention = {
                        **provenance,
                        "evidence": rel.get(
                            "evidence",
                            "",
                        ),
                    }

                    if mention not in relationships[
                        rel_key
                    ]["source_mentions"]:

                        relationships[
                            rel_key
                        ]["source_mentions"].append(
                            mention
                        )

    # ===============================================================
    # FINAL GRAPH
    # ===============================================================

    graph = {
        "version": "1.0",
        "entities": list(entities.values()),
        "relationships": list(relationships.values()),
        "validation_errors": validation_errors,
    }

    # ===============================================================
    # WRITE graph_data.json
    # ===============================================================

    GRAPH_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    GRAPH_FILE.write_text(
        json.dumps(
            graph,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # ===============================================================
    # REPORT
    # ===============================================================

    print()
    print("=" * 60)
    print("GRAPH CONSTRUCTION COMPLETED")
    print("=" * 60)
    print(f"Input chunks:             {len(chunks)}")
    print(f"Entities:                 {len(graph['entities'])}")
    print(f"Relationships:            {len(graph['relationships'])}")
    print(f"Skipped relationships:    {len(skipped_relationships)}")
    print(f"Validation errors:        {len(validation_errors)}")
    print(f"Output:                   {GRAPH_FILE}")
    print("=" * 60)

    # ---------------------------------------------------------------
    # Print unresolved relationships for inspection.
    # ---------------------------------------------------------------

    if skipped_relationships:
        print()
        print(
            f"FIRST {min(50, len(skipped_relationships))} "
            "UNRESOLVED RELATIONSHIPS"
        )
        print("-" * 60)

        for item in skipped_relationships[:50]:
            print(
                f"{item['chunk_id']} | "
                f"{item['source']} "
                f"-[{item['relationship']}]-> "
                f"{item['target']} | "
                f"{item['reason']}"
            )

        if len(skipped_relationships) > 50:
            print(
                f"... and "
                f"{len(skipped_relationships) - 50} more."
            )


if __name__ == "__main__":
    main()