import re


CLAUSE_RE = re.compile(
    r"^\s*((?:\d+\.)+\d+(?:\.\d+)*)\s+(.{2,200})\s*$"
)


def detect_clause(lines):
    """
    Best-effort clause detection from visible PDF text.
    It deliberately does not invent a clause when one is not visible.
    """
    current_clause = ""
    current_title = ""

    for line in lines:
        line = " ".join(line.split())
        if not line:
            continue

        match = CLAUSE_RE.match(line)
        if match:
            current_clause = match.group(1)
            current_title = match.group(2).strip()

    return current_clause, current_title


def split_text(text, max_chars=1800, overlap=250):
    """
    Character-based splitter that preserves paragraph boundaries when possible.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    chunks = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) <= max_chars:
            candidate = paragraph if not current else current + "\n\n" + paragraph
            if len(candidate) <= max_chars:
                current = candidate
                continue

        if current:
            chunks.append(current)
            current = ""

        if len(paragraph) <= max_chars:
            current = paragraph
            continue

        # Hard split unusually long paragraphs.
        start = 0
        while start < len(paragraph):
            end = min(start + max_chars, len(paragraph))
            piece = paragraph[start:end].strip()
            if piece:
                chunks.append(piece)
            if end >= len(paragraph):
                break
            start = max(0, end - overlap)

    if current:
        chunks.append(current)

    return chunks


def make_chunks(page_record, max_chars=1800, overlap=250):
    text = page_record["text"].strip()
    if not text:
        return []

    lines = text.splitlines()
    clause, title = detect_clause(lines)
    pieces = split_text(text, max_chars=max_chars, overlap=overlap)

    results = []
    for i, piece in enumerate(pieces, start=1):
        chunk_id = (
            f'{page_record["document"].replace(" ", "_").replace(".", "_")}'
            f'_p{page_record["page"]}_{i:03d}'
        )

        results.append({
            "chunk_id": chunk_id,
            "document": page_record["document"],
            "document_file": page_record["document_file"],
            "page": page_record["page"],
            "clause": clause,
            "section_title": title,
            "text": piece,
            "metadata": {
                "document": page_record["document"],
                "document_file": page_record["document_file"],
                "page": page_record["page"],
                "clause": clause,
                "section_title": title,
            },
        })

    return results
