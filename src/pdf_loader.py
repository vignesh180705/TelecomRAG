from pathlib import Path
import hashlib
import fitz


def document_id(path: Path) -> str:

    return hashlib.sha1(
        path.name.encode("utf-8")
    ).hexdigest()[:16]


def load_pdf(path, max_pages=0):

    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"PDF not found: {path}"
        )

    doc = fitz.open(path)

    pages = []

    limit = (
        len(doc)
        if max_pages <= 0
        else min(max_pages, len(doc))
    )

    for i in range(limit):

        page = doc.load_page(i)

        text = page.get_text("text") or ""

        text = "\n".join(
            line.rstrip()
            for line in text.splitlines()
        ).strip()

        pages.append({
            "page": i + 1,
            "text": text,
        })

    return {
        "document_id": document_id(path),
        "filename": path.name,
        "page_count": len(doc),
        "pages": pages,
    }