import fitz
from pathlib import Path

pdf_dir = Path("../data/pdfs")

documents = []

for pdf_path in pdf_dir.glob("*.pdf"):
    print(f"Reading {pdf_path.name}...")

    doc = fitz.open(pdf_path)

    full_text = ""
    for page_num, page in enumerate(doc):
        text = page.get_text()
        full_text += text + "\n"

    documents.append({
        "filename": pdf_path.name,
        "text": full_text
    })

    print(f"  ✓ {doc.page_count} pages extracted")

print(f"\nLoaded {len(documents)} documents.")

print("\nPreview:\n")
print(documents[0]["text"][:1000])