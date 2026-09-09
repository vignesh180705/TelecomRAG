import hashlib


def _hash(value: str) -> str:

    return hashlib.sha1(
        value.encode("utf-8")
    ).hexdigest()[:20]


def make_chunks(
    document,
    chunk_size=5000,
    overlap=500,
):

    if overlap >= chunk_size:

        raise ValueError(
            "overlap must be smaller than chunk_size"
        )

    chunks = []

    index = 0

    for page in document["pages"]:

        text = page["text"]

        if not text:
            continue

        start = 0

        while start < len(text):

            end = min(
                start + chunk_size,
                len(text),
            )

            chunk_text = text[
                start:end
            ].strip()

            if chunk_text:

                chunk_id = _hash(
                    f"{document['document_id']}|"
                    f"{page['page']}|"
                    f"{index}|"
                    f"{chunk_text}"
                )

                chunks.append({

                    "chunk_id": chunk_id,

                    "document_id":
                        document["document_id"],

                    "filename":
                        document["filename"],

                    "page_start":
                        page["page"],

                    "page_end":
                        page["page"],

                    "chunk_index":
                        index,

                    "text":
                        chunk_text,
                })

                index += 1

            if end >= len(text):
                break

            start = max(
                end - overlap,
                start + 1,
            )

    return chunks