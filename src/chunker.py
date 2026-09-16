import hashlib
import re


def _hash(value):
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:20]


def _split_sentences(text):
    """
    Split text while preserving 3GPP requirement blocks such as:

    [PR 5.5.5.3-1] ...

    Also keeps normal paragraphs/sentences reasonably intact.
    """

    # First split on blank lines because 3GPP PDFs often use
    # blank lines between logical blocks.
    blocks = re.split(r"\n\s*\n+", text)

    sentences = []

    for block in blocks:
        block = block.strip()

        if not block:
            continue

        # Requirement blocks should remain together.
        if re.match(r"^\[PR\s+", block):
            sentences.append(block)
            continue

        # Split ordinary prose at sentence boundaries.
        parts = re.split(
            r"(?<=[.!?])\s+(?=[A-Z\[\(])",
            block
        )

        for part in parts:
            part = part.strip()
            if part:
                sentences.append(part)

    return sentences


def make_chunks(document, chunk_size=1500, overlap=256):
    """
    Create page-aware, sentence-aware chunks.

    Important:
    - Chunks never cross PDF page boundaries.
    - Requirements such as [PR ...] are kept intact when possible.
    - chunk_size is an approximate target, not a hard character cut.
    - overlap is applied between logical chunks.
    """

    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks = []
    index = 0

    for page in document["pages"]:

        text = page["text"].strip()

        if not text:
            continue

        sentences = _split_sentences(text)

        if not sentences:
            continue

        current = []

        for sentence in sentences:

            # --------------------------------------------------------
            # Normal case: adding sentence still fits target
            # --------------------------------------------------------
            candidate = "\n".join(current + [sentence])

            if not current or len(candidate) <= chunk_size:
                current.append(sentence)
                continue

            # --------------------------------------------------------
            # Current chunk is ready
            # --------------------------------------------------------
            chunk_text = "\n".join(current).strip()

            if chunk_text:
                chunks.append({
                    "chunk_id": _hash(
                        f"{document['document_id']}|"
                        f"{page['page']}|"
                        f"{index}|"
                        f"{chunk_text}"
                    ),
                    "document_id": document["document_id"],
                    "filename": document["filename"],
                    "page_start": page["page"],
                    "page_end": page["page"],
                    "chunk_index": index,
                    "text": chunk_text,
                })

                index += 1

            # --------------------------------------------------------
            # Build overlap from the end of the previous chunk.
            # Keep complete sentences rather than cutting characters.
            # --------------------------------------------------------
            overlap_sentences = []
            overlap_length = 0

            for previous in reversed(current):
                if overlap_length + len(previous) > overlap:
                    break

                overlap_sentences.insert(0, previous)
                overlap_length += len(previous)

            current = overlap_sentences + [sentence]

        # ------------------------------------------------------------
        # Flush final chunk for page
        # ------------------------------------------------------------
        if current:

            chunk_text = "\n".join(current).strip()

            if chunk_text:
                chunks.append({
                    "chunk_id": _hash(
                        f"{document['document_id']}|"
                        f"{page['page']}|"
                        f"{index}|"
                        f"{chunk_text}"
                    ),
                    "document_id": document["document_id"],
                    "filename": document["filename"],
                    "page_start": page["page"],
                    "page_end": page["page"],
                    "chunk_index": index,
                    "text": chunk_text,
                })

                index += 1

    return chunks