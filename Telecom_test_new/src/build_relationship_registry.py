"""Run source-grounded relationship extraction over chunks.json."""

import argparse
import json
from collections import Counter
from pathlib import Path

try:
    from config import (
        CHUNKS_PATH,
        ENTITY_REGISTRY_PATH,
        RELATIONSHIP_REGISTRY_PATH,
        RELATIONSHIP_CSV_PATH,
    )
    from entity_registry import load_entities, build_entity_map
    from entity_matcher import build_patterns, match_entities
    from relationship_extractor import RelationshipExtractor
    from relationship_registry import add_mentions, finalize, save_json, save_csv

except ImportError:
    from .config import (
        CHUNKS_PATH,
        ENTITY_REGISTRY_PATH,
        RELATIONSHIP_REGISTRY_PATH,
        RELATIONSHIP_CSV_PATH,
    )
    from .entity_registry import load_entities, build_entity_map
    from .entity_matcher import build_patterns, match_entities
    from .relationship_extractor import RelationshipExtractor
    from .relationship_registry import add_mentions, finalize, save_json, save_csv


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--chunks",
        default=str(CHUNKS_PATH),
    )

    parser.add_argument(
        "--entities",
        default=str(ENTITY_REGISTRY_PATH),
    )

    parser.add_argument(
        "--output",
        default=str(RELATIONSHIP_REGISTRY_PATH),
    )

    parser.add_argument(
        "--output-csv",
        default=str(RELATIONSHIP_CSV_PATH),
    )

    parser.add_argument(
        "--limit-chunks",
        type=int,
        default=0,
    )

    args = parser.parse_args()

    # ---------------------------------------------------------
    # Load input data
    # ---------------------------------------------------------

    chunks = json.loads(
        Path(args.chunks).read_text(encoding="utf-8")
    )

    entities = load_entities(args.entities)

    # entity_id -> canonical entity
    entity_map = build_entity_map(entities)

    # Build regex/string matching patterns from the
    # canonical entity registry.
    patterns = build_patterns(entities)

    # Relationship extractor
    extractor = RelationshipExtractor(
        entities,
        patterns,
    )

    # ---------------------------------------------------------
    # Extraction state
    # ---------------------------------------------------------

    edges = {}
    stats = Counter()

    # ---------------------------------------------------------
    # Process chunks
    # ---------------------------------------------------------

    for index, chunk in enumerate(chunks):

        if args.limit_chunks and index >= args.limit_chunks:
            break

        stats["chunks_seen"] += 1

        text = chunk.get("text", "").strip()

        if not text:
            stats["chunks_skipped"] += 1
            stats["chunks_empty"] += 1
            continue

        # -----------------------------------------------------
        # Closed-world entity matching
        # -----------------------------------------------------

        matched_entities = match_entities(
            text,
            patterns,
        )

        print(
            f"Chunk {chunk['id']} | "
            f"matched_entities={len(matched_entities)} | "
            f"source={chunk['source']} | "
            f"page={chunk['page']}"
        )

        # Print the matched entities for debugging.
        if matched_entities:
            print(
                "  Entities:",
                ", ".join(
                    entity["canonical_name"]
                    for entity in matched_entities
                ),
            )

        # -----------------------------------------------------
        # Skip chunks with no known entities
        # -----------------------------------------------------

        if len(matched_entities) == 0:
            stats["chunks_skipped"] += 1
            stats["chunks_no_entities"] += 1
            continue

        # At this point the chunk contains at least one
        # canonical entity from our closed-world registry.
        stats["chunks_sent_to_llm"] += 1

        # -----------------------------------------------------
        # LLM relationship extraction
        # -----------------------------------------------------

        try:
            mentions, local_stats = extractor.extract_from_chunk(
                chunk
            )

        except Exception as exc:
            stats["llm_errors"] += 1

            print(
                f"ERROR "
                f"{chunk['source']} "
                f"p{chunk['page']} "
                f"{chunk['id']}: "
                f"{exc}"
            )

            continue

        # -----------------------------------------------------
        # Handle extractor-level skip
        # -----------------------------------------------------

        if local_stats.get("skipped"):
            stats["extractor_skipped"] += 1
            continue

        # -----------------------------------------------------
        # Collect extraction statistics
        # -----------------------------------------------------

        stats["raw_relation_mentions"] += local_stats.get(
            "raw",
            0,
        )

        stats["accepted_relation_mentions"] += len(
            mentions
        )

        # -----------------------------------------------------
        # Add validated relationships to registry
        # -----------------------------------------------------

        add_mentions(
            edges,
            mentions,
            entity_map,
        )

        # -----------------------------------------------------
        # Progress logging
        # -----------------------------------------------------

        if (index + 1) % 25 == 0:
            print(
                f"Processed {index + 1}/{len(chunks)} chunks; "
                f"edges={len(edges)}"
            )

    # ---------------------------------------------------------
    # Finalize relationship registry
    # ---------------------------------------------------------

    records = finalize(edges)

    save_json(
        records,
        args.output,
        stats,
    )

    save_csv(
        records,
        args.output_csv,
    )

    # ---------------------------------------------------------
    # Final summary
    # ---------------------------------------------------------

    print(
        json.dumps(
            {
                "chunks_seen": stats["chunks_seen"],
                "chunks_sent_to_llm": stats[
                    "chunks_sent_to_llm"
                ],
                "chunks_skipped": stats[
                    "chunks_skipped"
                ],
                "chunks_no_entities": stats[
                    "chunks_no_entities"
                ],
                "extractor_skipped": stats[
                    "extractor_skipped"
                ],
                "llm_errors": stats[
                    "llm_errors"
                ],
                "raw_relation_mentions": stats[
                    "raw_relation_mentions"
                ],
                "accepted_relation_mentions": stats[
                    "accepted_relation_mentions"
                ],
                "relationship_instances": len(records),
                "relationship_types": sorted(
                    {
                        r["relationship_type"]
                        for r in records
                    }
                ),
                "output": args.output,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()