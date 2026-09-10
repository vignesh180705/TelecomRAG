from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]

PDF_DIR = ROOT / "data" / "pdfs"
CHUNKS_FILE = ROOT / "data" / "chunks" / "chunks.json"
RAW_EXTRACTION_FILE = ROOT / "data" / "extraction" / "extraction_raw.json"
VALIDATED_EXTRACTION_FILE = ROOT / "data" / "extraction" / "extraction_validated.json"
GRAPH_FILE = ROOT / "data" / "graph" / "graph_data.json"
SCHEMA_FILE = ROOT / "schema" / "3gpp_schema_fixed.json"

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")

VALIDATED_EXTRACTION_FILE = ROOT / "out" / "graph_extraction_with_relationships.json"

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

# Chunking defaults. Page boundaries are never crossed.
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "250"))

ALLOWED_ENTITY_TYPES = [
    "NETWORK_FUNCTION",
    "NETWORK_ENTITY",
    "INTERFACE",
    "PROTOCOL",
    "PROCEDURE",
    "STATE",
    "PARAMETER",
    "INFORMATION_ELEMENT",
    "QOS_CONCEPT",
    "SECURITY_CONCEPT",
    "NETWORK_SLICE",
    "SERVICE",
    "USE_CASE",
    "REQUIREMENT",
    "PERFORMANCE_METRIC",
    "RESOURCE",
    "APPLICATION",
    "ANALYTICS_CONCEPT",
    "CONCEPT",
]
