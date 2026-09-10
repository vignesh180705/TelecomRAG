"""Extract page-aware, provenance-preserving chunks from PDFs."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import fitz

try:
    from config import PDF_DIR, CHUNKS_PATH, CHUNK_SIZE, CHUNK_OVERLAP, ensure_output_dirs
except ImportError:
    from .config import PDF_DIR, CHUNKS_PATH, CHUNK_SIZE, CHUNK_OVERLAP, ensure_output_dirs


def clean_text(text: str) -> str:
    return re.sub(r"\\s+", " ", text or "").strip()


def chunk_page(text: str, size: int, overlap: int):
    start = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        value = text[start:end].strip()
        if value:
            yield start, end, value
        if end >= n:
            break
        start = max(end - overlap, start + 1)


def build_chunks(pdf_dir: Path):
    chunks = []
    for pdf_path in sorted(pdf_dir.glob("*.pdf")):
        if pdf_path.name == "2407.06245v2.pdf":
            continue
        doc = fitz.open(pdf_path)
        try:
            for page_number, page in enumerate(doc, start=1):
                text = clean_text(page.get_text("text"))
                for chunk_index, (start, end, chunk_text) in enumerate(
                    chunk_page(text, CHUNK_SIZE, CHUNK_OVERLAP)
                ):
                    chunk_id = hashlib.sha1(
                        f"{pdf_path.name}|{page_number}|{start}|{end}|{chunk_text}".encode()
                    ).hexdigest()[:16]
                    chunks.append({
                        "id": chunk_id,
                        "source": pdf_path.name,
                        "page": page_number,
                        "chunk_index": chunk_index,
                        "text": chunk_text,
                    })
        finally:
            doc.close()
    return chunks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf-dir", default=str(PDF_DIR))
    parser.add_argument("--output", default=str(CHUNKS_PATH))
    args = parser.parse_args()
    ensure_output_dirs()
    chunks = build_chunks(Path(args.pdf_dir))
    Path(args.output).write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(chunks)} chunks to {args.output}")


if __name__ == "__main__":
    main()
