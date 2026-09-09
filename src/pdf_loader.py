from pathlib import Path
import hashlib
import pymupdf

def document_id(path):
    return hashlib.sha1(Path(path).name.encode("utf-8")).hexdigest()[:16]

def load_pdf(path, max_pages=0):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    doc = pymupdf.open(path)
    try:
        pages = []
        limit = len(doc) if max_pages <= 0 else min(max_pages, len(doc))
        for i in range(limit):
            text = doc.load_page(i).get_text("text") or ""
            text = "\n".join(x.rstrip() for x in text.splitlines()).strip()
            pages.append({"page": i + 1, "text": text})
        return {
            "document_id": document_id(path),
            "filename": path.name,
            "page_count": len(doc),
            "pages": pages,
        }
    finally:
        doc.close()
