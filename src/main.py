'''
from schema_loader import Neo4jSchema
from importer import ThreeGPPImporter


def main():

    print("================================")
    print("3GPP Knowledge Graph Builder")
    print("================================")

    # --------------------------------
    # 1. Neo4j schema
    # --------------------------------

    print("\nCreating Neo4j schema...")

    schema = Neo4jSchema()

    try:

        schema.create_constraints()
        schema.create_indexes()

    finally:

        schema.close()

    # --------------------------------
    # 2. Import graph
    # --------------------------------

    importer = ThreeGPPImporter()

    try:

        importer.run()

    finally:

        importer.close()


if __name__ == "__main__":
    main()

'''

from pathlib import Path

from config import (
    PDF_DIR,
    OUTPUT_DIR,
    SCHEMA_FILE,
    MAX_PAGES_PER_PDF,
    MAX_CHUNKS,
)

from schema_loader import Ontology
from pdf_loader import load_pdf
from chunker import make_chunks
from grok_extractor import (
    GrokExtractor,
    checkpoint_path,
    load_checkpoint,
    append_checkpoint,
)
from graph_loader import GraphLoader


def main():

    print("=" * 70)
    print("3GPP KNOWLEDGE GRAPH BUILDER")
    print("=" * 70)

    # ---------------------------------------------------------
    # 1. Load ontology
    # ---------------------------------------------------------

    print("\n[1/6] Loading ontology...")

    ontology = Ontology(SCHEMA_FILE)

    print(
        f"Entity types   : {len(ontology.entity_types)}"
    )

    print(
        f"Relationships   : {len(ontology.relationships)}"
    )

    # ---------------------------------------------------------
    # 2. Find PDFs
    # ---------------------------------------------------------

    print("\n[2/6] Finding PDFs...")

    pdf_files = sorted(
        Path(PDF_DIR).glob("*.pdf")
    )

    if not pdf_files:
        raise RuntimeError(
            f"No PDF files found in: {PDF_DIR}"
        )

    print(
        f"Found {len(pdf_files)} PDF(s)"
    )

    for pdf in pdf_files:
        print(f"  - {pdf.name}")

    # ---------------------------------------------------------
    # 3. Initialize Grok
    # ---------------------------------------------------------

    print("\n[3/6] Initializing Grok...")

    extractor = GrokExtractor(
        ontology=ontology
    )

    # ---------------------------------------------------------
    # 4. Initialize Neo4j
    # ---------------------------------------------------------

    print("\n[4/6] Connecting to Neo4j Aura...")

    graph = GraphLoader()

    graph.verify_connectivity()
    graph.init_schema()

    # ---------------------------------------------------------
    # 5. Process PDFs
    # ---------------------------------------------------------

    print("\n[5/6] Processing PDFs...")

    checkpoint = checkpoint_path(OUTPUT_DIR)

    processed_chunks = 0

    try:

        for pdf_file in pdf_files:

            print("\n" + "-" * 70)
            print(f"PDF: {pdf_file.name}")
            print("-" * 70)

            # ---------------------------------------------
            # PDF -> pages
            # ---------------------------------------------

            document = load_pdf(
                pdf_file,
                max_pages=MAX_PAGES_PER_PDF,
            )

            print(
                f"Pages loaded: {len(document['pages'])}"
            )

            # ---------------------------------------------
            # pages -> chunks
            # ---------------------------------------------

            chunks = make_chunks(document)

            if MAX_CHUNKS > 0:

                chunks = chunks[:MAX_CHUNKS]

            print(
                f"Chunks created: {len(chunks)}"
            )

            # ---------------------------------------------
            # Load document/chunks into Neo4j
            # ---------------------------------------------

            for chunk in chunks:

                graph.load_document_and_chunk(
                    document,
                    chunk,
                )

                # -----------------------------------------
                # Checkpoint
                # -----------------------------------------

                existing = load_checkpoint(
                    checkpoint
                )

                if chunk["chunk_id"] in existing:

                    extraction = existing[
                        chunk["chunk_id"]
                    ]

                    print(
                        f"  [CHECKPOINT] "
                        f"page {chunk['page_start']} "
                        f"chunk {chunk['chunk_id']}"
                    )

                else:

                    print(
                        f"  [GROK] "
                        f"page {chunk['page_start']} "
                        f"chunk {chunk['chunk_id']}"
                    )

                    extraction = extractor.extract(
                        chunk
                    )

                    append_checkpoint(
                        checkpoint,
                        chunk["chunk_id"],
                        extraction,
                    )

                # -----------------------------------------
                # Graph
                # -----------------------------------------

                graph.load_extraction(
                    extraction,
                    chunk,
                    document,
                )

                processed_chunks += 1

    finally:

        graph.close()

    # ---------------------------------------------------------
    # 6. Complete
    # ---------------------------------------------------------

    print("\n[6/6] COMPLETE")

    print(
        f"Processed chunks: {processed_chunks:,}"
    )

    print(
        f"Checkpoint: {checkpoint}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()