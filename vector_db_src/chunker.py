import re
import hashlib

import numpy as np

from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer


# ============================================================
# CONFIG
# ============================================================

EMBEDDING_MODEL = (
    "sentence-transformers/all-MiniLM-L6-v2"
)

TOKENIZER_MODEL = (
    "bert-base-uncased"
)

TARGET_TOKENS = 550

MAX_TOKENS = 900

SIMILARITY_THRESHOLD = 0.70


embedder = SentenceTransformer(
    EMBEDDING_MODEL
)

tokenizer = AutoTokenizer.from_pretrained(
    TOKENIZER_MODEL
)


# ============================================================
# UTILITIES
# ============================================================

def token_count(text):

    return len(
        tokenizer.encode(
            text,
            add_special_tokens=False
        )
    )


def make_id(text):

    return hashlib.sha1(
        text.encode("utf-8")
    ).hexdigest()[:20]


# ============================================================
# PARAGRAPH SPLITTING
# ============================================================

def split_paragraphs(text):

    text = text.strip()

    paragraphs = re.split(
        r"\n\s*\n",
        text
    )

    return [
        p.strip()
        for p in paragraphs
        if p.strip()
    ]


# ============================================================
# STRUCTURE DETECTION
# ============================================================

def is_requirement(text):

    # 3GPP normative bracket identifiers
    if re.search(
        r"\[[^\]\n]{1,100}\]",
        text
    ):
        return True

    # Strong normative language
    normative = re.search(
        r"\b("
        r"shall|shall not|"
        r"should|should not|"
        r"may|may not|"
        r"must|"
        r"is required to"
        r")\b",
        text,
        re.IGNORECASE
    )

    return normative is not None


def is_table(text):

    return bool(
        re.search(
            r"\bTable\s+\d+(?:[-.]\d+)*\b",
            text,
            re.IGNORECASE
        )
    )


def is_figure(text):

    return bool(
        re.search(
            r"\bFigure\s+\d+(?:[-.]\d+)*\b",
            text,
            re.IGNORECASE
        )
    )


def is_yang(text):

    return bool(
        re.search(
            r"\b("
            r"module|container|leaf|list|"
            r"typedef|identity|grouping|augment|"
            r"notification|rpc|choice|case"
            r")\b",
            text,
            re.IGNORECASE
        )
    )


def structure_type(text):

    if is_requirement(text):
        return "requirement"

    if is_table(text):
        return "table"

    if is_figure(text):
        return "figure"

    if is_yang(text):
        return "yang"

    return "normal"


# ============================================================
# SENTENCE SPLITTING
# ============================================================

def split_sentences(text):

    sentences = re.split(
        r"(?<=[.!?])\s+",
        text
    )

    return [
        s.strip()
        for s in sentences
        if s.strip()
    ]


# ============================================================
# SEMANTIC SIMILARITY
# ============================================================

def semantic_similarities(
    paragraphs
):

    if len(paragraphs) <= 1:
        return []

    embeddings = embedder.encode(
        paragraphs,
        normalize_embeddings=True,
        show_progress_bar=False
    )

    similarities = []

    for i in range(
        len(embeddings) - 1
    ):

        score = np.dot(
            embeddings[i],
            embeddings[i + 1]
        )

        similarities.append(
            float(score)
        )

    return similarities


# ============================================================
# SEMANTIC GROUPING
# ============================================================

def semantic_groups(
    paragraphs
):

    if not paragraphs:
        return []

    if len(paragraphs) == 1:
        return [paragraphs]

    similarities = (
        semantic_similarities(
            paragraphs
        )
    )

    groups = []

    current = [
        paragraphs[0]
    ]

    for i, similarity in enumerate(
        similarities
    ):

        next_paragraph = (
            paragraphs[i + 1]
        )

        if (
            similarity
            < SIMILARITY_THRESHOLD
        ):

            groups.append(
                current
            )

            current = [
                next_paragraph
            ]

        else:

            current.append(
                next_paragraph
            )

    if current:

        groups.append(
            current
        )

    return groups


# ============================================================
# OVERSIZED TEXT
# ============================================================

def split_oversized(
    text
):

    if token_count(text) <= MAX_TOKENS:
        return [text]

    sentences = split_sentences(
        text
    )

    pieces = []

    current = []

    current_tokens = 0

    for sentence in sentences:

        s_tokens = token_count(
            sentence
        )

        if (
            current
            and
            current_tokens
            + s_tokens
            > MAX_TOKENS
        ):

            pieces.append(
                " ".join(current)
            )

            current = []

            current_tokens = 0

        current.append(
            sentence
        )

        current_tokens += s_tokens

    if current:

        pieces.append(
            " ".join(current)
        )

    return pieces


# ============================================================
# PACK NORMAL SEMANTIC GROUP
# ============================================================

def pack_group(
    group
):

    chunks = []

    current = []

    current_tokens = 0

    for paragraph in group:

        p_tokens = token_count(
            paragraph
        )

        # Oversized paragraph
        if p_tokens > MAX_TOKENS:

            if current:

                chunks.append(
                    "\n\n".join(
                        current
                    )
                )

                current = []
                current_tokens = 0

            chunks.extend(
                split_oversized(
                    paragraph
                )
            )

            continue

        # Hard maximum
        if (
            current
            and
            current_tokens
            + p_tokens
            > MAX_TOKENS
        ):

            chunks.append(
                "\n\n".join(
                    current
                )
            )

            current = []

            current_tokens = 0

        current.append(
            paragraph
        )

        current_tokens += p_tokens

        # Soft target
        if current_tokens >= TARGET_TOKENS:

            chunks.append(
                "\n\n".join(
                    current
                )
            )

            current = []

            current_tokens = 0

    if current:

        chunks.append(
            "\n\n".join(
                current
            )
        )

    return chunks


# ============================================================
# STRUCTURE-AWARE CHUNKING
# ============================================================

def create_chunks(
    paragraphs
):

    chunks = []

    normal_buffer = []

    def flush_normal():

        nonlocal normal_buffer

        if not normal_buffer:
            return

        groups = semantic_groups(
            normal_buffer
        )

        for group in groups:

            chunks.extend(
                pack_group(group)
            )

        normal_buffer = []

    for paragraph in paragraphs:

        kind = structure_type(
            paragraph
        )

        # ----------------------------------------------------
        # Normal prose
        # ----------------------------------------------------

        if kind == "normal":

            normal_buffer.append(
                paragraph
            )

        # ----------------------------------------------------
        # Protected 3GPP structure
        # ----------------------------------------------------

        else:

            # Finish preceding prose
            flush_normal()

            if (
                token_count(paragraph)
                <= MAX_TOKENS
            ):

                chunks.append(
                    paragraph
                )

            else:

                chunks.extend(
                    split_oversized(
                        paragraph
                    )
                )

    flush_normal()

    return chunks


# ============================================================
# EMBEDDING CONTEXT
# ============================================================

def build_embedding_text(
    section,
    chunk_text
):

    document_number = (
        section.get(
            "document_number"
        )
        or ""
    )

    release = (
        section.get(
            "release"
        )
        or ""
    )

    version = (
        section.get(
            "version"
        )
        or ""
    )

    section_path = (
        section.get(
            "section_path",
            []
        )
    )

    hierarchy = (
        " > ".join(
            section_path
        )
    )

    return (
        f"3GPP document: "
        f"{document_number}\n"
        f"Release: {release}\n"
        f"Version: {version}\n"
        f"Section: {hierarchy}\n\n"
        f"{chunk_text}"
    )


# ============================================================
# CHUNK ONE SECTION
# ============================================================

def chunk_section(
    section
):

    text = section.get(
        "text",
        ""
    ).strip()

    if not text:
        return []

    paragraphs = split_paragraphs(
        text
    )

    chunks = create_chunks(
        paragraphs
    )

    results = []

    for index, chunk_text in enumerate(
        chunks
    ):

        kind = structure_type(
            chunk_text
        )

        embedding_text = (
            build_embedding_text(
                section,
                chunk_text
            )
        )

        raw_id = (
            f"{section.get('document_id')}|"
            f"{section.get('section_number')}|"
            f"{index}|"
            f"{chunk_text}"
        )

        results.append({

            "chunk_id":
                make_id(raw_id),

            "document_id":
                section.get(
                    "document_id"
                ),

            "filename":
                section.get(
                    "filename"
                ),

            "document_number":
                section.get(
                    "document_number"
                ),

            "document_type":
                section.get(
                    "document_type"
                ),

            "release":
                section.get(
                    "release"
                ),

            "version":
                section.get(
                    "version"
                ),

            "section_number":
                section.get(
                    "section_number"
                ),

            "section_title":
                section.get(
                    "section_title"
                ),

            "section_level":
                section.get(
                    "section_level"
                ),

            "parent_section":
                section.get(
                    "parent_section"
                ),

            "section_path":
                section.get(
                    "section_path",
                    []
                ),

            "annex":
                section.get(
                    "annex",
                    False
                ),

            "annex_letter":
                section.get(
                    "annex_letter"
                ),

            "annex_type":
                section.get(
                    "annex_type"
                ),

            "page_start":
                section.get(
                    "page_start"
                ),

            "page_end":
                section.get(
                    "page_end"
                ),

            "chunk_index":
                index,

            "chunk_type":
                kind,

            "token_count":
                token_count(
                    chunk_text
                ),

            "text":
                chunk_text,

            "embedding_text":
                embedding_text
        })

    return results


# ============================================================
# CHUNK ENTIRE DOCUMENT
# ============================================================

def chunk_document(
    document
):

    chunks = []

    for section in document[
        "sections"
    ]:

        chunks.extend(
            chunk_section(
                section
            )
        )

    # Global ordering
    for index, chunk in enumerate(
        chunks
    ):

        chunk[
            "global_chunk_index"
        ] = index

    return chunks