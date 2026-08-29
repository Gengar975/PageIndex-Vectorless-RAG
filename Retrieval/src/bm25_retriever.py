import re
from rank_bm25 import BM25Okapi


def tokenize(text):
    return re.findall(r"\b\w+\b", str(text).lower())


def bm25_search(nodes, query):

    corpus = []

    for node in nodes:

        searchable_text = (
            f"{node.get('title', '')} "
            f"{node.get('document', '')} "
            f"{node.get('text', '')}"
        )

        corpus.append(tokenize(searchable_text))

    bm25 = BM25Okapi(corpus)

    query_tokens = tokenize(query)

    scores = bm25.get_scores(query_tokens)

    results = []

    for node, score in zip(nodes, scores):

        results.append({
            "id": node["id"],
            "title": node["title"],
            "document": node.get("document"),
            "text": node["text"],
            "page_start": node["page_start"],
            "page_end": node["page_end"],
            "score": float(score)
        })

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    if results:

        best_score = results[0]["score"]

        filtered_results = [
            r for r in results
            if r["score"] > max(0.25, best_score * 0.20)
        ]

        return filtered_results

    return results

