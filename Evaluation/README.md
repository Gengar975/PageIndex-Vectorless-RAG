# 📊 Vectorless RAG Evaluation Report

> **Comprehensive performance benchmark of a Vectorless RAG pipeline (BM25 Retrieval + Groq LLM Generation) across multi-category corporate queries.**

[![Retriever](https://img.shields.io/badge/Retriever-BM25-blue.svg)](#)
[![Generator](https://img.shields.io/badge/Model-openai%2Fgpt--oss--120b_(Groq)-orange.svg)](#)
[![Generation Success](https://img.shields.io/badge/Generation_Success-100%25-brightgreen.svg)](#)
[![Total Cost](https://img.shields.io/badge/Run_Cost-%240.0065-success.svg)](#)

---

## 📌 Executive Summary

* **100% Generation Reliability ($G_q$):** Zero generation crashes or hallucinations; the model appropriately declined when context was missing.
* **Cost-Efficient:** The complete 20-question evaluation suite ran for **$0.0065** (~$0.00032/query).
* **Clear Failure Boundary:** 100% accuracy on single-document lookups vs. structural degradation down to **14.3% retrieval accuracy** on multi-hop queries requiring multi-document synthesis.

---

## ⚙️ Benchmark Setup

* **Corpus:** Meridian Dynamics Corp (9 cross-functional documents: HR policy, IT security, vendor contracts, product manual, financial reports, supply chain, org chart, approval workflows, company overview)
* **Retriever:** BM25 (Vectorless keyword search)
* **LLM / Inference:** `openai/gpt-oss-120b` via Groq Cloud
* **Evaluation Set:** 20 test queries across 4 difficulty tiers

---

## 📈 Headline Metrics

| Core Metric | Result | Benchmark Dimension | Value |
|:---|:---:|:---|:---:|
| **Retrieval Accuracy ($R_q$)** | **60.0%** (12/20) | **Avg. Retrieval Latency** | 0.001s (1ms) |
| **Generation Success ($G_q$)** | **100.0%** (20/20) | **Avg. Generation Latency** | 7.98s |
| **Answer Accuracy ($A_q$)** | **75.0%** (15/20) | **Avg. Input / Output Tokens** | 1,198 / 241 |
| **Total Evaluation Cost** | **$0.0065** | **Avg. Cost / Question** | $0.00032 |

---

## 🔬 Performance by Query Category

| Category | Queries | Retrieval Accuracy ($R_q$) | Generation Rate ($G_q$) | Answer Accuracy ($A_q$) |
|:---|:---:|:---:|:---:|:---:|
| **Factual** | 5 | **100.0%** | 100.0% | **100.0%** |
| **Structured** | 3 | **100.0%** | 100.0% | **100.0%** |
| **Semantic-Paraphrased** | 5 | **60.0%** | 100.0% | **80.0%** |
| **Multi-Hop-Relational** | 7 | **14.3%** | 100.0% | **42.9%** |

### Key Observations
* **Single-Document Retrieval (Solved):** `Factual` and `Structured` questions achieved perfect (100%) precision because queries share immediate lexical overlap with the corpus.
* **Multi-Hop Bottleneck:** BM25 struggles when an answer requires pulling 2–3 disparate documents simultaneously (e.g., matching a role in an org chart to a step in a policy workflow).

---

## 🔍 Detailed Query-by-Query Breakdown

| ID | Category | Retrieval ($R_q$) | Accuracy ($A_q$) | Diagnostic Notes |
|:---:|:---|:---:|:---:|:---|
| **Q1** | Factual | ✅ | ✅ | Exact match retrieved |
| **Q2** | Factual | ✅ | ✅ | Exact match retrieved |
| **Q3** | Factual | ✅ | ✅ | Exact match retrieved |
| **Q4** | Factual | ✅ | ✅ | Exact match retrieved |
| **Q5** | Factual | ✅ | ✅ | Exact match retrieved |
| **Q6** | Semantic-Paraphrased | ✅ | ✅ | High lexical overlap maintained |
| **Q7** | Semantic-Paraphrased | ✅ | ✅ | Grounded response generated |
| **Q8** | Semantic-Paraphrased | ❌ | ❌ | Missing `06_quarterly_financial_report_q3.xlsx` (Model safely declined) |
| **Q9** | Semantic-Paraphrased | ✅ | ✅ | Grounded response generated |
| **Q10** | Semantic-Paraphrased | ❌ | ✅ | Missing `05_project_approval_workflow.docx`; core answer recovered from retrieved context |
| **Q11** | Multi-Hop-Relational | ❌ | ❌ | Missing 2/3 required docs (Model safely declined) |
| **Q12** | Multi-Hop-Relational | ❌ | ✅ | Missing `09_org_chart_and_roles.xlsx`; substantive facts recovered |
| **Q13** | Multi-Hop-Relational | ❌ | ✅ | Missing 2 docs; partial context sufficient for correct synthesis |
| **Q14** | Multi-Hop-Relational | ❌ | ❌ | Missing `09_org_chart_and_roles.xlsx` (Omitted key stakeholder name) |
| **Q15** | Multi-Hop-Relational | ❌ | ❌ | Missing `09_org_chart_and_roles.xlsx` (Approval sequence degraded) |
| **Q16** | Multi-Hop-Relational | ✅ | ✅ | All supporting documents retrieved |
| **Q17** | Multi-Hop-Relational | ❌ | ❌ | Missing `09_org_chart_and_roles.xlsx` (Omitted reporting chain) |
| **Q18** | Structured | ✅ | ✅ | Direct tabular lookup |
| **Q19** | Structured | ✅ | ✅ | Direct tabular lookup |
| **Q20** | Structured | ✅ | ✅ | Direct tabular lookup |

---

## 🧠 Failure Analysis & Insights

* **Root Cause Dependency:** 100% of answer failures ($A_q$) stemmed directly from retrieval misses ($R_q$). When relevant context was fully present, accuracy was 100%.
* **The Org Chart Blindspot:** `09_org_chart_and_roles.xlsx` accounted for **50% (4/8)** of all retrieval failures. Keyword-based BM25 fails to link person-role relationships across files lacking shared lexical vocabulary.
* **Groundedness:** The model demonstrated strict factual alignment by declining to guess (e.g., Q8, Q11) rather than hallucinating when source context was missing.

---

## ⚡ Latency & Cost Profile

* **Retrieval Overhead:** Near-zero runtime (~1ms per query).
* **Generation Dynamics:** Simple factual queries resolved in 0.5–1.0s. Complex multi-hop queries (e.g., Q15 at 13.8s, Q18 at 17.5s) demanded significantly higher output token synthesis.
* **Data Source:** Raw logs available in [`evaluation_results.csv`](./evaluation_results.csv).
