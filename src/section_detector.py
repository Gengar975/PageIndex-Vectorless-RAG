import re
from typing import Any


ARTICLE = re.compile(
    r"^(?:Article|ARTICLE)\s+(\d+)\s*[—\-:]\s*(.+)$",
    re.IGNORECASE,
)

EXHIBIT = re.compile(
    r"^Exhibit\s+([A-Z0-9]+)\s*[—\-:]\s*(.+)$",
    re.IGNORECASE,
)

CHAPTER = re.compile(
    r"^(?:CHAPTER|Chapter)\s+(.+)$",
)

NUMERIC_TOP_LEVEL = re.compile(
    r"^(\d+)\s*[.)]\s+(.+)$"
)

NUMERIC_SUBSECTION = re.compile(
    r"^(\d+\.\d+(?:\.\d+)*)\s*[.)]\s+(.+)$"
)

SIGNATURES = re.compile(
    r"^Signatures?$",
    re.IGNORECASE,
)


def detect_sections(document: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Detect structural sections and subsections.

    Supported structures:

        1. Employment Basics
            1.1 Employment Classification
            1.2 Probationary Period

        Article 1 — Scope of Services

        Chapter 1

        Exhibit A — Statement of Work

        Signatures

    For DOCX documents, Word heading styles are also used:

        Heading 1 -> top-level section
        Heading 2 -> subsection

    XLSX worksheets are treated as structural sections.

    IDs generated here are deterministic within a document.
    The PageIndex tree builder can later add document-level
    identity if required.
    """

    # ---------------------------------------------------------
    # XLSX
    # ---------------------------------------------------------

    if document.get("file_type") == "xlsx":
        return _detect_worksheets(document)

    sections = []

    current = None
    current_subsection = None

    # Counter for structural sections.

    # This counter is important for unnumbered DOCX headings.
    # We do NOT use len(sections) here because the currently
    # active section has not yet been appended to sections.
    section_counter = 0

    for page in document.get("pages", []):
        page_number = page["page_number"]

        # -----------------------------------------------------
        # DOCX pages contain blocks with style information.
        #
        # For PDFs and older normalized documents, blocks may
        # not exist, so we fall back to text lines.
        # -----------------------------------------------------

        blocks = _get_blocks(page)

        for block in blocks:
            line = block.get("text", "").strip()

            if not line:
                continue

            is_heading = block.get(
                "is_heading",
                False,
            )

            style = block.get(
                "style",
                "",
            ).strip().lower()

            # =================================================
            # 1. ARTICLE
            # =================================================

            match = ARTICLE.match(line)

            if match:
                number = int(match.group(1))

                current, current_subsection = _start_section(
                    sections,
                    current,
                    page_number,
                    "article",
                    f"article_{number:03d}",
                    line,
                    section_number=number,
                )

                continue

            # =================================================
            # 2. EXHIBIT
            # =================================================

            match = EXHIBIT.match(line)

            if match:
                letter = match.group(1).lower()

                current, current_subsection = _start_section(
                    sections,
                    current,
                    page_number,
                    "exhibit",
                    f"exhibit_{letter}",
                    line,
                )

                continue

            # =================================================
            # 3. SIGNATURES
            # =================================================

            if SIGNATURES.match(line):
                section_counter += 1

                current, current_subsection = _start_section(
                    sections,
                    current,
                    page_number,
                    "signatures",
                    f"signatures_{section_counter:03d}",
                    line,
                )

                continue

            # =================================================
            # 4. CHAPTER
            # =================================================

            if CHAPTER.match(line) and _looks_like_chapter(line):
                section_counter += 1

                current, current_subsection = _start_section(
                    sections,
                    current,
                    page_number,
                    "chapter",
                    f"chapter_{section_counter:03d}",
                    line,
                )

                continue

            # =================================================
            # 5. NUMERIC SUBSECTION
            #
            # Example:
            #
            # 1.1 Employment Classification
            # 1.2 Probationary Period
            #
            # These belong underneath section 1.
            # =================================================

            match = NUMERIC_SUBSECTION.match(line)

            if match and current is not None:
                number = match.group(1)

                if _belongs_to_current_section(
                    number,
                    current,
                ):
                    subsection = _create_subsection(
                        current,
                        number,
                        line,
                        page_number,
                    )

                    current["subsections"].append(
                        subsection
                    )

                    current_subsection = subsection

                    current["text"] += line + "\n"

                    continue

            # =================================================
            # 6. NUMERIC TOP-LEVEL SECTION
            #
            # Example:
            #
            # 1. Employment Basics
            # 2. Leave Policy
            # 3. Benefits
            #
            # IMPORTANT:
            # Numbered headings are handled before DOCX
            # heading styles.
            # =================================================

            match = NUMERIC_TOP_LEVEL.match(line)

            if match:
                number = int(match.group(1))

                current, current_subsection = _start_section(
                    sections,
                    current,
                    page_number,
                    "section",
                    f"section_{number:03d}",
                    line,
                    section_number=number,
                )

                continue

            # =================================================
            # 7. DOCX HEADING 1
            #
            # Handles documents such as:
            #
            # About Us
            # Leadership
            # Culture and Ways of Working
            # Strategic Initiatives
            # Locations
            # Contact and Escalation
            #
            # IMPORTANT:
            # We use section_counter rather than
            # len(sections) + 1.
            #
            # The active section is not yet inside sections,
            # so len(sections) can otherwise produce duplicate
            # IDs.
            # =================================================

            if (
                document.get("file_type") == "docx"
                and is_heading
                and style in {
                    "heading 1",
                    "heading1",
                }
            ):
                section_counter += 1

                current, current_subsection = _start_section(
                    sections,
                    current,
                    page_number,
                    "section",
                    f"section_{section_counter:03d}",
                    line,
                )

                continue

            # =================================================
            # 8. DOCX HEADING 2
            #
            # Handles:
            #
            # Heading 1
            #     Heading 2
            #
            # These are stored as children of the current
            # section.
            # =================================================

            if (
                document.get("file_type") == "docx"
                and is_heading
                and style in {
                    "heading 2",
                    "heading2",
                }
                and current is not None
            ):
                subsection = _create_subsection(
                    current,
                    None,
                    line,
                    page_number,
                )

                current["subsections"].append(
                    subsection
                )

                current_subsection = subsection

                current["text"] += line + "\n"

                continue

            # =================================================
            # 9. NORMAL CONTENT
            # =================================================

            if current is not None:
                current["text"] += line + "\n"

                if current_subsection is not None:
                    current_subsection["text"] += line + "\n"
                    current_subsection["end_page"] = page_number

    # ---------------------------------------------------------
    # Finish final section.
    # ---------------------------------------------------------

    if current is not None:
        current["end_page"] = max(
            current.get("end_page", 1),
            current.get("start_page", 1),
        )

        sections.append(current)

    return sections


def _get_blocks(page: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Return normalized blocks.

    DOCX parsing preserves paragraph style information
    through page["blocks"].

    PDF documents do not currently have blocks, so their text
    is converted into simple blocks.
    """

    blocks = page.get("blocks")

    if blocks:
        return blocks

    return [
        {
            "text": line,
            "style": "",
            "is_heading": False,
        }
        for line in page.get(
            "text",
            "",
        ).splitlines()
        if line.strip()
    ]


def _create_subsection(
    current: dict[str, Any],
    number: str | None,
    heading: str,
    page_number: int,
) -> dict[str, Any]:
    """
    Create a subsection belonging to the current section.

    Numeric subsections use their actual number:

        section_001_1_1

    Unnumbered Heading 2 elements receive a deterministic
    sequential identifier:

        section_001_subsection_001
    """

    index = len(
        current.get(
            "subsections",
            [],
        )
    ) + 1

    if number is not None:
        subsection_id = (
            f"{current['id']}_"
            f"{number.replace('.', '_')}"
        )
    else:
        subsection_id = (
            f"{current['id']}_"
            f"subsection_{index:03d}"
        )

    return {
        "subsection_id": subsection_id,
        "type": "subsection",
        "section_number": number,
        "heading": heading,
        "title": heading,
        "start_page": page_number,
        "end_page": page_number,
        "text": "",
    }


def _belongs_to_current_section(
    subsection_number: str,
    current: dict[str, Any],
) -> bool:
    """
    Check whether a numeric subsection belongs to
    the currently active top-level section.

    Examples:

        Current section = 1
        1.1 -> True
        1.2 -> True
        2.1 -> False

        Current section = 2
        2.1 -> True
        2.2 -> True
        3.1 -> False
    """

    parts = subsection_number.split(".")

    if len(parts) < 2:
        return False

    parent_number = parts[0]

    current_number = current.get(
        "section_number"
    )

    if current_number is None:
        return False

    return str(current_number) == parent_number


def _start_section(
    sections,
    current,
    page_number,
    node_type,
    node_id,
    heading,
    section_number=None,
):
    """
    Finish the previous section and start a new one.
    """

    if current is not None:

        if current["start_page"] == page_number:
            current["end_page"] = page_number
        else:
            current["end_page"] = max(
                current["start_page"],
                page_number - 1,
            )

        sections.append(current)

    current = {
        "id": node_id,
        "section_id": node_id,
        "type": node_type,
        "heading": heading,
        "title": heading,
        "section_number": section_number,
        "start_page": page_number,
        "end_page": page_number,
        "text": "",
        "subsections": [],
    }

    return current, None


def _looks_like_chapter(line: str) -> bool:
    """
    Verify that a Chapter heading has a recognizable number,
    word-number, or Roman numeral.
    """

    return bool(
        re.match(
            r"^(?:CHAPTER|Chapter)\s+"
            r"(?:ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|"
            r"EIGHT|NINE|TEN|\d+|[IVXLCDM]+)\b",
            line,
        )
    )


def _detect_worksheets(
    document: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Treat each XLSX worksheet as a structural section.

    Worksheet IDs are based on worksheet position and are
    therefore deterministic within the document.
    """

    sections = []

    for page in document.get("pages", []):
        number = page["page_number"]

        name = page.get(
            "worksheet_name",
            page.get(
                "title",
                f"Worksheet {number}",
            ),
        )

        worksheet_id = f"worksheet_{number:03d}"

        sections.append({
            "id": worksheet_id,
            "section_id": worksheet_id,
            "type": "worksheet",
            "title": name,
            "heading": name,
            "section_number": number,
            "start_page": number,
            "end_page": number,
            "text": page.get(
                "text",
                "",
            ),
            "subsections": [],
        })

    return sections