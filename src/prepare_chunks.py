import json
from pathlib import Path
from config import PDF_DIR, DOCUMENTS_FILE, CHUNKS_FILE, CHUNK_SIZE, CHUNK_OVERLAP, MAX_PAGES_PER_PDF
from pdf_loader import load_pdf
from chunker import make_chunks

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PDF_DIR = BASE_DIR / "data" / "pdfs"


def write_jsonl(path, rows):
    with Path(path).open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

def main():
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    if not pdfs:
        raise RuntimeError(f"No PDFs found in {PDF_DIR}")

    documents, all_chunks = [], []
    print("=" * 70)
    print("STAGE 1: PDF -> CHUNKS")
    print("=" * 70)

    for pdf in pdfs:
        print(f"[PDF] {pdf.name}")
        doc = load_pdf(pdf, MAX_PAGES_PER_PDF)
        chunks = make_chunks(doc, CHUNK_SIZE, CHUNK_OVERLAP)
        documents.append({
            "document_id": doc["document_id"],
            "filename": doc["filename"],
            "page_count": doc["page_count"],
            "pages_loaded": len(doc["pages"]),
            "chunks_created": len(chunks),
        })
        all_chunks.extend(chunks)
        print(f"      pages={len(doc['pages'])}/{doc['page_count']} chunks={len(chunks)}")

    write_jsonl(DOCUMENTS_FILE, documents)
    write_jsonl(CHUNKS_FILE, all_chunks)
    print(f"[OK] {DOCUMENTS_FILE}")
    print(f"[OK] {CHUNKS_FILE}")
    print(f"[OK] PDFs={len(pdfs)} chunks={len(all_chunks)}")
    print("No Groq or Neo4j calls were made.")

if __name__ == "__main__":
    main()
