import json
from pathlib import Path
from typing import Any


def build_document_tree(document, sections, document_index=1):
    stem = Path(
        document.get(
            "document_name",
            "document",
        )
    ).stem

    document_node = {
        "id": f"document_{document_index:03d}",
        "type": "document",
        "title": document.get(
            "document_name",
            stem,
        ),
        "source": document.get(
            "source",
            "",
        ),
        "file_type": document.get(
            "file_type",
            "",
        ),
        "page_count": len(
            document.get(
                "pages",
                [],
            )
        ),
        "summary": "",
        "children": [],
    }

    for section in sections:
        node = {
            "id": section["id"],
            "type": section["type"],
            "title": section.get(
                "title",
                section.get(
                    "heading",
                    "",
                ),
            ),
            "page_start": section.get(
                "start_page"
            ),
            "page_end": section.get(
                "end_page"
            ),
            "summary": "",
            "full_text": section.get(
                "text",
                "",
            ),
            "children": [],
        }

        for subsection in section.get(
            "subsections",
            [],
        ):
            node["children"].append({
                "id": subsection[
                    "subsection_id"
                ],
                "type": "subsection",
                "title": subsection.get(
                    "heading",
                    "",
                ),
                "page_start": subsection.get(
                    "start_page"
                ),
                "page_end": subsection.get(
                    "end_page"
                ),
                "summary": "",
                "full_text": subsection.get(
                    "text",
                    "",
                ),
                "children": [],
            })

        # For XLSX, preserve every worksheet's logical page.
        if section["type"] == "worksheet":
            node["children"] = _worksheet_pages(
                document,
                section,
            )

        document_node["children"].append(node)

    return document_node


def _worksheet_pages(document, section):
    page_number = section.get(
        "start_page"
    )

    page = next(
        (
            p
            for p in document.get(
                "pages",
                []
            )
            if p.get("page_number") == page_number
        ),
        None,
    )

    if not page:
        return []

    # A worksheet is itself the meaningful
    # structural unit.
    #
    # Do not duplicate the entire worksheet
    # text into the page node.
    return [{
        "id": page.get(
            "page_id",
            f"worksheet_page_{page_number:03d}",
        ),
        "type": "page",
        "title": f"Page {page_number}",
        "page_number": page_number,
        "children": [],
    }]


def build_corpus_tree(processed_documents):
    corpus = {
        "id": "corpus_001",
        "type": "corpus",
        "title": "Document Corpus",
        "children": [],
    }

    for index, item in enumerate(
        processed_documents,
        start=1,
    ):
        corpus["children"].append(
            build_document_tree(
                item["document"],
                item["sections"],
                document_index=index,
            )
        )

    return corpus


# -------------------------------------------------------------
# Resumability
# -------------------------------------------------------------


def _node_fingerprint(node: dict[str, Any]):
    """
    Create a representation of a node that excludes generated
    summary information.

    If this representation is unchanged between runs, the old
    summary can safely be reused.
    """

    fingerprint = {
        "id": node.get("id"),
        "type": node.get("type"),
        "title": node.get("title"),
        "page_start": node.get("page_start"),
        "page_end": node.get("page_end"),
        "page_number": node.get("page_number"),
        "full_text": node.get("full_text"),
        "source": node.get("source"),
        "file_type": node.get("file_type"),
        "page_count": node.get("page_count"),
    }

    children = []

    for child in node.get(
        "children",
        [],
    ):
        children.append(
            _node_fingerprint(child)
        )

    fingerprint["children"] = children

    return fingerprint


def _same_source_structure(
    new_node: dict[str, Any],
    old_node: dict[str, Any],
) -> bool:
    """
    Determine whether a previous summary still belongs to the
    current node.
    """

    return (
        _node_fingerprint(new_node)
        == _node_fingerprint(old_node)
    )


def _index_nodes_by_id(node):
    """
    Build an ID → node lookup table for an existing tree.
    """

    nodes = {}

    node_id = node.get("id")

    if node_id:
        nodes[node_id] = node

    for child in node.get(
        "children",
        [],
    ):
        nodes.update(
            _index_nodes_by_id(child)
        )

    return nodes


def _reuse_node_summary(
    new_node: dict[str, Any],
    old_nodes: dict[str, dict[str, Any]],
):
    """
    Reuse a summary when the node still represents the same
    source content and structure.
    """

    node_id = new_node.get("id")

    if not node_id:
        return False

    old_node = old_nodes.get(node_id)

    if not old_node:
        return False

    if not _same_source_structure(
        new_node,
        old_node,
    ):
        return False

    old_summary = old_node.get(
        "summary",
        "",
    )

    if not old_summary:
        return False

    new_node["summary"] = old_summary

    # An old summary_error is no longer relevant because the
    # summary itself was successfully preserved.
    new_node.pop(
        "summary_error",
        None,
    )

    return True


def merge_existing_summaries(
    new_tree: dict[str, Any],
    old_tree: dict[str, Any],
) -> int:
    """
    Copy valid summaries from old_tree into new_tree.

    A summary is reused only when the node's source content and
    structural information are unchanged.

    Returns the number of reused summaries.
    """

    old_nodes = _index_nodes_by_id(
        old_tree
    )

    reused = 0

    def walk(node):
        nonlocal reused

        if _reuse_node_summary(
            node,
            old_nodes,
        ):
            reused += 1

        for child in node.get(
            "children",
            [],
        ):
            walk(child)

    walk(new_tree)

    return reused


# -------------------------------------------------------------
# Backward-compatible single-document function.
# -------------------------------------------------------------


def build_pageindex_tree(
    document,
    sections,
):
    return build_corpus_tree([
        {
            "document": document,
            "sections": sections,
        }
    ])


def save_pageindex_tree(
    tree,
    output_path,
):
    output_path = Path(
        output_path
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            tree,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(
        f"PageIndex tree saved to: {output_path}"
    )