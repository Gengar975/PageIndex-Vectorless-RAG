import argparse
import json
from pathlib import Path

from src.document_parser import (
    discover_documents,
    parse_document,
)

from src.section_detector import (
    detect_sections,
)

from src.page_index import (
    build_page_index,
)

from pageindex_tree import (
    build_corpus_tree,
    save_pageindex_tree,
    merge_existing_summaries,
)


# -------------------------------------------------------------
# Output locations
# -------------------------------------------------------------

OUTPUT_DIR = Path(
    "output"
)

TREE_OUTPUT = (
    OUTPUT_DIR
    / "pageindex_tree.json"
)

PAGE_INDEX_OUTPUT = (
    OUTPUT_DIR
    / "page_index.json"
)


# -------------------------------------------------------------
# Main pipeline
# -------------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Build PageIndex from PDF, DOCX and XLSX."
        )
    )

    parser.add_argument(
        "input",
        nargs="?",
        default="input",
        help=(
            "File or directory containing "
            "PDF/DOCX/XLSX files."
        ),
    )

    parser.add_argument(
        "--summary",
        action="store_true",
        help=(
            "Generate missing structural and "
            "whole-document Gemini summaries."
        ),
    )

    args = parser.parse_args()

    # ---------------------------------------------------------
    # Discover input documents.
    # ---------------------------------------------------------

    files = discover_documents(
        args.input
    )

    if not files:

        raise RuntimeError(
            "No supported PDF, DOCX or XLSX "
            "documents found."
        )

    processed = []

    page_indexes = []

    # ---------------------------------------------------------
    # Document processing.
    # ---------------------------------------------------------

    print(
        "\n===== DOCUMENT PROCESSING =====\n"
    )

    for index, path in enumerate(
        files,
        start=1,
    ):

        print(
            f"[{index}/{len(files)}] {path}"
        )

        document = parse_document(
            path
        )

        sections = detect_sections(
            document
        )

        processed.append({
            "document": document,
            "sections": sections,
        })

        page_indexes.append(
            build_page_index(
                document,
                sections,
            )
        )

        print(
            f"  type={document['file_type']} "
            f"pages={len(document['pages'])} "
            f"sections={len(sections)}"
        )

    # ---------------------------------------------------------
    # Make sure output directory exists.
    # ---------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ---------------------------------------------------------
    # Save PageIndex.
    # ---------------------------------------------------------

    with open(
        PAGE_INDEX_OUTPUT,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            page_indexes,
            file,
            indent=2,
            ensure_ascii=False,
        )

    # ---------------------------------------------------------
    # Build the current PageIndex tree.
    # ---------------------------------------------------------

    new_tree = build_corpus_tree(
        processed
    )

    # ---------------------------------------------------------
    # Resume previous successful summaries.
    #
    # This is important:
    #
    # Every execution rebuilds the structural tree, but
    # previously generated summaries are copied back only when
    # the corresponding node still represents the same source
    # content and structure.
    # ---------------------------------------------------------

    if TREE_OUTPUT.exists():

        print(
            "\n===== RESUMING EXISTING SUMMARIES =====\n"
        )

        try:

            with open(
                TREE_OUTPUT,
                "r",
                encoding="utf-8",
            ) as file:

                old_tree = json.load(
                    file
                )

            reused = merge_existing_summaries(
                new_tree,
                old_tree,
            )

            print(
                f"Reused summaries: {reused}"
            )

        except (
            json.JSONDecodeError,
            OSError,
        ) as exc:

            print(
                "Could not reuse previous tree. "
                "Starting fresh. "
                f"Reason: {exc}"
            )

    # ---------------------------------------------------------
    # Save the current tree BEFORE Gemini generation.
    #
    # This guarantees that the structural tree itself is
    # available even if Gemini fails.
    # ---------------------------------------------------------

    save_pageindex_tree(
        new_tree,
        TREE_OUTPUT,
    )

    # ---------------------------------------------------------
    # Gemini summary generation.
    # ---------------------------------------------------------

    if args.summary:

        from summary_generator import (
            process_tree,
        )

        print(
            "\n===== GENERATING MISSING GEMINI SUMMARIES =====\n"
        )

        # -----------------------------------------------------
        # Save the entire tree after every successful summary.
        #
        # The callback receives the node that was just
        # summarized, but saves the complete current tree.
        # -----------------------------------------------------

        def save_after_summary(
            _node,
        ):

            save_pageindex_tree(
                new_tree,
                TREE_OUTPUT,
            )

        process_tree(
            new_tree,
            save_callback=save_after_summary,
        )

        # -----------------------------------------------------
        # Final save.
        # -----------------------------------------------------

        save_pageindex_tree(
            new_tree,
            TREE_OUTPUT,
        )

    else:

        print(
            "\nGemini summary generation skipped."
            "\nUse --summary to generate missing summaries."
        )

    # ---------------------------------------------------------
    # Final status.
    # ---------------------------------------------------------

    print(
        "\n===== COMPLETE ====="
    )

    print(
        f"PageIndex tree: {TREE_OUTPUT}"
    )

    print(
        f"Page index:     {PAGE_INDEX_OUTPUT}"
    )


# -------------------------------------------------------------
# Entry point
# -------------------------------------------------------------

if __name__ == "__main__":
    main()