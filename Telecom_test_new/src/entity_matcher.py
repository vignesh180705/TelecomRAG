"""Closed-world entity matching utilities."""

import re
from typing import Any, Dict, List


def normalize(text: str) -> str:
    """
    Normalize text for robust entity matching.

    Examples:
        Near-RT RIC -> near rt ric
        Near_RT_RIC -> near rt ric
        O-DU        -> o du
    """

    text = text.lower()

    # Treat common separators as spaces.
    text = re.sub(r"[-_/]", " ", text)

    # Remove remaining punctuation.
    text = re.sub(r"[^\w\s]", " ", text)

    # Collapse whitespace.
    text = re.sub(r"\s+", " ", text).strip()

    return text


def build_patterns(
    entities: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Build a normalized entity-name index.

    The entity registry is closed-world:
    this function never creates entities.
    """

    patterns: Dict[str, List[Dict[str, Any]]] = {}

    for entity in entities:

        names = []

        canonical_name = entity.get("canonical_name")

        if canonical_name:
            names.append(canonical_name)

        aliases = entity.get("aliases", [])

        if aliases:
            names.extend(aliases)

        for name in names:

            normalized = normalize(name)

            if not normalized:
                continue

            patterns.setdefault(normalized, [])

            # Avoid duplicate entity entries.
            entity_id = entity.get("entity_id")

            existing_ids = {
                e.get("entity_id")
                for e in patterns[normalized]
            }

            if entity_id not in existing_ids:
                patterns[normalized].append(entity)

    return patterns


def find_candidates(
    text: str,
    patterns: Dict[str, List[Dict[str, Any]]],
    entities: List[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Find canonical entities explicitly mentioned in a chunk.

    This is a CLOSED-WORLD matcher.

    It can only return entities that already exist in the
    canonical entity registry.

    Longer entity names are preferred over shorter overlapping
    names.

    Example:

        "Near-RT RIC"

    prefers:

        Near-RT RIC

    over:

        RIC
    """

    normalized_text = normalize(text)

    candidates = []

    for normalized_name, entities in patterns.items():

        if not normalized_name:
            continue

        pattern = (
            r"(?<!\w)"
            + re.escape(normalized_name)
            + r"(?!\w)"
        )

        for match in re.finditer(
            pattern,
            normalized_text,
        ):

            candidates.append(
                {
                    "start": match.start(),
                    "end": match.end(),
                    "name": normalized_name,
                    "entities": entities,
                }
            )

    # Longer mentions first.
    candidates.sort(
        key=lambda candidate: (
            -(candidate["end"] - candidate["start"]),
            candidate["start"],
        )
    )

    accepted_spans = []
    matches: Dict[str, Dict[str, Any]] = {}

    for candidate in candidates:

        start = candidate["start"]
        end = candidate["end"]

        # Ignore shorter matches contained inside a longer
        # already-accepted match.
        overlaps = False

        for accepted_start, accepted_end in accepted_spans:

            if (
                start >= accepted_start
                and end <= accepted_end
            ):
                overlaps = True
                break

        if overlaps:
            continue

        accepted_spans.append(
            (start, end)
        )

        for entity in candidate["entities"]:

            entity_id = entity.get("entity_id")

            if entity_id:
                matches[entity_id] = entity

    return list(matches.values())


def match_entities(
    text: str,
    patterns: Dict[str, List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """
    Backwards-compatible alias for find_candidates().
    """

    return find_candidates(
        text,
        patterns,
    )