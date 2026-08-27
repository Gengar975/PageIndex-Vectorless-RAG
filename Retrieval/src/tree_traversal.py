def flatten_nodes(node, nodes=None, current_document=None):

    if nodes is None:
        nodes = []

    # If current node is a document
    if node.get("type") == "document":
        current_document = node.get("title")

    if node.get("full_text"):

        nodes.append({
            "id": node.get("id"),
            "document": current_document,
            "title": node.get("title"),
            "text": node.get("full_text"),
            "page_start": node.get("page_start"),
            "page_end": node.get("page_end")
        })

    for child in node.get("children", []):
        flatten_nodes(child, nodes, current_document)

    return nodes