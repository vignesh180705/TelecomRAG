import re
import json
from pathlib import Path
from collections import Counter

from pypdf import PdfReader


# ============================================================
# CONFIGURATION
# ============================================================

HEADER_FOOTER_FREQUENCY = 0.30

MIN_REPEATED_LINE_LENGTH = 4


# ============================================================
# BASIC CLEANING
# ============================================================

def clean_line(line):
    """
    Normalize whitespace while preserving the actual text.
    """

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


def clean_page_text(text):
    """
    Clean extracted page text while preserving line boundaries.
    """

    if not text:
        return ""

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
# PAGE NUMBER DETECTION
# ============================================================

def is_page_number(line):
    """
    Detect common standalone page-number formats.

    Examples:
        1
        25
        - 25 -
        Page 25
        25 of 100
    """

    line = line.strip()

    patterns = [

        r"^\d+$",

        r"^[-–—]\s*\d+\s*[-–—]$",

        r"^Page\s+\d+$",

        r"^\d+\s+of\s+\d+$"

    ]

    return any(
        re.match(
            pattern,
            line,
            re.IGNORECASE
        )
        for pattern in patterns
    )


# ============================================================
# NORMALIZE REPEATED LINES
# ============================================================

def normalize_for_frequency(line):
    """
    Normalize a line so repeated headers/footers can be detected.
    """

    line = line.lower()

    # Remove page-number-like values
    line = re.sub(
        r"\b\d+\b",
        "#",
        line
    )

    line = re.sub(
        r"\s+",
        " ",
        line
    )

    return line.strip()


# ============================================================
# FIND REPEATED HEADERS / FOOTERS
# ============================================================

def find_repeated_lines(
    raw_pages
):
    """
    Find lines that occur on a significant fraction of pages.

    We use frequency rather than hardcoded 3GPP headers because
    different TS/TR documents have different headers.
    """

    counter = Counter()

    total_pages = len(
        raw_pages
    )

    for page in raw_pages:

        # Only inspect the first/last few lines.
        # This prevents ordinary body text from being considered
        # a repeated header/footer.
        lines = page["raw_text"].split("\n")

        candidates = []

        candidates.extend(
            lines[:6]
        )

        candidates.extend(
            lines[-6:]
        )

        seen_on_page = set()

        for line in candidates:

            line = clean_line(line)

            if not line:
                continue

            if is_page_number(line):
                continue

            if len(line) < MIN_REPEATED_LINE_LENGTH:
                continue

            normalized = (
                normalize_for_frequency(
                    line
                )
            )

            if normalized:
                seen_on_page.add(
                    normalized
                )

        for normalized in seen_on_page:

            counter[
                normalized
            ] += 1

    repeated = set()

    for line, count in counter.items():

        frequency = (
            count / total_pages
            if total_pages
            else 0
        )

        if (
            frequency
            >= HEADER_FOOTER_FREQUENCY
        ):

            repeated.add(line)

    return repeated


# ============================================================
# REMOVE HEADERS / FOOTERS
# ============================================================

def remove_headers_footers(
    text,
    repeated_lines
):
    """
    Remove lines identified as repeated headers/footers.
    """

    cleaned = []

    lines = text.split("\n")

    for line in lines:

        original = clean_line(
            line
        )

        if not original:
            continue

        # Remove standalone page numbers
        if is_page_number(original):
            continue

        normalized = (
            normalize_for_frequency(
                original
            )
        )

        if normalized in repeated_lines:
            continue

        cleaned.append(
            original
        )

    return "\n".join(
        cleaned
    )


# ============================================================
# TOC DETECTION
# ============================================================

TOC_LINE_RE = re.compile(
    r"^(\d+(?:\.\d+)*)\s+(.+?)\s+\.{2,}\s*(\d+)\s*$"
)


def is_toc_line(line):

    return (
        TOC_LINE_RE.match(
            line.strip()
        )
        is not None
    )


def count_toc_entries(text):

    count = 0

    for line in text.split("\n"):

        if is_toc_line(line):
            count += 1

    return count


def detect_toc_pages(pages):

    toc_pages = []

    for page in pages:

        # extract_pages() stores cleaned text
        # under the "text" key.
        count = count_toc_entries(
            page["text"]
        )

        if count >= 3:

            toc_pages.append(
                page["page_number"]
            )

    return toc_pages

# ============================================================
# PAGE EXTRACTION
# ============================================================

def extract_raw_pages(
    pdf_path
):
    """
    Extract raw text from every PDF page.

    Nothing is removed at this stage.
    """

    reader = PdfReader(
        str(pdf_path)
    )

    pages = []

    for index, page in enumerate(
        reader.pages
    ):

        raw_text = (
            page.extract_text()
            or ""
        )

        pages.append({

            "page_number":
                index + 1,

            "raw_text":
                raw_text
        })

    return reader, pages


# ============================================================
# COMPLETE PAGE EXTRACTION PIPELINE
# ============================================================

def extract_pages(
    pdf_path
):
    """
    Complete page extraction pipeline.

    Returns:
        {
            page_count,
            pages,
            toc_pages,
            repeated_lines
        }
    """

    pdf_path = Path(
        pdf_path
    )

    reader, raw_pages = (
        extract_raw_pages(
            pdf_path
        )
    )

    # --------------------------------------------------------
    # Find repeated headers/footers
    # --------------------------------------------------------

    repeated_lines = (
        find_repeated_lines(
            raw_pages
        )
    )

    # --------------------------------------------------------
    # Clean every page
    # --------------------------------------------------------

    pages = []

    for page in raw_pages:

        raw_text = page[
            "raw_text"
        ]

        clean_text = (
            clean_page_text(
                raw_text
            )
        )

        clean_text = (
            remove_headers_footers(
                clean_text,
                repeated_lines
            )
        )

        pages.append({

            "page_number":
                page[
                    "page_number"
                ],

            "text":
                clean_text
        })

    # --------------------------------------------------------
    # Detect TOC after cleaning
    # --------------------------------------------------------

    toc_pages = (
        detect_toc_pages(
            pages
        )
    )

    return {

        "page_count":
            len(reader.pages),

        "pages":
            pages,

        "toc_pages":
            toc_pages,

        "repeated_lines":
            sorted(
                repeated_lines
            )
    }


# ============================================================
# SAVE
# ============================================================

def save_pages(
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
# DEBUG PRINT
# ============================================================

def print_page_summary(
    data
):

    print(
        f"Pages: "
        f"{data['page_count']}"
    )

    print(
        f"TOC pages: "
        f"{data['toc_pages']}"
    )

    print(
        "\nRepeated header/footer lines:"
    )

    for line in data[
        "repeated_lines"
    ]:

        print(
            f"  {line}"
        )

    print(
        "\nPage summary:"
    )

    for page in data[
        "pages"
    ]:

        text = page[
            "text"
        ]

        print(
            f"Page "
            f"{page['page_number']:>3}: "
            f"{len(text):>6} chars"
        )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    pdf_path = (
        "documents/TS_23.501.pdf"
    )

    output_path = (
        "data/parsed/"
        "TS_23.501_pages.json"
    )

    data = extract_pages(
        pdf_path
    )

    save_pages(
        data,
        output_path
    )

    print_page_summary(
        data
    )

    print(
        f"\nSaved to: "
        f"{output_path}"
    )