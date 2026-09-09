import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


SCHEMA_FILE = BASE_DIR / "schema" / "3gpp_schema.json"


PDF_DIR = BASE_DIR / os.getenv("PDF_DIR", "pdfs")

OUTPUT_DIR = BASE_DIR / os.getenv("OUTPUT_DIR", "output")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "256"))
MAX_PAGES_PER_PDF = int(os.getenv("MAX_PAGES_PER_PDF", "0"))
MAX_CHUNKS = int(os.getenv("MAX_CHUNKS", "0"))
REQUEST_DELAY_SECONDS = float(os.getenv("REQUEST_DELAY_SECONDS", "0.0"))

DOCUMENTS_FILE = OUTPUT_DIR / "documents.jsonl"
CHUNKS_FILE = OUTPUT_DIR / "chunks.jsonl"
EXTRACTIONS_FILE = OUTPUT_DIR / "extractions.jsonl"

for p in (PDF_DIR, OUTPUT_DIR, SCHEMA_FILE.parent):
    p.mkdir(parents=True, exist_ok=True)

def validate_config(require_groq=False, require_neo4j=False):
    missing = []
    if not SCHEMA_FILE.exists():
        missing.append(f"SCHEMA_FILE ({SCHEMA_FILE})")
    if require_groq and (not GROQ_API_KEY or "YOUR_" in GROQ_API_KEY):
        missing.append("GROQ_API_KEY")
    if require_neo4j:
        for name, value in {"NEO4J_URI": NEO4J_URI, "NEO4J_PASSWORD": NEO4J_PASSWORD}.items():
            if not value or "YOUR_" in value:
                missing.append(name)
    if missing:
        raise RuntimeError("Missing configuration: " + ", ".join(missing))
