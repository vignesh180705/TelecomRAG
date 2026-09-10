"""Relationship registry construction and deduplication."""

from typing import Any, Dict, List, Tuple


def add_mentions(
    edges: Dict[Tuple[str, str, str], Dict[str, Any]],
    mentions: List[Dict[str, Any]],
    entity_map: Dict[str, Dict[str, Any]],
) -> None:
    """
    Add validated relationship mentions to the edge registry.

    Multiple mentions of the same canonical edge are preserved
    as separate evidence records.
    """

    for mention in mentions:
        source_id = mention.get("source_entity_id")
        target_id = mention.get("target_entity_id")
        relationship_type = mention.get("relationship_type")

        if not source_id or not target_id or not relationship_type:
            continue

        # Make sure both entities exist.
        if source_id not in entity_map:
            continue

        if target_id not in entity_map:
            continue

        edge_key = (
            source_id,
            relationship_type,
            target_id,
        )

        if edge_key not in edges:
            edges[edge_key] = {
                "source_entity_id": source_id,
                "relationship_type": relationship_type,
                "target_entity_id": target_id,
                "evidence": [],
            }

        evidence_record = {
            "text": mention.get("evidence") or "",
            "confidence": mention.get("confidence", 0.0),
            "source": mention.get("source"),
            "page": mention.get("page"),
            "chunk_id": mention.get("chunk_id"),
        }

        # Don't add completely empty evidence.
        if not evidence_record["text"]:
            continue

        edges[edge_key]["evidence"].append(
            evidence_record
        )


def finalize(
    edges: Dict[Tuple[str, str, str], Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Finalize the relationship registry.

    Deduplicates identical evidence records while preserving
    multiple independent pieces of evidence for the same edge.
    """

    records = []

    for edge in edges.values():

        unique_evidence = []
        seen_evidence = set()

        for evidence in edge.get("evidence", []):

            key = (
                evidence.get("source"),
                evidence.get("page"),
                evidence.get("chunk_id"),
                evidence.get("text"),
            )

            if key in seen_evidence:
                continue

            seen_evidence.add(key)
            unique_evidence.append(evidence)

        if not unique_evidence:
            continue

        # Use the highest confidence among supporting evidence.
        confidence = max(
            (
                float(ev.get("confidence", 0.0) or 0.0)
                for ev in unique_evidence
            ),
            default=0.0,
        )

        records.append(
            {
                "source_entity_id": edge["source_entity_id"],
                "relationship_type": edge["relationship_type"],
                "target_entity_id": edge["target_entity_id"],
                "confidence": confidence,
                "evidence": unique_evidence,
            }
        )

    return records

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

def save_json(
    records: List[Dict[str, Any]],
    path: str,
    stats: Dict[str, Any] | None = None,
) -> None:
    """Save relationship registry and extraction statistics as JSON."""

    output_path = Path(path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output = {
        "stats": stats or {},
        "relationships": records,
    }

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            output,
            f,
            indent=2,
            ensure_ascii=False,
        )


def save_csv(
    records: List[Dict[str, Any]],
    path: str,
) -> None:
    """Save relationship registry as CSV."""

    output_path = Path(path)
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    rows = []

    for record in records:
        rows.append(
            {
                "source_entity_id": record.get(
                    "source_entity_id"
                ),
                "relationship_type": record.get(
                    "relationship_type"
                ),
                "target_entity_id": record.get(
                    "target_entity_id"
                ),
                "confidence": record.get(
                    "confidence"
                ),
                "evidence_count": len(
                    record.get("evidence", [])
                ),
                "evidence": " || ".join(
                    ev.get("text", "")
                    for ev in record.get("evidence", [])
                ),
            }
        )

    fieldnames = [
        "source_entity_id",
        "relationship_type",
        "target_entity_id",
        "confidence",
        "evidence_count",
        "evidence",
    ]

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)