import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
PDF_DIR = DATA_DIR / "pdfs"
OUTPUT_DIR = PROJECT_ROOT / "output"

CHUNKS_PATH = OUTPUT_DIR / "chunks.json"
ENTITY_REGISTRY_PATH = OUTPUT_DIR / "entity_registry_v4_canonical.json"
RELATIONSHIP_REGISTRY_PATH = OUTPUT_DIR / "relationship_registry_v2_source_grounded.json"
RELATIONSHIP_CSV_PATH = OUTPUT_DIR / "relationship_registry_v2_source_grounded.csv"

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLM_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1")

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1400"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "250"))
MIN_ENTITY_MENTIONS = int(os.getenv("MIN_ENTITY_MENTIONS", "2"))
MAX_CANDIDATES_PER_CHUNK = int(os.getenv("MAX_CANDIDATES_PER_CHUNK", "35"))
MIN_RELATION_CONFIDENCE = float(os.getenv("MIN_RELATION_CONFIDENCE", "0.75"))


def ensure_output_dirs():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
