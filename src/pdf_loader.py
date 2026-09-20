from pathlib import Path
import re
import fitz

SCOPE_RE = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*)?\s*Scope\s*$",
    re.IGNORECASE,
)

# Boilerplate/header patterns
BOILERPLATE_PATTERNS = [
    r"copyright",
    r"all rights reserved",
    r"o-ran alliance.*copyright",
    r"o-ran alliance.*confidential",
    r"confidential and proprietary",
    r"agreement in annex zzz",
]

# Page headers like "Page 12"
PAGE_PATTERN = re.compile(r"^Page\s+\d+\s*$", re.IGNORECASE)

# Repeated O-RAN document title/header
DOC_HEADER_PATTERN = re.compile(
    r"^O-RAN\.[A-Za-z0-9&_.\-\s]+v\d+\.\d+\s*$",
    re.IGNORECASE,
)


def is_boilerplate(line: str) -> bool:
    """Return True if a line is PDF boilerplate/header/footer."""

    clean_line = " ".join(line.split()).strip()

    if not clean_line:
        return False

    if PAGE_PATTERN.fullmatch(clean_line):
        return True

    if DOC_HEADER_PATTERN.fullmatch(clean_line):
        return True

    #if LINE_NUMBER_PATTERN.fullmatch(clean_line):
    #    return True

    for pattern in BOILERPLATE_PATTERNS:
        if re.search(pattern, clean_line, re.IGNORECASE):
            return True

    return False


def clean_lines(lines):
    """Remove PDF boilerplate and normalize whitespace."""

    cleaned = []

    for line in lines:
        line = line.strip()

        if is_boilerplate(line):
            continue

        # Skip repeated blank lines
        if not line:
            if cleaned and cleaned[-1] == "":
                continue
            cleaned.append("")
            continue

        cleaned.append(line)

    # Remove leading/trailing blank lines
    while cleaned and cleaned[0] == "":
        cleaned.pop(0)

    while cleaned and cleaned[-1] == "":
        cleaned.pop()

    return cleaned


def specification_name(pdf_path: Path) -> str:
    """Convert TS_23.501.pdf -> TS 23.501."""
    return pdf_path.stem.replace("_", " ")


def load_pdf_pages(pdf_path: Path):
    """
    Yield one record per PDF page, starting from Scope.

    Content before Scope is discarded.
    Copyright/license boilerplate is removed.
    """

    doc = fitz.open(pdf_path)

    try:
        scope_found = False

        for page_index, page in enumerate(doc):

            text = page.get_text("text") or ""

            if not text.strip():
                continue

            lines = text.splitlines()

            # ----------------------------------------
            # Find Scope
            # ----------------------------------------

            if not scope_found:

                # Avoid matching Scope in TOC
                if page_index < 2:
                    continue

                scope_line_index = None

                for i, line in enumerate(lines):

                    clean_line = " ".join(line.split()).strip()

                    if SCOPE_RE.fullmatch(clean_line):
                        scope_line_index = i
                        break

                if scope_line_index is None:
                    continue

                scope_found = True

                # Remove everything before Scope
                lines = lines[scope_line_index:]

            # ----------------------------------------
            # Remove boilerplate
            # ----------------------------------------

            lines = clean_lines(lines)

            text = "\n".join(lines).strip()

            if not text:
                continue

            # ----------------------------------------
            # Yield page
            # ----------------------------------------

            yield {
                "document": specification_name(pdf_path),
                "document_file": pdf_path.name,
                "page": page_index + 1,
                "text": text,
            }

    finally:
        doc.close()