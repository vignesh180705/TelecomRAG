import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    src = Path(__file__).resolve().parent
    for name in ("prepare_chunks.py", "extract_groq.py", "load_neo4j.py"):
        subprocess.run([sys.executable, str(src / name)], check=True)
