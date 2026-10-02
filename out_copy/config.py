from pathlib import Path
import os


# ============================================================
# PROJECT ROOT
# ============================================================

ROOT = Path(__file__).resolve().parents[1]


# ============================================================
# DATA PATHS
# ============================================================

PDF_DIR = ROOT / "data" / "pdfs"

CHUNKS_FILE = ROOT / "data" / "chunks" / "chunks.json"

#RAW_EXTRACTION_FILE = ROOT / "data" / "extraction" / "extraction_raw.json"
RAW_EXTRACTION_FILE = ROOT / "out_copy" / "3gpp_ex_new.json"

#VALIDATED_EXTRACTION_FILE = (
#    ROOT / "out" / "graph_extraction_with_relationships_v2.json"
#)

VALIDATED_EXTRACTION_FILE = (
    ROOT / "out_copy" / "3gpp_ex_new.json"
)

GRAPH_FILE = ROOT / "out_copy" / "graph_data.json"

SCHEMA_FILE = ROOT / "schema" / "3gpp_schema.json"


# ============================================================
# OLLAMA
# ============================================================

OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://localhost:11434",
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen2.5:14b",
)


# ============================================================
# NEO4J
# ============================================================

NEO4J_URI = os.getenv(
    "NEO4J_URI",
    "neo4j+s://d1bdd9d0.databases.neo4j.io",
)

NEO4J_USERNAME = os.getenv(
    "NEO4J_USERNAME",
    "d1bdd9d0",
)

NEO4J_PASSWORD = os.getenv(
    "NEO4J_PASSWORD",
    "Jl-HyytoHNh71uKrzLCECs7CeQS6mcuttUgwxdvBEFc",
)
NEO4J_DATABASE = os.getenv(
    "NEO4J_DATABASE",
    "d1bdd9d0",
)

# ============================================================
# CHUNKING
# ============================================================

CHUNK_SIZE = int(
    os.getenv("CHUNK_SIZE", "1800")
)

CHUNK_OVERLAP = int(
    os.getenv("CHUNK_OVERLAP", "250")
)


# ============================================================
# ALLOWED ENTITY TYPES
# ============================================================

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