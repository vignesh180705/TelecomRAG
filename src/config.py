from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


SCHEMA_FILE = BASE_DIR / "schema" / "3gpp_schema.json"


PDF_DIR = BASE_DIR / os.getenv("PDF_DIR", "pdfs")

OUTPUT_DIR = BASE_DIR / os.getenv("OUTPUT_DIR", "output")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

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
