# PageIndex Multi-Format Parser — v3

This version follows the supplied PageIndex-style example.

## Supported formats

- PDF
- DOCX
- XLSX

## Output

There is one canonical tree:

`output/pageindex_tree.json`

Its shape is:

```text
corpus
└── document
    ├── summary                 <- whole-document summary
    ├── chapter/article
    │   ├── summary             <- structural summary
    │   ├── full_text
    │   └── page
    ├── chapter/article
    │   └── ...
    └── ...
```

### Summary policy

Gemini summarizes:

- document
- chapter
- article
- section
- exhibit
- signatures
- worksheet

Gemini does NOT individually summarize:

- subsection
- page

The whole-document summary is generated **after** structural summaries,
using those summaries as compact context. This avoids sending the entire
raw document to Gemini a second time.

## Rate limiting / 429 protection

Summary generation is optional:

```bash
python main.py input
```

builds the tree without Gemini.

To generate summaries:

```bash
python main.py input --summary
```

Configure `.env`:

```env
GEMINI_API_KEY=YOUR_NEW_API_KEY
GEMINI_MODEL=gemini-3.5-flash
GEMINI_MAX_REQUESTS=5
GEMINI_REQUEST_INTERVAL=15
```

The summarizer:
- preserves existing summaries
- skips nodes that already have summaries
- waits between requests
- retries common 429/503 errors
- stores errors on the affected node instead of destroying the tree

Therefore an interrupted run can be run again.

## Install

```bash
pip install -r requirements.txt
```

## Important DOCX limitation

DOCX files do not reliably expose rendered page numbers through
`python-docx`. This parser therefore treats explicit page breaks as logical
page boundaries. For exact Word pagination, a rendering engine would be
needed.

## XLSX representation

Each worksheet is represented as a meaningful `worksheet` node.
Its content is stored as text with:

```text
column A | column B | column C
```

This preserves row/column relationships sufficiently for the current
PageIndex pipeline while keeping the original values.

## Security

Never commit `.env` or a real API key. If a key has been exposed, revoke it
and create a new one.
