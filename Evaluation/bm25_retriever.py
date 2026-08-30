import re
from rank_bm25 import BM25Okapi


def tokenize(text):
    """
    Splits on any non-alphanumeric character, including
    underscore.

    Using \\w+ here would treat underscore as a word character
    (it's part of \\w), which glues filename-style strings like
    "06_quarterly_financial_report_q3" into a single token. That
    silently breaks keyword matching for any query whose words
    overlap with a source filename's underscore-separated words
    (e.g. a question containing "quarterly financial report"
    never matches a document field containing
    "06_quarterly_financial_report_q3" as one glued token).
    Splitting on underscore as well fixes this without changing
    matching behavior for normal prose text.
    """
    return re.findall(r"[a-z0-9]+", str(text).lower())


# ---------------------------------------------------------
# Query expansion
#
# CAUTION for evaluation validity: expanding "hot/heat" toward
# "temperature/thermal" and "controller" toward "motor/actuator"
# measurably helps exactly the paraphrased-question category in
# this eval set (e.g. "what happens if the controller gets too
# hot" -> the Maintenance section's "thermal protection"
# language). That is a legitimate, generalizable technique
# (domain synonym expansion), but if these specific terms were
# chosen BECAUSE a specific eval question was seen failing, this
# is tuning to the test set rather than improving retrieval in
# general - which inflates R_q without reflecting real
# capability. If reporting this in a paper, disclose this
# function and its provenance, or also evaluate with it removed
# as a robustness check.
# ---------------------------------------------------------

def expand_query(query):
    """
    Add related technical terms to improve BM25 retrieval.
    """

    query_lower = query.lower()

    expanded_terms = []

    if any(word in query_lower for word in [
        "hot", "heat", "heating", "overheat", "overheating"
    ]):
        expanded_terms.extend([
            "temperature",
            "overtemperature",
            "overheating",
            "thermal",
            "high temperature",
            "internal temperature",
            "cool",
            "cooling"
        ])

    if "controller" in query_lower:
        expanded_terms.extend([
            "controller",
            "motor",
            "actuator"
        ])

    return query + " " + " ".join(expanded_terms)


class BM25Index:
    """
    A BM25 index built once over a fixed set of retrieval nodes.

    Building the index means tokenizing every node's searchable
    text and constructing BM25Okapi over the whole corpus - this
    is the expensive part of retrieval and does not depend on
    the query. Build it once per node set, then call `.search()`
    as many times as needed (e.g. once per evaluation question)
    without paying that cost again.
    """

    def __init__(self, nodes):
        self.nodes = nodes

        self._corpus = [
            tokenize(
                f"{node.get('title', '')} "
                f"{node.get('document', '')} "
                f"{node.get('text', '')}"
            )
            for node in nodes
        ]

        self._bm25 = BM25Okapi(self._corpus)

    def search(self, query):

        expanded_query = expand_query(query)

        query_tokens = tokenize(expanded_query)

        scores = self._bm25.get_scores(query_tokens)

        results = []

        for node, score in zip(self.nodes, scores):

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


def bm25_search(nodes, query):
    """
    Convenience one-shot search: builds a fresh BM25Index and
    queries it immediately.

    Fine for a single ad-hoc query (e.g. main.py's interactive
    loop, where a human is typing one question at a time and
    the rebuild cost is invisible next to typing/reading time).

    Wasteful if called repeatedly over the SAME node set, since
    every call re-tokenizes the entire corpus. For batch workloads
    (e.g. evaluate.py running over many questions), build a
    BM25Index once and call `.search()` per query instead.
    """
    return BM25Index(nodes).search(query)

