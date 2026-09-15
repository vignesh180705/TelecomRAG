import re
import unicodedata


def normalize_name(name: str) -> str:
    value = unicodedata.normalize("NFKC", name).strip()
    value = re.sub(r"\s+", " ", value)
    return value


def entity_key(name: str, entity_type: str) -> str:
    normalized = normalize_name(name).lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")
    return f"{entity_type.lower()}:{normalized}"


def merge_entity(store, entity, provenance):
    name = normalize_name(
    entity.get("name") or entity.get("canonical_name", "")
)

    et = entity["entity_type"]
    key = entity_key(name, et)

    if key not in store:
        store[key] = {
            "entity_id": key,
            "canonical_name": name,
            "entity_type": et,
            "aliases": [],
            "description": entity.get("description", ""),
            "domains": [],
            "properties": {},
            "source_mentions": [],
        }

    item = store[key]

    description = entity.get("description", "").strip()
    if description and not item["description"]:
        item["description"] = description

    evidence = entity.get("evidence", "").strip()

    mention = {
        "document": provenance["document"],
        "document_file": provenance["document_file"],
        "page": provenance["page"],
        "clause": provenance.get("clause", ""),
        "section_title": provenance.get("section_title", ""),
        "chunk_id": provenance["chunk_id"],
        "evidence": evidence,
    }

    if mention not in item["source_mentions"]:
        item["source_mentions"].append(mention)

    return key


def add_aliases(store):
    for item in store.values():
        aliases = set(item["aliases"])
        canonical = item["canonical_name"]

        for mention in item["source_mentions"]:
            evidence = mention.get("evidence", "")
            # Alias discovery is intentionally conservative; do not manufacture
            # aliases from arbitrary evidence.
            if evidence == canonical:
                continue

        item["aliases"] = sorted(a for a in aliases if a != canonical)
