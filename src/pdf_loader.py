from pathlib import Path
import fitz  # PyMuPDF


def specification_name(pdf_path: Path) -> str:
    """Convert TS_23.501.pdf -> TS 23.501."""
    return pdf_path.stem.replace("_", " ")


def load_pdf_pages(pdf_path: Path):
    """
    Yield one record per PDF page. Page numbering is 1-based.
    The PDF page text is kept intact here; chunking happens later.
    """
    doc = fitz.open(pdf_path)
    try:
        for page_index, page in enumerate(doc):
            text = page.get_text("text") or ""
            yield {
                "document": specification_name(pdf_path),
                "document_file": pdf_path.name,
                "page": page_index + 1,
                "text": text,
            }
    finally:
        doc.close()
