import csv
import json
import os
import re
import time
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# Imports
# ---------------------------------------------------------

from tree_traversal import flatten_nodes
from bm25_retriever import BM25Index
from groq_client import generate_answer


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent

TREE_PATH = PROJECT_ROOT / "data" / "pageindex_tree.json"
QUESTIONS_PATH = PROJECT_ROOT / "questions.csv"
OUTPUT_PATH = PROJECT_ROOT / "evaluation_results.csv"

# ---------------------------------------------------------
# Evaluation configuration
# ---------------------------------------------------------

TOP_K = 8

# ---------------------------------------------------------
# Cost estimation
#
# These are placeholders - Groq's pricing changes over time
# and varies by model, so verify the current rate for your
# GROQ_MODEL at https://groq.com/pricing before trusting the
# "Cost ($)" column. Override via env vars if needed.
# ---------------------------------------------------------

INPUT_PRICE_PER_1M = float(
    os.getenv("GROQ_INPUT_PRICE_PER_1M", "0.15")
)

OUTPUT_PRICE_PER_1M = float(
    os.getenv("GROQ_OUTPUT_PRICE_PER_1M", "0.60")
)


def estimate_cost(input_tokens: int, output_tokens: int) -> float:

    cost = (
        (input_tokens / 1_000_000) * INPUT_PRICE_PER_1M
        + (output_tokens / 1_000_000) * OUTPUT_PRICE_PER_1M
    )

    return cost


# ---------------------------------------------------------
# Filename normalization
# ---------------------------------------------------------

def normalize_filename(
    filename: str,
) -> str:

    if not filename:
        return ""

    filename = str(filename).strip()

    # Remove quotes
    filename = filename.strip(
        "\"'"
    )

    # Only keep basename
    filename = Path(
        filename
    ).name

    # Normalize whitespace
    filename = re.sub(
        r"\s+",
        "_",
        filename,
    )

    return filename.lower()


def normalize_source_list(
    source_string: str,
) -> list[str]:

    if not source_string:
        return []

    # Your CSV uses ;
    sources = source_string.split(";")

    return [
        normalize_filename(source)
        for source in sources
        if normalize_filename(source)
    ]


# ---------------------------------------------------------
# Extract source filename from tree node
# ---------------------------------------------------------

def get_node_source(
    node: dict[str, Any],
) -> str:

    source = node.get(
        "source",
        "",
    )

    if source:
        return normalize_filename(
            source
        )

    document = node.get(
        "document",
        "",
    )

    if document:
        return normalize_filename(
            document
        )

    # Sometimes document name is stored in title
    title = node.get(
        "title",
        "",
    )

    # Do NOT blindly use title as source.
    # This is only a fallback for actual file-looking titles.

    if title:

        suffixes = (
            ".pdf",
            ".docx",
            ".xlsx",
        )

        if title.lower().endswith(
            suffixes
        ):
            return normalize_filename(
                title
            )

    return ""


# ---------------------------------------------------------
# Add document information to nodes
# ---------------------------------------------------------

def propagate_document_names(
    node: dict[str, Any],
    current_document: str = "",
):

    node_type = node.get(
        "type",
        "",
    )

    if node_type == "document":

        current_document = normalize_filename(
            node.get(
                "title",
                node.get(
                    "source",
                    "",
                ),
            )
        )

        node["_document_source"] = (
            current_document
        )

    else:

        if current_document:
            node["_document_source"] = (
                current_document
            )

    for child in node.get(
        "children",
        [],
    ):

        propagate_document_names(
            child,
            current_document,
        )


# ---------------------------------------------------------
# Get source from retrieval node
# ---------------------------------------------------------

def get_retrieval_source(
    node: dict[str, Any],
) -> str:

    source = node.get(
        "_document_source",
        "",
    )

    if source:
        return normalize_filename(
            source
        )

    source = get_node_source(
        node
    )

    return source


# ---------------------------------------------------------
# Context creation
# ---------------------------------------------------------

def build_context(
    results: list[dict[str, Any]],
) -> str:

    parts = []

    for node in results[:TOP_K]:

        document = (
            node.get(
                "_document_source",
                "",
            )
            or get_node_source(node)
            or "Unknown"
        )

        title = node.get(
            "title",
            "",
        )

        text = node.get(
            "full_text",
            node.get(
                "text",
                "",
            ),
        )

        if not isinstance(
            text,
            str,
        ):
            text = ""

        if not text.strip():
            continue

        parts.append(
            f"""
Document: {document}
Section: {title}

{text}
""".strip()
        )

    return "\n\n".join(
        parts
    )


# ---------------------------------------------------------
# Retrieved source extraction
# ---------------------------------------------------------

def get_retrieved_sources(
    results: list[dict[str, Any]],
) -> list[str]:

    sources = []

    for node in results[:TOP_K]:

        source = get_retrieval_source(
            node
        )

        if source and source not in sources:
            sources.append(source)

    return sources


# ---------------------------------------------------------
# Source recall
# ---------------------------------------------------------

def calculate_source_recall(
    expected_sources: list[str],
    retrieved_sources: list[str],
) -> tuple[int, list[str]]:
    """
    Compares filename STEMS (basename without extension), not
    full filenames.

    Source corpora often store the same logical document under
    a different extension than however it's referenced in the
    question bank (e.g. questions.csv says "02_hr_policy.md" but
    the actual indexed file is "02_hr_policy.docx"). Comparing
    full filenames would treat that as a miss even though the
    correct document was retrieved. Comparing stems fixes that
    without weakening the check - a stem match still requires
    the correct document identity, just not the same extension.
    """

    def stem(name: str) -> str:
        return Path(
            normalize_filename(name)
        ).stem

    expected_by_stem = {
        stem(x): normalize_filename(x)
        for x in expected_sources
        if normalize_filename(x)
    }

    retrieved_stems = set(
        stem(x)
        for x in retrieved_sources
        if normalize_filename(x)
    )

    if not expected_by_stem:
        return 0, []

    missing = sorted(
        original
        for s, original in expected_by_stem.items()
        if s not in retrieved_stems
    )

    found_count = sum(
        1
        for s in expected_by_stem
        if s in retrieved_stems
    )

    recall = (
        1
        if found_count == len(expected_by_stem)
        else 0
    )

    return recall, missing


# ---------------------------------------------------------
# Simple answer normalization
# ---------------------------------------------------------

def normalize_answer(
    answer: str,
) -> str:

    if not answer:
        return ""

    answer = answer.lower()

    answer = answer.replace(
        "–",
        "-",
    )

    answer = answer.replace(
        "—",
        "-",
    )

    answer = answer.replace(
        "\u202f",
        " ",
    )

    answer = re.sub(
        r"\s+",
        " ",
        answer,
    )

    return answer.strip()


# ---------------------------------------------------------
# Role/title abbreviation equivalence
#
# Reference answers often use an abbreviation ("CFO") while a
# generated answer spells it out ("Chief Financial Officer"),
# or vice versa. Treat these as equivalent so a substantively
# correct answer isn't penalized for spelling choice.
# ---------------------------------------------------------

ROLE_ABBREVIATIONS = {
    "ceo": "chief executive officer",
    "cfo": "chief financial officer",
    "coo": "chief operating officer",
    "cto": "chief technology officer",
    "ciso": "chief information security officer",
    "vp": "vice president",
    "svp": "senior vice president",
    "hr": "human resources",
}


def _token_present(
    token: str,
    text: str,
) -> bool:

    if token in text:
        return True

    expansion = ROLE_ABBREVIATIONS.get(
        token
    )

    if expansion and expansion in text:
        return True

    return False


# ---------------------------------------------------------
# Simple lexical answer check
# ---------------------------------------------------------

def answer_has_reference_information(
    generated: str,
    reference: str,
) -> int:

    generated_norm = normalize_answer(
        generated
    )

    reference_norm = normalize_answer(
        reference
    )

    if not generated_norm:
        return 0

    if not reference_norm:
        return 0

    # Exact match
    if generated_norm == reference_norm:
        return 1

    # Check whether important reference tokens occur.
    #
    # Trailing periods get glued onto the preceding token by
    # this regex (e.g. a reference ending "...E-204." tokenizes
    # as "e-204." rather than "e-204."), which then never matches
    # a generated answer that (correctly) omits the sentence-
    # final period. Strip trailing periods per-token to avoid
    # penalizing correct short-form answers for punctuation.
    reference_tokens = re.findall(
        r"[a-z0-9$%€£₹.-]+",
        reference_norm,
    )

    reference_tokens = [
        token.rstrip(".")
        for token in reference_tokens
    ]

    if not reference_tokens:
        return 0

    important_tokens = [
        token
        for token in reference_tokens
        if len(token) >= 3
    ]

    if not important_tokens:
        return 0

    matched = sum(
        1
        for token in important_tokens
        if _token_present(token, generated_norm)
    )

    ratio = (
        matched
        / len(important_tokens)
    )

    return 1 if ratio >= 0.5 else 0


# ---------------------------------------------------------
# Safe division
# ---------------------------------------------------------

def safe_divide(
    numerator: float,
    denominator: float,
) -> float:

    if denominator == 0:
        return 0.0

    return numerator / denominator


# ---------------------------------------------------------
# CSV writer
# ---------------------------------------------------------

FIELDNAMES = [
    "Question ID",
    "Category",
    "Method",
    "R_q",
    "G_q",
    "A_q",
    "Latency (s)",
    "Retrieval Latency (s)",
    "Generation Latency (s)",
    "Input Tokens",
    "Output Tokens",
    "Cost ($)",
    "Retrieved Sources",
    "Missing Sources",
    "Generated Answer",
    "Reference Answer",
    "Notes",
]


def write_results(
    results: list[dict[str, Any]],
):

    with open(
        OUTPUT_PATH,
        "w",
        encoding="utf-8",
        newline="",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=FIELDNAMES,
        )

        writer.writeheader()

        for row in results:

            writer.writerow(row)


# ---------------------------------------------------------
# Load questions
# ---------------------------------------------------------

def load_questions():

    if not QUESTIONS_PATH.exists():

        raise FileNotFoundError(
            f"Questions file not found:\n"
            f"{QUESTIONS_PATH}"
        )

    with open(
        QUESTIONS_PATH,
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:

        reader = csv.DictReader(
            file
        )

        questions = list(reader)

    if not questions:

        raise RuntimeError(
            "questions.csv contains no questions."
        )

    required = {
        "Question ID",
        "Category",
        "Question",
        "Reference Answer",
        "Source Documents",
    }

    missing = (
        required
        - set(reader.fieldnames or [])
    )

    if missing:

        raise RuntimeError(
            "questions.csv is missing columns: "
            + ", ".join(
                sorted(missing)
            )
        )

    return questions


# ---------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------

def main():

    print("=" * 70)
    print("VECTORLESS RAG EVALUATION")
    print("=" * 70)

    print(
        f"Tree     : {TREE_PATH}"
    )

    print(
        f"Questions: {QUESTIONS_PATH}"
    )

    print(
        f"Output   : {OUTPUT_PATH}"
    )

    # -----------------------------------------------------
    # Check files
    # -----------------------------------------------------

    if not TREE_PATH.exists():

        raise FileNotFoundError(
            f"Tree file not found:\n"
            f"{TREE_PATH}"
        )

    # -----------------------------------------------------
    # Load tree
    # -----------------------------------------------------

    print(
        "\nLoading PageIndex tree..."
    )

    with open(
        TREE_PATH,
        "r",
        encoding="utf-8",
    ) as file:

        tree = json.load(
            file
        )

    # -----------------------------------------------------
    # Add document source to descendants
    # -----------------------------------------------------

    propagate_document_names(
        tree
    )

    # -----------------------------------------------------
    # Flatten nodes
    # -----------------------------------------------------

    print(
        "Building searchable nodes..."
    )

    nodes = flatten_nodes(
        tree
    )

    print(
        f"Nodes indexed: {len(nodes)}"
    )

    if not nodes:

        raise RuntimeError(
            "No searchable nodes found in "
            "pageindex_tree.json."
        )

    # -----------------------------------------------------
    # Build the BM25 index once. Retrieval for every question
    # below re-uses this same index instead of re-tokenizing
    # the whole corpus per question.
    # -----------------------------------------------------

    print(
        "Building BM25 index..."
    )

    index = BM25Index(nodes)

    # -----------------------------------------------------
    # Load questions
    # -----------------------------------------------------

    questions = load_questions()

    print(
        f"Questions loaded: {len(questions)}"
    )

    # -----------------------------------------------------
    # Results
    # -----------------------------------------------------

    results = []

    successful_questions = 0

    total_retrieval_latency = 0.0
    total_generation_latency = 0.0

    total_input_tokens = 0
    total_output_tokens = 0
    total_cost = 0.0

    retrieval_hits = 0
    generation_hits = 0
    answer_hits = 0

    # -----------------------------------------------------
    # Evaluation loop
    # -----------------------------------------------------

    for question_num, question_row in enumerate(
        questions,
        start=1,
    ):

        question_id = (
            question_row["Question ID"]
        )

        category = (
            question_row["Category"]
        )

        question = (
            question_row["Question"]
        )

        reference = (
            question_row["Reference Answer"]
        )

        expected_sources = (
            normalize_source_list(
                question_row[
                    "Source Documents"
                ]
            )
        )

        print(
            "\n"
            + "=" * 70
        )

        print(
            f"[{question_num}/{len(questions)}] "
            f"Question {question_id}"
        )

        print(
            f"Category: {category}"
        )

        print(
            f"Question: {question}"
        )

        start_total = time.perf_counter()

        retrieval_start = (
            time.perf_counter()
        )

        try:

            retrieved = index.search(
                question,
            )

            retrieval_latency = (
                time.perf_counter()
                - retrieval_start
            )

        except Exception as exc:

            retrieval_latency = (
                time.perf_counter()
                - retrieval_start
            )

            print(
                f"Retrieval ERROR: {exc}"
            )

            results.append({
                "Question ID": question_id,
                "Category": category,
                "Method": "Vectorless",
                "R_q": 0,
                "G_q": 0,
                "A_q": 0,
                "Latency (s)": round(
                    retrieval_latency,
                    3,
                ),
                "Retrieval Latency (s)": round(
                    retrieval_latency,
                    3,
                ),
                "Generation Latency (s)": 0,
                "Input Tokens": 0,
                "Output Tokens": 0,
                "Cost ($)": 0.0,
                "Retrieved Sources": "",
                "Missing Sources": "; ".join(
                    expected_sources
                ),
                "Generated Answer": "",
                "Reference Answer": reference,
                "Notes": f"Retrieval error: {exc}",
            })

            write_results(
                results
            )

            continue

        if not retrieved:

            print(
                "No retrieval results."
            )

            missing = expected_sources

            total_latency = (
                time.perf_counter()
                - start_total
            )

            results.append({
                "Question ID": question_id,
                "Category": category,
                "Method": "Vectorless",
                "R_q": 0,
                "G_q": 0,
                "A_q": 0,
                "Latency (s)": round(
                    total_latency,
                    3,
                ),
                "Retrieval Latency (s)": round(
                    retrieval_latency,
                    3,
                ),
                "Generation Latency (s)": 0,
                "Input Tokens": 0,
                "Output Tokens": 0,
                "Cost ($)": 0.0,
                "Retrieved Sources": "",
                "Missing Sources": "; ".join(
                    missing
                ),
                "Generated Answer": "",
                "Reference Answer": reference,
                "Notes": "No retrieval results.",
            })

            write_results(
                results
            )

            continue

        # -------------------------------------------------
        # Top results
        # -------------------------------------------------

        top_results = retrieved[:TOP_K]

        retrieved_sources = (
            get_retrieved_sources(
                top_results
            )
        )

        rq, missing_sources = (
            calculate_source_recall(
                expected_sources,
                retrieved_sources,
            )
        )

        retrieval_hits += rq

        total_retrieval_latency += (
            retrieval_latency
        )

        print(
            "\nRetrieved sources:"
        )

        for source in retrieved_sources:
            print(
                f"  ✓ {source}"
            )

        if missing_sources:

            print(
                "\nMissing expected sources:"
            )

            for source in missing_sources:
                print(
                    f"  ✗ {source}"
                )

        else:

            print(
                "\nAll expected sources retrieved."
            )

        # -------------------------------------------------
        # Build context
        # -------------------------------------------------

        context = build_context(
            top_results
        )

        if not context.strip():

            print(
                "Retrieved nodes contain no text."
            )

            total_latency = (
                time.perf_counter()
                - start_total
            )

            results.append({
                "Question ID": question_id,
                "Category": category,
                "Method": "Vectorless",
                "R_q": rq,
                "G_q": 0,
                "A_q": 0,
                "Latency (s)": round(
                    total_latency,
                    3,
                ),
                "Retrieval Latency (s)": round(
                    retrieval_latency,
                    3,
                ),
                "Generation Latency (s)": 0,
                "Input Tokens": 0,
                "Output Tokens": 0,
                "Cost ($)": 0.0,
                "Retrieved Sources": "; ".join(
                    retrieved_sources
                ),
                "Missing Sources": "; ".join(
                    missing_sources
                ),
                "Generated Answer": "",
                "Reference Answer": reference,
                "Notes": (
                    "Retrieved nodes contained "
                    "no usable text."
                ),
            })

            write_results(
                results
            )

            continue

        # -------------------------------------------------
        # Generate answer
        # -------------------------------------------------

        print(
            "\nGenerating answer..."
        )

        generation_start = (
            time.perf_counter()
        )

        try:

            response = generate_answer(
                question,
                context,
            )

            generation_latency = (
                time.perf_counter()
                - generation_start
            )

            generated_answer = (
                response.get(
                    "answer",
                    "",
                )
            )

            input_tokens = int(
                response.get(
                    "input_tokens",
                    0,
                )
                or 0
            )

            output_tokens = int(
                response.get(
                    "output_tokens",
                    0,
                )
                or 0
            )

            gq = 1 if generated_answer else 0

        except Exception as exc:

            generation_latency = (
                time.perf_counter()
                - generation_start
            )

            generated_answer = ""

            input_tokens = 0
            output_tokens = 0

            gq = 0

            print(
                f"Generation ERROR: {exc}"
            )

        # -------------------------------------------------
        # Answer quality
        # -------------------------------------------------

        if generated_answer:

            aq = answer_has_reference_information(
                generated_answer,
                reference,
            )

        else:

            aq = 0

        generation_hits += gq
        answer_hits += aq

        total_generation_latency += (
            generation_latency
        )

        total_input_tokens += (
            input_tokens
        )

        total_output_tokens += (
            output_tokens
        )

        total_cost += estimate_cost(
            input_tokens,
            output_tokens,
        )

        successful_questions += 1

        total_latency = (
            time.perf_counter()
            - start_total
        )

        print(
            "\nGenerated answer:"
        )

        print(
            generated_answer
        )

        print(
            f"\nR_q={rq} "
            f"G_q={gq} "
            f"A_q={aq}"
        )

        # -------------------------------------------------
        # Save immediately
        # -------------------------------------------------

        notes = ""

        if missing_sources:
            notes += (
                "Some expected sources were not retrieved. "
            )

        if not generated_answer:
            notes += (
                "No answer was generated. "
            )

        if not notes:
            notes = "OK"

        results.append({
            "Question ID": question_id,
            "Category": category,
            "Method": "Vectorless",
            "R_q": rq,
            "G_q": gq,
            "A_q": aq,
            "Latency (s)": round(
                total_latency,
                3,
            ),
            "Retrieval Latency (s)": round(
                retrieval_latency,
                3,
            ),
            "Generation Latency (s)": round(
                generation_latency,
                3,
            ),
            "Input Tokens": input_tokens,
            "Output Tokens": output_tokens,
            "Cost ($)": round(
                estimate_cost(
                    input_tokens,
                    output_tokens,
                ),
                6,
            ),
            "Retrieved Sources": "; ".join(
                retrieved_sources
            ),
            "Missing Sources": "; ".join(
                missing_sources
            ),
            "Generated Answer": generated_answer,
            "Reference Answer": reference,
            "Notes": notes.strip(),
        })

        write_results(
            results
        )

        print(
            f"Saved progress to: "
            f"{OUTPUT_PATH}"
        )

    # -----------------------------------------------------
    # Final metrics
    # -----------------------------------------------------

    total_questions = len(
        questions
    )

    print(
        "\n"
        + "=" * 70
    )

    print(
        "FINAL EVALUATION"
    )

    print(
        "=" * 70
    )

    print(
        f"Total questions       : "
        f"{total_questions}"
    )

    print(
        f"Processed successfully: "
        f"{successful_questions}"
    )

    # -----------------------------------------------------
    # SAFE METRICS
    # -----------------------------------------------------

    retrieval_rate = safe_divide(
        retrieval_hits,
        total_questions,
    )

    generation_rate = safe_divide(
        generation_hits,
        total_questions,
    )

    answer_rate = safe_divide(
        answer_hits,
        total_questions,
    )

    avg_retrieval_latency = safe_divide(
        total_retrieval_latency,
        successful_questions,
    )

    avg_generation_latency = safe_divide(
        total_generation_latency,
        successful_questions,
    )

    avg_input_tokens = safe_divide(
        total_input_tokens,
        successful_questions,
    )

    avg_output_tokens = safe_divide(
        total_output_tokens,
        successful_questions,
    )

    print(
        f"\nRetrieval accuracy : "
        f"{retrieval_rate:.2%}"
    )

    print(
        f"Generation success: "
        f"{generation_rate:.2%}"
    )

    print(
        f"Answer accuracy    : "
        f"{answer_rate:.2%}"
    )

    print(
        f"\nAverage retrieval latency: "
        f"{avg_retrieval_latency:.3f}s"
    )

    print(
        f"Average generation latency: "
        f"{avg_generation_latency:.3f}s"
    )

    print(
        f"Average input tokens: "
        f"{avg_input_tokens:.1f}"
    )

    print(
        f"Average output tokens: "
        f"{avg_output_tokens:.1f}"
    )

    avg_cost = safe_divide(
        total_cost,
        successful_questions,
    )

    print(
        f"\nTotal estimated cost: "
        f"${total_cost:.4f}"
    )

    print(
        f"Average cost per question: "
        f"${avg_cost:.5f}"
    )

    print(
        f"\nResults saved to:"
    )

    print(
        OUTPUT_PATH
    )


# ---------------------------------------------------------
# Entry point
# ---------------------------------------------------------

if __name__ == "__main__":
    main()