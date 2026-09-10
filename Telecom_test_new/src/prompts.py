"""Prompts for source-grounded relationship extraction."""


def build_relationship_prompt(
    chunk,
    candidates,
    allowed_relationships,
):
    """
    Build a compact prompt for relationship extraction.

    Only entities detected in the current chunk and potentially
    applicable relationship types are supplied to the model.
    """

    candidate_lines = []

    for entity in candidates or []:
      description = entity.get("description") or ""
      aliases = entity.get("aliases") or []

      if not isinstance(description, str):
          description = str(description)

      if not isinstance(aliases, list):
          aliases = [str(aliases)]

      candidate_lines.append(
          f"- entity_id: {entity.get('entity_id') or ''}\n"
          f"  canonical_name: {entity.get('canonical_name') or ''}\n"
          f"  entity_type: {entity.get('entity_type') or ''}\n"
          f"  description: {description[:300]}\n"
          f"  aliases: {aliases[:5]}"
      )

    candidate_text = (
        "\n".join(candidate_lines)
        if candidate_lines
        else "NONE"
    )

    relationship_lines = []

    for relation in allowed_relationships or []:
        relationship_lines.append(
            f"- {relation.get('relationship_type')}: "
            f"{relation.get('description', '')}\n"
            f"  source_types: "
            f"{relation.get('source_types', [])}\n"
            f"  target_types: "
            f"{relation.get('target_types', [])}"
        )

    relationship_text = (
        "\n".join(relationship_lines)
        if relationship_lines
        else "NONE"
    )

    return f"""
You are extracting relationships from an O-RAN technical document.

Your task is to identify ONLY relationships explicitly supported
by the supplied source text.

STRICT RULES:

1. Use ONLY entity IDs from CANDIDATE ENTITIES.
2. NEVER invent an entity.
3. Use ONLY relationship types from ALLOWED RELATIONSHIPS.
4. NEVER invent a relationship type.
5. Do NOT create a relationship merely because two entities
   appear in the same chunk.
6. The relationship must be explicitly supported by the text.
7. Preserve relationship direction.
8. Every accepted relationship MUST contain evidence copied
   directly from the source text.
9. The evidence must be sufficient to justify the relationship.
10. Confidence must be a number between 0 and 1.
11. If there are no explicit relationships, return an empty list.

DOCUMENT:
{chunk.get("source", "")}

PAGE:
{chunk.get("page", "")}

CHUNK ID:
{chunk.get("id", "")}

SOURCE TEXT:
{chunk.get("text", "")}

CANDIDATE ENTITIES:
{candidate_text}

ALLOWED RELATIONSHIPS:
{relationship_text}

RETURN ONLY JSON.

Expected format:

{{
  "relationships": [
    {{
      "source_entity_id": "ENTITY_ID",
      "relationship_type": "RELATIONSHIP_TYPE",
      "target_entity_id": "ENTITY_ID",
      "evidence": "exact text from source",
      "confidence": 0.95
    }}
  ]
}}

If there are no valid relationships:

{{
  "relationships": []
}}
""".strip()