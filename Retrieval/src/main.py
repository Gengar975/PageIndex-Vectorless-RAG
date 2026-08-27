import json
import os

from gemini_client import generate_answer
from tree_traversal import flatten_nodes
from bm25_retriever import bm25_search

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

json_path = os.path.join(
    BASE_DIR,
    "data",
    "pageindex_tree.json"
)

with open(json_path, "r", encoding="utf-8") as f:
    tree = json.load(f)

# Build searchable nodes
nodes = flatten_nodes(tree)

print("=" * 60)
print("VECTORLESS RAG SYSTEM")
print("=" * 60)
print(f"TOTAL NODES INDEXED: {len(nodes)}")

while True:

    query = input("\nEnter your question (type 'exit' to quit): ")

    if query.lower() == "exit":
        print("\nExiting...")
        break

    # BM25 Retrieval
    results = bm25_search(nodes, query)

    if len(results) == 0:
        print("\nNo relevant results found.")
        continue

    print("\nTOP RETRIEVAL RESULTS")

    for i, result in enumerate(results[:5], start=1):

        print("\n" + "-" * 50)
        print(f"Rank      : {i}")
        print(f"Document  : {result.get('document', 'Unknown')}")
        print(f"Title     : {result['title']}")
        print(f"Score     : {round(result['score'], 2)}")
        print(f"Pages     : {result['page_start']} - {result['page_end']}")

        preview = result["text"][:150].replace("\n", " ")
        print(f"Preview   : {preview}")

    # Build context for Gemini
    context = ""

    top_k = results[:5]

    for node in top_k:

        context += (
            f"\n\nDocument: {node.get('document', 'Unknown')}"
            f"\nTitle: {node['title']}\n"
        )

        context += node["text"]

    print("\n" + "=" * 60)
    print("CONTEXT SENT TO LLM")
    print("=" * 60)
    print(context[:1000])

    print("\nGenerating answer...")

    answer = generate_answer(
        query,
        context
    )

    print("\n" + "=" * 60)
    print("FINAL ANSWER")
    print("=" * 60)
    print(answer)