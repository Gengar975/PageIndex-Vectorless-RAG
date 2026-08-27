"""
Gemini summaries for meaningful structural nodes.

PageIndex summary design:

corpus
└── document
    ├── summary
    └── section/article/exhibit/worksheet
        ├── summary
        ├── full_text
        └── children

Important rules:
- Only meaningful structural nodes are summarized.
- Page and subsection nodes are NOT sent to Gemini individually.
- Existing summaries are preserved.
- Failed summaries can be retried on a later run.
- The request limit is enforced per execution.
- Retryable Gemini errors are retried with backoff.
- The tree can be saved after every successful summary.
- Document summaries are generated from structural summaries,
  not from the entire raw document.
"""

import json
import os
import random
import time
from pathlib import Path
from typing import Any, Callable, Optional

from dotenv import load_dotenv
from google import genai


# -------------------------------------------------------------
# Environment configuration
# -------------------------------------------------------------

load_dotenv()

MODEL_NAME = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.6-flash",
)

MAX_REQUESTS = int(
    os.getenv(
        "GEMINI_MAX_REQUESTS",
        "5",
    )
)

REQUEST_INTERVAL = float(
    os.getenv(
        "GEMINI_REQUEST_INTERVAL",
        "15",
    )
)


# -------------------------------------------------------------
# Runtime state
# -------------------------------------------------------------

_client = None
_requests_made = 0


# -------------------------------------------------------------
# Node types that are meaningful Gemini summary targets
# -------------------------------------------------------------

SUMMARY_NODE_TYPES = {
    "document",
    "chapter",
    "article",
    "section",
    "exhibit",
    "signatures",
    "worksheet",
}


# -------------------------------------------------------------
# Gemini client
# -------------------------------------------------------------

def _get_client():
    global _client

    if _client is not None:
        return _client

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY environment variable is not set."
        )

    _client = genai.Client(
        api_key=api_key
    )

    return _client


# -------------------------------------------------------------
# Error helpers
# -------------------------------------------------------------

def _is_retryable_error(exc: Exception) -> bool:
    """
    Determine whether a Gemini error is potentially temporary.

    Retryable:
        429
        RESOURCE_EXHAUSTED
        503
        UNAVAILABLE

    However, an explicit free-tier quota exhaustion message is
    treated as a run-stopping condition because waiting a few
    seconds will not restore the quota.
    """

    message = str(exc).upper()

    if (
        "QUOTA EXHAUSTED" in message
        or "QUOTA_EXCEEDED" in message
        or "FREE TIER" in message
        or "PER DAY" in message
        or "PER MINUTE" in message
        or "LIMIT: 5" in message
        or "REQUEST LIMIT REACHED" in message
    ):
        return False

    return (
        "429" in message
        or "RESOURCE_EXHAUSTED" in message
        or "503" in message
        or "UNAVAILABLE" in message
    )


def _requests_remaining() -> int:
    return max(
        0,
        MAX_REQUESTS - _requests_made,
    )


# -------------------------------------------------------------
# Gemini request
# -------------------------------------------------------------

def _call_gemini(prompt: str) -> str:
    """
    Send one prompt to Gemini.

    The configured MAX_REQUESTS value is a hard limit for this
    Python execution.

    Every actual API attempt counts toward that limit.

    This prevents retries from accidentally exceeding the
    configured request budget.
    """

    global _requests_made

    max_retries = 4

    for attempt in range(max_retries):

        # -----------------------------------------------------
        # Check request budget BEFORE making the request.
        # -----------------------------------------------------

        if _requests_made >= MAX_REQUESTS:
            raise RuntimeError(
                "Gemini request limit reached for this run "
                f"({MAX_REQUESTS})."
            )

        # -----------------------------------------------------
        # Wait between API calls.
        # -----------------------------------------------------

        if _requests_made > 0:
            time.sleep(
                REQUEST_INTERVAL
            )

        # -----------------------------------------------------
        # Count the actual API attempt.
        # -----------------------------------------------------

        _requests_made += 1

        try:
            response = _get_client().models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
            )

            output = getattr(
                response,
                "text",
                None,
            )

            if not output:
                raise RuntimeError(
                    "Gemini returned an empty response."
                )

            return output.strip()

        except Exception as exc:

            message = str(exc)

            # -------------------------------------------------
            # If no requests remain, do not retry.
            # -------------------------------------------------

            if _requests_remaining() <= 0:
                raise

            # -------------------------------------------------
            # Non-retryable errors stop immediately.
            # -------------------------------------------------

            if not _is_retryable_error(exc):
                raise

            # -------------------------------------------------
            # Last retry attempt.
            # -------------------------------------------------

            if attempt == max_retries - 1:
                raise

            # -------------------------------------------------
            # Exponential backoff.
            # -------------------------------------------------

            delay = max(
                REQUEST_INTERVAL,
                15 * (2 ** attempt),
            ) + random.uniform(
                0,
                2,
            )

            print(
                "  Gemini retryable error."
            )

            print(
                f"  Waiting {delay:.1f}s "
                f"before retry..."
            )

            time.sleep(delay)

    raise RuntimeError(
        "Gemini request failed after retries."
    )


# -------------------------------------------------------------
# Text extraction helpers
# -------------------------------------------------------------

def _get_node_text(
    node: dict[str, Any],
) -> str:
    """
    Obtain the best available source text for a node.

    Priority:
        1. full_text
        2. text
        3. combined subsection text

    Page and subsection nodes are normally excluded before this
    function is called, but the fallback makes the generator
    tolerant of slightly different tree structures.
    """

    full_text = node.get(
        "full_text",
        "",
    )

    if isinstance(full_text, str):
        full_text = full_text.strip()

        if full_text:
            return full_text

    text = node.get(
        "text",
        "",
    )

    if isinstance(text, str):
        text = text.strip()

        if text:
            return text

    subsection_parts = []

    for child in node.get(
        "children",
        [],
    ):
        if child.get("type") != "subsection":
            continue

        subsection_text = child.get(
            "full_text",
            child.get(
                "text",
                "",
            ),
        )

        if isinstance(
            subsection_text,
            str,
        ):
            subsection_text = subsection_text.strip()

            if subsection_text:
                subsection_parts.append(
                    subsection_text
                )

    return "\n".join(
        subsection_parts
    ).strip()


# -------------------------------------------------------------
# Structural node summary
# -------------------------------------------------------------

def generate_node_summary(
    title: str,
    text: str,
    node_type: str,
) -> str:

    if not text.strip():
        return ""

    prompt = f"""
You are a document summarization component for a PageIndex
vectorless RAG system.

Summarize the supplied {node_type}.

Rules:
- Use ONLY information present in the supplied content.
- Do not invent, infer, or assume facts.
- Preserve important names, numbers, dates, obligations,
  limits, conditions, references, formulas, identifiers,
  technical terms, and relationships.
- For spreadsheet content, preserve important row/column
  relationships and significant values.
- Focus on information that could help a future retrieval
  system determine whether this node is relevant to a query.
- Be concise but informative.
- Write one clear paragraph.
- Do not begin with "Summary:".
- Do not mention these instructions.

Title:
{title}

Content:
{text}
""".strip()

    return _call_gemini(
        prompt
    )


# -------------------------------------------------------------
# Document summary context
# -------------------------------------------------------------

def _build_document_summary_context(
    node: dict[str, Any],
) -> str:
    """
    Build document-summary context from already generated
    structural summaries.

    We intentionally do NOT send the entire raw document to
    Gemini again.
    """

    parts = []

    for child in node.get(
        "children",
        [],
    ):

        child_type = child.get(
            "type",
            "",
        )

        if child_type not in SUMMARY_NODE_TYPES:
            continue

        if child_type == "document":
            continue

        child_summary = child.get(
            "summary",
            "",
        )

        if not isinstance(
            child_summary,
            str,
        ):
            continue

        child_summary = child_summary.strip()

        if not child_summary:
            continue

        title = child.get(
            "title",
            "",
        )

        parts.append(
            f"{title}: {child_summary}"
        )

    return "\n".join(parts)


# -------------------------------------------------------------
# Whole-document summary
# -------------------------------------------------------------

def generate_document_summary(
    title: str,
    structural_summaries: str,
) -> str:

    if not structural_summaries.strip():
        return ""

    prompt = f"""
You are creating the overall summary of a document for a
PageIndex vectorless RAG system.

Create ONE concise but informative paragraph describing the
document as a whole.

Rules:
- Use ONLY the supplied structural summaries.
- Do not invent facts.
- Preserve important names, purpose, major topics,
  obligations, dates, amounts, conditions, and relationships
  when they appear in the supplied summaries.
- Do not describe your process.
- Do not mention these instructions.
- Do not begin with "Summary:".

Document title:
{title}

Structural summaries:
{structural_summaries}
""".strip()

    return _call_gemini(
        prompt
    )


# -------------------------------------------------------------
# Structural node processing
# -------------------------------------------------------------

def process_structural_nodes(
    node: dict[str, Any],
    save_callback: Optional[
        Callable[[dict[str, Any]], None]
    ] = None,
) -> None:
    """
    Generate summaries for meaningful structural nodes.

    Pages and subsections are deliberately skipped.

    Children are processed before their parent so that the
    document-level summary can later use structural summaries.
    """

    for child in node.get(
        "children",
        [],
    ):
        process_structural_nodes(
            child,
            save_callback,
        )

    node_type = node.get(
        "type",
        "",
    )

    # ---------------------------------------------------------
    # Documents are processed separately after structural
    # children have been summarized.
    # ---------------------------------------------------------

    if node_type == "document":
        return

    # ---------------------------------------------------------
    # Ignore non-structural node types.
    # ---------------------------------------------------------

    if node_type not in SUMMARY_NODE_TYPES:
        return

    # ---------------------------------------------------------
    # Explicitly skip pages and subsections.
    # ---------------------------------------------------------

    if node_type in {
        "page",
        "subsection",
    }:
        return

    # ---------------------------------------------------------
    # Never regenerate a successful summary.
    # ---------------------------------------------------------

    existing_summary = node.get(
        "summary",
        "",
    )

    if isinstance(
        existing_summary,
        str,
    ) and existing_summary.strip():

        print(
            f"Skipping existing summary: "
            f"{node.get('id', 'unknown')} | "
            f"{node.get('title', '')}"
        )

        return

    # ---------------------------------------------------------
    # Get source text.
    # ---------------------------------------------------------

    text = _get_node_text(
        node
    )

    if not text:
        print(
            f"Skipping empty node: "
            f"{node.get('id', 'unknown')} | "
            f"{node.get('title', '')}"
        )

        return

    print(
        f"Generating summary: "
        f"{node.get('id', 'unknown')} | "
        f"{node.get('title', '')}"
    )

    try:

        summary = generate_node_summary(
            title=node.get(
                "title",
                "",
            ),
            text=text,
            node_type=node_type,
        )

        if not summary:
            raise RuntimeError(
                "Gemini returned an empty summary."
            )

        node["summary"] = summary

        # A successful summary means an old error is no longer
        # relevant.
        node.pop(
            "summary_error",
            None,
        )

        print(
            "  OK"
        )

        # -----------------------------------------------------
        # Save immediately after success.
        # -----------------------------------------------------

        if save_callback is not None:
            save_callback(node)

    except Exception as exc:

        node["summary_error"] = str(
            exc
        )

        print(
            f"  ERROR: {exc}"
        )


# -------------------------------------------------------------
# Document summary processing
# -------------------------------------------------------------

def process_document_summary(
    document_node: dict[str, Any],
    save_callback: Optional[
        Callable[[dict[str, Any]], None]
    ] = None,
) -> None:

    # ---------------------------------------------------------
    # Preserve an existing document summary.
    # ---------------------------------------------------------

    existing_summary = document_node.get(
        "summary",
        "",
    )

    if isinstance(
        existing_summary,
        str,
    ) and existing_summary.strip():

        print(
            f"Skipping existing document summary: "
            f"{document_node.get('id', 'unknown')}"
        )

        return

    # ---------------------------------------------------------
    # Build context from structural summaries.
    # ---------------------------------------------------------

    context = _build_document_summary_context(
        document_node
    )

    if not context.strip():

        print(
            f"Skipping document summary because no structural "
            f"summaries are available: "
            f"{document_node.get('id', 'unknown')}"
        )

        return

    print(
        f"Generating document summary: "
        f"{document_node.get('id', 'unknown')}"
    )

    try:

        summary = generate_document_summary(
            title=document_node.get(
                "title",
                "",
            ),
            structural_summaries=context,
        )

        if not summary:
            raise RuntimeError(
                "Gemini returned an empty document summary."
            )

        document_node["summary"] = summary

        document_node.pop(
            "summary_error",
            None,
        )

        print(
            "  OK"
        )

        if save_callback is not None:
            save_callback(
                document_node
            )

    except Exception as exc:

        document_node["summary_error"] = str(
            exc
        )

        print(
            f"  ERROR: {exc}"
        )


# -------------------------------------------------------------
# Complete tree processing
# -------------------------------------------------------------

def process_tree(
    tree: dict[str, Any],
    save_callback: Optional[
        Callable[[dict[str, Any]], None]
    ] = None,
) -> None:
    """
    Process every document in the corpus.

    Order:

        structural summaries
                ↓
        document summary

    Existing successful summaries are preserved.
    """

    global _requests_made

    # Reset request counter whenever process_tree() starts.
    _requests_made = 0

    documents = [
        child
        for child in tree.get(
            "children",
            [],
        )
        if child.get("type") == "document"
    ]

    print(
        f"Documents to process: {len(documents)}"
    )

    print(
        f"Gemini model: {MODEL_NAME}"
    )

    print(
        f"Maximum requests this run: {MAX_REQUESTS}"
    )

    for document in documents:

        print(
            "\n"
            + "=" * 60
        )

        print(
            f"DOCUMENT: "
            f"{document.get('id', 'unknown')} | "
            f"{document.get('title', '')}"
        )

        print(
            "=" * 60
        )

        process_structural_nodes(
            document,
            save_callback,
        )

        process_document_summary(
            document,
            save_callback,
        )

        # -----------------------------------------------------
        # If the request limit has been reached, continue
        # walking the remaining documents. Existing summaries
        # will be preserved and missing ones will record an
        # error. A future run can continue from there.
        # -----------------------------------------------------

    print(
        "\n===== GEMINI SUMMARY RUN COMPLETE ====="
    )

    print(
        f"Requests used: "
        f"{_requests_made}/{MAX_REQUESTS}"
    )


# -------------------------------------------------------------
# Standalone execution
# -------------------------------------------------------------

def save_tree(
    tree: dict[str, Any],
    output_path: str | Path,
) -> None:

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


def main():

    input_file = Path(
        "output/pageindex_tree.json"
    )

    if not input_file.exists():
        raise FileNotFoundError(
            input_file
        )

    with open(
        input_file,
        "r",
        encoding="utf-8",
    ) as file:

        tree = json.load(file)

    process_tree(
        tree,
        save_callback=lambda _node: save_tree(
            tree,
            input_file,
        ),
    )

    save_tree(
        tree,
        input_file,
    )

    print(
        f"\nUpdated: {input_file}"
    )

if __name__ == "__main__":
    main()