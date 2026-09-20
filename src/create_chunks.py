import json
import sys
from pathlib import Path

from config import PDF_DIR, CHUNKS_FILE, CHUNK_SIZE, CHUNK_OVERLAP
from pdf_loader import load_pdf_pages
from chunker import make_chunks


def main():
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(PDF_DIR.rglob("*.pdf"))

    if not pdfs:
        print(f"No PDFs found in {PDF_DIR}")
        sys.exit(1)

    all_chunks = []
    total_page_count=0
    total_doc_count=0
    for pdf in pdfs:
        print(f"Reading {pdf.name}")
        page_count = 0
        for page in load_pdf_pages(pdf):
            page_count += 1
            all_chunks.extend(
                make_chunks(page, CHUNK_SIZE, CHUNK_OVERLAP)
            )
        print(f"  pages={page_count}")
        total_page_count+=page_count
        total_doc_count+=1
    payload = {
        "version": "1.0",
        "chunk_count": len(all_chunks),
        "documents": sorted({c["document"] for c in all_chunks}),
        "chunks": all_chunks,
    }

    CHUNKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHUNKS_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Wrote {len(all_chunks)} chunks to {CHUNKS_FILE}")
    print("Total Documents:",total_doc_count)
    print("Total Pages:",total_page_count)

if __name__ == "__main__":
    main()
