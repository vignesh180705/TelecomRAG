import json
from pathlib import Path

from page_extractor import extract_pages
from parser import extract_document_metadata, extract_sections
from chunker import chunk_document


# ============================================================
# DIRECTORIES
# ============================================================

DOCUMENT_DIR = Path("data/pdfs")

PAGE_DIR = Path("vector_data/pages")
PARSED_DIR = Path("vector_data/parsed")
CHUNK_DIR = Path("vector_data/chunks")


# ============================================================
# JSON UTILITY
# ============================================================

def save_json(data, path):

    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )


# ============================================================
# PROCESS ONE PDF
# ============================================================

def process_document(pdf_path):

    print("\n" + "=" * 70)

    print(
        f"Processing: {pdf_path.name}"
    )

    print("=" * 70)


    # ========================================================
    # STEP 1
    # PAGE EXTRACTION
    # ========================================================

    print("\n[1/3] Extracting pages...")

    page_data = extract_pages(
        pdf_path
    )

    page_output = (
        PAGE_DIR
        / f"{pdf_path.stem}_pages.json"
    )

    save_json(
        page_data,
        page_output
    )

    print(
        f"Pages extracted: "
        f"{page_data['page_count']}"
    )

    print(
        f"TOC pages: "
        f"{page_data['toc_pages']}"
    )

    print(
        f"Repeated header/footer lines: "
        f"{len(page_data['repeated_lines'])}"
    )


    # ========================================================
    # STEP 2
    # DOCUMENT METADATA
    # ========================================================

    print("\n[2/3] Parsing document structure...")

    # Combine cleaned page text.
    #
    # The parser needs the page boundaries because section
    # start/end pages must be preserved.
    pages = []

    for page in page_data["pages"]:

        pages.append({

            "page":
                page["page_number"],

            "text":
                page["text"]
        })


    # ========================================================
    # DOCUMENT METADATA
    # ========================================================

    combined_text = "\n".join(
        page["text"]
        for page in pages[:10]
    )

    metadata = extract_document_metadata(
        pdf_path.name,
        combined_text
    )


    # ========================================================
    # SECTION EXTRACTION
    # ========================================================

    sections = extract_sections(
        pages,
        set(
            page_data["toc_pages"]
        )
    )


    # Add document metadata to sections

    document_id = pdf_path.stem

    for section in sections:

        section["document_id"] = (
            document_id
        )

        section["filename"] = (
            pdf_path.name
        )

        section["document_number"] = (
            metadata["document_number"]
        )

        section["document_type"] = (
            metadata["document_type"]
        )

        section["version"] = (
            metadata["version"]
        )

        section["release"] = (
            metadata["release"]
        )


    # ========================================================
    # CREATE PARSED DOCUMENT
    # ========================================================

    document = {

        "document_id":
            document_id,

        "filename":
            pdf_path.name,

        "page_count":
            page_data["page_count"],

        "document_number":
            metadata["document_number"],

        "document_type":
            metadata["document_type"],

        "version":
            metadata["version"],

        "release":
            metadata["release"],

        "toc_pages":
            page_data["toc_pages"],

        "sections":
            sections
    }


    # Save parsed JSON

    parsed_output = (
        PARSED_DIR
        / f"{pdf_path.stem}.json"
    )

    save_json(
        document,
        parsed_output
    )


    print(
        f"Document number: "
        f"{document['document_number']}"
    )

    print(
        f"Document type: "
        f"{document['document_type']}"
    )

    print(
        f"Version: "
        f"{document['version']}"
    )

    print(
        f"Release: "
        f"{document['release']}"
    )

    print(
        f"Sections detected: "
        f"{len(sections)}"
    )


    # ========================================================
    # STEP 3
    # CHUNKING
    # ========================================================

    print("\n[3/3] Creating chunks...")

    chunks = chunk_document(
        document
    )


    # Save chunks for this document

    chunk_output = (
        CHUNK_DIR
        / f"{pdf_path.stem}_chunks.json"
    )

    save_json(
        chunks,
        chunk_output
    )


    print(
        f"Chunks created: "
        f"{len(chunks)}"
    )


    # ========================================================
    # CHUNK STATISTICS
    # ========================================================

    if chunks:

        token_counts = [
            chunk["token_count"]
            for chunk in chunks
        ]

        print(
            f"Minimum tokens: "
            f"{min(token_counts)}"
        )

        print(
            f"Maximum tokens: "
            f"{max(token_counts)}"
        )

        print(
            f"Average tokens: "
            f"{sum(token_counts) / len(token_counts):.1f}"
        )


    return chunks


# ============================================================
# PROCESS ALL PDFs
# ============================================================

def process_all_documents():

    # Create directories

    PAGE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    PARSED_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    CHUNK_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    # Find PDFs

    pdf_files = sorted(
        DOCUMENT_DIR.glob("*.pdf")
    )


    if not pdf_files:

        print(
            "No PDF files found in "
            f"{DOCUMENT_DIR}"
        )

        return


    print(
        f"Found {len(pdf_files)} PDF files."
    )


    all_chunks = []


    # ========================================================
    # PROCESS EACH DOCUMENT
    # ========================================================

    for pdf_path in pdf_files:

        try:

            chunks = process_document(
                pdf_path
            )

            all_chunks.extend(
                chunks
            )

        except Exception as e:

            print(
                f"\nERROR processing "
                f"{pdf_path.name}"
            )

            print(
                f"{type(e).__name__}: {e}"
            )

            # Continue with remaining PDFs
            continue


    # ========================================================
    # GLOBAL CHUNK INDEX
    # ========================================================

    for index, chunk in enumerate(
        all_chunks
    ):

        chunk[
            "global_chunk_index"
        ] = index


    # ========================================================
    # SAVE ALL CHUNKS
    # ========================================================

    all_chunks_path = (
        CHUNK_DIR
        / "all_chunks.json"
    )

    save_json(
        all_chunks,
        all_chunks_path
    )


    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print("\n" + "=" * 70)

    print("PREPROCESSING COMPLETE")

    print("=" * 70)

    print(
        f"Documents processed: "
        f"{len(pdf_files)}"
    )

    print(
        f"Total chunks: "
        f"{len(all_chunks)}"
    )

    print(
        f"Output: "
        f"{all_chunks_path}"
    )

    print("=" * 70)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    process_all_documents()