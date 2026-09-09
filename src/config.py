import os
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

SCHEMA_FILE = os.getenv("SCHEMA_FILE")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")
AURA_INSTANCEID = os.getenv("AURA_INSTANCEID")
JSON_FILE = os.getenv("SCHEMA_FILE")
PDF_DIR = os.getenv("PDF_DIR")
OUTPUT_DIR = os.getenv("OUTPUT_DIR")
MAX_PAGES_PER_PDF = int(os.getenv("MAX_PAGES_PER_PDF", "0"))
MAX_CHUNKS = int(os.getenv("MAX_CHUNKS", "0"))

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000"))
XAI_API_KEY = os.getenv("XAI_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
REQUEST_DELAY_SECONDS = 2


if not NEO4J_URI:
    raise ValueError("NEO4J_URI is not set")

if not NEO4J_USERNAME:
    raise ValueError("NEO4J_USERNAME is not set")

if not NEO4J_PASSWORD:
    raise ValueError("NEO4J_PASSWORD is not set")

