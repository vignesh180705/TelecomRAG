from pathlib import Path
import os
from dotenv import load_dotenv


# ============================================================
# PROJECT ROOT
# ============================================================

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)


# ============================================================
# DATA PATHS
# ============================================================

PDF_DIR = ROOT / "data" / "pdfs"

CHUNKS_FILE = ROOT / "data" / "chunks" / "chunks.json"

#RAW_EXTRACTION_FILE = ROOT / "data" / "extraction" / "extraction_raw.json"
RAW_EXTRACTION_FILE = ROOT / "out_copy" / "final_extraction_combined_sorted.json"

#VALIDATED_EXTRACTION_FILE = (
#    ROOT / "out" / "graph_extraction_with_relationships_v2.json"
#)

VALIDATED_EXTRACTION_FILE = (
    ROOT / "out_copy" / "final_extraction_combined_sorted.json"
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
    "error",
)

NEO4J_USERNAME = os.getenv(
    "NEO4J_USERNAME",
    "error",
)

NEO4J_PASSWORD = os.getenv(
    "NEO4J_PASSWORD",
    "error",
)
NEO4J_DATABASE = os.getenv(
    "NEO4J_DATABASE",
    "error",
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

print("Loaded database:", repr(NEO4J_DATABASE))
print("Loaded .env from:", ROOT)