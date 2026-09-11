import re
import json
from pathlib import Path

from pypdf import PdfReader


# ============================================================
# REGEX
# ============================================================

# Examples:
#
# 1 Scope
# 2 References
# 5.3 Architecture
# 5.3.1 General
# 5.3.1.1 Description
#
NUMBERED_HEADING_RE = re.compile(
    r"^(\d+(?:\.\d+)*)\s+(.+?)\s*$"
)


# Examples from TOC:
#
# 5.3 Architecture ................. 42
# 5.3.1 General .................... 43
#
TOC_LINE_RE = re.compile(
    r"^(\d+(?:\.\d+)*)\s+(.+?)\s+\.{2,}\s*(\d+)\s*$"
)


# Annex:
#
# Annex A (informative):
# Annex B:
#
ANNEX_RE = re.compile(
    r"^Annex\s+([A-Z]+)(?:\s+\(([^)]+)\))?\s*:?\s*(.*)$",
    re.IGNORECASE
)


# 3GPP requirement identifiers can vary between documents.
# We intentionally detect the bracketed identifier without
# assuming one exact format.
REQUIREMENT_RE = re.compile(
    r"\[[^\]\n]{1,100}\]"
)


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_line(line):

    line = line.replace(
        "\u00a0",
        " "
    )

    line = re.sub(
        r"[ \t]+",
        " ",
        line
    )

    return line.strip()


def clean_text(text):

    text = text.replace(
        "\r\n",
        "\n"
    )

    text = text.replace(
        "\r",
        "\n"
    )

    lines = []

    for line in text.split("\n"):

        line = clean_line(line)

        if line:
            lines.append(line)

    return "\n".join(lines)


# ============================================================
# DOCUMENT METADATA
# ============================================================

def extract_document_metadata(
    filename,
    text
):

    metadata = {
        "document_number": None,
        "document_type": None,
        "version": None,
        "release": None
    }

    filename_upper = filename.upper()

    # --------------------------------------------------------
    # TS / TR number
    # --------------------------------------------------------

    match = re.search(
        r"\b(TS|TR)\s*[_\-\.]?\s*(\d{2}\.\d{3})\b",
        filename_upper
    )

    if not match:

        match = re.search(
            r"\b(TS|TR)\s+(\d{2}\.\d{3})\b",
            text.upper()
        )

    if match:

        metadata["document_type"] = (
            match.group(1)
        )

        metadata["document_number"] = (
            match.group(2)
        )

    # --------------------------------------------------------
    # Version
    #
    # Typical:
    # Version 18.4.0
    # 18.4.0
    # --------------------------------------------------------

    version_patterns = [
        r"Version\s+(\d+\.\d+\.\d+)",
        r"\b(\d+\.\d+\.\d+)\b"
    ]

    for pattern in version_patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            metadata["version"] = (
                match.group(1)
            )

            break

    # --------------------------------------------------------
    # Release
    #
    # Examples:
    # Release 18
    # Rel-18
    # Rel 18
    # --------------------------------------------------------

    release_patterns = [
        r"Release\s+(\d+)",
        r"Rel[-\s]*(\d+)"
    ]

    for pattern in release_patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            metadata["release"] = (
                match.group(1)
            )

            break

    return metadata


# ============================================================
# SECTION DETECTION
# ============================================================

def parse_numbered_heading(line):

    match = NUMBERED_HEADING_RE.match(
        line
    )

    if not match:
        return None

    number = match.group(1)
    title = match.group(2).strip()

    # Avoid treating long sentences as headings
    if len(title) > 200:
        return None

    # Heading should normally be relatively short
    if len(title.split()) > 25:
        return None

    # Don't classify ordinary sentences as headings
    if title.endswith("."):

        if len(title.split()) > 8:
            return None

    return {
        "section_number": number,
        "section_title": title,
        "section_level": len(
            number.split(".")
        )
    }


def parse_annex_heading(line):

    match = ANNEX_RE.match(
        line.strip()
    )

    if not match:
        return None

    letter = match.group(1).upper()
    annex_type = match.group(2)
    title = match.group(3).strip()

    return {
        "section_number": f"Annex {letter}",
        "section_title": title,
        "section_level": 1,
        "annex": True,
        "annex_letter": letter,
        "annex_type": annex_type
    }


# ============================================================
# SECTION HIERARCHY
# ============================================================

def get_parent_number(
    section_number
):

    # Normal numbered clause
    if section_number[0].isdigit():

        parts = section_number.split(".")

        if len(parts) == 1:
            return None

        return ".".join(
            parts[:-1]
        )

    # Annex has no numbered parent
    return None


def build_section_path(
    section_number,
    registry
):

    path = []

    current = registry.get(
        section_number
    )

    while current:

        number = current[
            "section_number"
        ]

        title = current[
            "section_title"
        ]

        if title:

            label = (
                f"{number} {title}"
            )

        else:

            label = number

        path.insert(
            0,
            label
        )

        parent = current.get(
            "parent_section"
        )

        if not parent:
            break

        current = registry.get(
            parent
        )

    return path


# ============================================================
# TOC
# ============================================================

def parse_toc_line(line):

    line = clean_line(line)

    match = TOC_LINE_RE.match(
        line
    )

    if not match:
        return None

    return {
        "section_number": match.group(1),
        "section_title": match.group(2).strip(),
        "page": int(match.group(3))
    }


def detect_toc_pages(reader):

    toc_pages = set()

    for page_index, page in enumerate(
        reader.pages
    ):

        text = page.extract_text() or ""

        matches = 0

        for line in text.split("\n"):

            if parse_toc_line(line):
                matches += 1

        # Several TOC entries indicate a TOC page
        if matches >= 3:

            toc_pages.add(
                page_index
            )

    return toc_pages


# ============================================================
# PAGE EXTRACTION
# ============================================================

def extract_pages(pdf_path):

    reader = PdfReader(
        str(pdf_path)
    )

    pages = []

    for page_index, page in enumerate(
        reader.pages
    ):

        text = page.extract_text() or ""

        pages.append({

            "page": page_index + 1,

            "text": clean_text(
                text
            )
        })

    return reader, pages


# ============================================================
# SECTION EXTRACTION
# ============================================================

def extract_sections(
    pages,
    toc_pages
):

    sections = []

    registry = {}

    current = None

    for page in pages:

        page_number = page["page"]

        # Skip TOC
        if (
            page_number - 1
            in toc_pages
        ):
            continue

        lines = page["text"].split("\n")

        for line in lines:

            line = clean_line(line)

            if not line:
                continue

            # ------------------------------------------------
            # Numbered clause
            # ------------------------------------------------

            heading = (
                parse_numbered_heading(
                    line
                )
            )

            # ------------------------------------------------
            # Annex
            # ------------------------------------------------

            if heading is None:

                heading = (
                    parse_annex_heading(
                        line
                    )
                )

            # ------------------------------------------------
            # New section
            # ------------------------------------------------

            if heading:

                # Save previous
                if current:

                    sections.append(
                        current
                    )

                section_number = (
                    heading[
                        "section_number"
                    ]
                )

                parent = (
                    get_parent_number(
                        section_number
                    )
                )

                current = {

                    "section_number":
                        section_number,

                    "section_title":
                        heading[
                            "section_title"
                        ],

                    "section_level":
                        heading[
                            "section_level"
                        ],

                    "parent_section":
                        parent,

                    "page_start":
                        page_number,

                    "page_end":
                        page_number,

                    "annex":
                        heading.get(
                            "annex",
                            False
                        ),

                    "annex_letter":
                        heading.get(
                            "annex_letter"
                        ),

                    "annex_type":
                        heading.get(
                            "annex_type"
                        ),

                    "text":
                        ""
                }

                registry[
                    section_number
                ] = current

                continue

            # ------------------------------------------------
            # Content
            # ------------------------------------------------

            if current:

                current[
                    "text"
                ] += line + "\n"

                current[
                    "page_end"
                ] = page_number

    # Final section
    if current:

        sections.append(
            current
        )

    # Build hierarchy
    for section in sections:

        section[
            "section_path"
        ] = build_section_path(
            section[
                "section_number"
            ],
            registry
        )

    return sections


# ============================================================
# DOCUMENT PARSER
# ============================================================

def parse_document(
    pdf_path
):

    pdf_path = Path(
        pdf_path
    )

    reader, pages = (
        extract_pages(
            pdf_path
        )
    )

    # Metadata requires some document text
    combined_text = "\n".join(
        p["text"]
        for p in pages[:10]
    )

    metadata = (
        extract_document_metadata(
            pdf_path.name,
            combined_text
        )
    )

    toc_pages = detect_toc_pages(
        reader
    )

    sections = extract_sections(
        pages,
        toc_pages
    )

    document_id = (
        pdf_path.stem
    )

    # Attach document metadata
    for section in sections:

        section[
            "document_id"
        ] = document_id

        section[
            "filename"
        ] = pdf_path.name

        section[
            "document_number"
        ] = metadata[
            "document_number"
        ]

        section[
            "document_type"
        ] = metadata[
            "document_type"
        ]

        section[
            "version"
        ] = metadata[
            "version"
        ]

        section[
            "release"
        ] = metadata[
            "release"
        ]

    return {

        "document_id":
            document_id,

        "filename":
            pdf_path.name,

        "page_count":
            len(pages),

        "document_number":
            metadata[
                "document_number"
            ],

        "document_type":
            metadata[
                "document_type"
            ],

        "version":
            metadata[
                "version"
            ],

        "release":
            metadata[
                "release"
            ],

        "toc_pages":
            sorted(
                p + 1
                for p in toc_pages
            ),

        "sections":
            sections
    }


# ============================================================
# SAVE
# ============================================================

def save_json(
    data,
    output_path
):

    output_path = Path(
        output_path
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        output_path,
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
# TEST
# ============================================================

if __name__ == "__main__":

    pdf = (
        "documents/TS_23.501.pdf"
    )

    document = parse_document(
        pdf
    )

    save_json(
        document,
        "vector_data/parsed/TS_23.501.json"
    )

    print(
        "Document:",
        document["filename"]
    )

    print(
        "Document number:",
        document["document_number"]
    )

    print(
        "Version:",
        document["version"]
    )

    print(
        "Release:",
        document["release"]
    )

    print(
        "Sections:",
        len(document["sections"])
    )