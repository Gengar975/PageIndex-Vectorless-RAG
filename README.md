# 📄 PageIndex Multi-Format Parser (v3)

> **Structured hierarchical document ingestion and semantic summarization engine for multi-format corpora (PDF, DOCX, XLSX).**

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](#)
[![Supported Formats](https://img.shields.io/badge/Formats-PDF%20%7C%20DOCX%20%7C%20XLSX-brightgreen.svg)](#)
[![LLM Engine](https://img.shields.io/badge/Summarizer-Gemini%20Flash-orange.svg)](#)
[![Evaluation Report](https://img.shields.io/badge/Benchmark-Evaluation_Report-purple.svg)](./Evaluation/README.md)
[![Status](https://img.shields.io/badge/Status-Active-success.svg)](#)

---

## 📊 Performance Benchmark & Evaluation

For full benchmark metrics, retrieval latency, and accuracy breakdowns across multi-hop and factual categories:

👉 **[View the Full Vectorless RAG Evaluation Report →](./Evaluation/README.md)**

* **Retrieval Accuracy ($R_q$):** 60.0%
* **Answer Accuracy ($A_q$):** 75.0%
* **Avg. Retrieval Latency:** 1ms (BM25)
* **Full Data:** [`Evaluation/evaluation_results.csv`](./Evaluation/evaluation_results.csv)

---

## 📌 Overview

PageIndex Multi-Format Parser standardizes unstructured heterogeneous documents into a unified, hierarchical JSON tree (`pageindex_tree.json`). It provides structured node traversal and contextual multi-stage summarization powered by Google Gemini, designed with built-in rate-limiting and fault tolerance.

---

## 📑 Supported Formats & Parsing Behavior

| Format | Parsing Engine / Behavior | Representation Notes |
|:---:|:---|:---|
| **`.pdf`** | Structural text & page extraction | Native page and boundary tracking |
| **`.docx`** | `python-docx` boundary parser | Uses explicit page breaks as logical boundaries |
| **`.xlsx`** | Worksheet-to-text matrix parser | Flattens rows into delimited text (`Col A \| Col B \| Col C`) |

---

## 🌳 Output Hierarchy

All processed documents are output into a canonical tree at:
`Ingestion/output/pageindex_tree.json`

### Tree Architecture

```text
corpus
└── document
    ├── summary                 <-- Whole-document contextual summary
    ├── chapter / article
    │   ├── summary             <-- Structural section summary
    │   ├── full_text
    │   └── page
    ├── chapter / article
    │   └── ...
    └── ...
