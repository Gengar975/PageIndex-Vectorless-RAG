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

# Create searchable nodes
nodes = flatten_nodes(tree)

print("TOTAL NODES FOUND:")
print(len(nodes))

# Query
query = "What is the guaranteed monthly uptime in the Acme Cloud Solutions SLA?"

# BM25 Search
results = bm25_search(nodes, query)

context = ""

for result in results[:3]:

    context += f"\nTitle: {result['title']}\n"
    context += result["text"]
    context += "\n"

print("\nTOP RESULTS\n")
top_k = results[:6]

context = ""

for node in top_k:
    context += f"\n\nTitle: {node['title']}\n"
    context += node["text"]

print("\nCONTEXT SENT TO LLM")
print(context)

for result in results[:5]:

    print("\n---")

    print("Title :", result["title"])
    print("Score :", round(result["score"], 2))
    print("Pages :", result["page_start"], "-", result["page_end"])
    print("Text :", result["text"][:150])

print("\nQUESTION:")
print(query)

print("\nRETRIEVED CONTEXT:")
print(context)

answer = generate_answer(
    query,
    context
)

print("\nFINAL ANSWER\n")
print(answer)

