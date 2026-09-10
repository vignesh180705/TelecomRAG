"""Load and index the canonical entity registry."""
import json
from pathlib import Path

try:
    from config import ENTITY_REGISTRY_PATH
except ImportError:
    from .config import ENTITY_REGISTRY_PATH


def load_entities(path=ENTITY_REGISTRY_PATH):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data["entities"] if isinstance(data, dict) else data


def build_entity_map(entities):
    return {e["entity_id"]: e for e in entities}
