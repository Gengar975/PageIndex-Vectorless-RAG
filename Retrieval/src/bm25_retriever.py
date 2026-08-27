from rank_bm25 import BM25Okapi


def bm25_search(nodes, query):

    corpus = []

    for node in nodes:
        corpus.append(node["text"].lower().split())

    bm25 = BM25Okapi(corpus)

    query_tokens = query.lower().split()

    scores = bm25.get_scores(query_tokens)

    results = []

    for node, score in zip(nodes, scores):

        results.append({
            "id": node["id"],
            "title": node["title"],
            "text": node["text"],
            "page_start": node["page_start"],
            "page_end": node["page_end"],
            "score": float(score)
        })

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return results