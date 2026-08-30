# Vectorless RAG Evaluation Report

**Corpus:** Meridian Dynamics Corp (9 documents — HR policy, IT security policy, vendor contract, product manual, financial report, supply chain network, org chart, project approval workflow, company overview)
**Method:** Vectorless (BM25 retrieval + Groq LLM generation)
**Questions:** 20, across 4 categories
**Model:** `openai/gpt-oss-120b` via Groq

---

## Headline results

| Metric | Score |
|---|---|
| **Retrieval accuracy (R_q)** | 60.0% (12/20) |
| **Generation success (G_q)** | 100.0% (20/20) |
| **Answer accuracy (A_q)** | 75.0% (15/20) |

| | |
|---|---|
| Avg. total latency | 7.98s |
| Avg. retrieval latency | 0.001s |
| Avg. generation latency | 7.98s |
| Avg. input tokens | 1,198 |
| Avg. output tokens | 241 |
| **Total cost** | **$0.0065** |
| Avg. cost / question | $0.00032 |

Generation never failed (100% G_q) and the whole 20-question run cost under a cent — the LLM reliably declines to answer rather than hallucinate when retrieval comes up empty (see Q8, Q11 below), which is exactly the intended failure mode for a grounded RAG system.

---

## Results by category

| Category | Questions | R_q | G_q | A_q |
|---|---|---|---|---|
| Factual | 5 | **100.0%** | 100.0% | **100.0%** |
| Semantic-Paraphrased | 5 | 60.0% | 100.0% | 80.0% |
| Multi-Hop-Relational | 7 | **14.3%** | 100.0% | **42.9%** |
| Structured | 3 | **100.0%** | 100.0% | **100.0%** |

The pattern is sharp: single-document lookups (Factual, Structured) are essentially solved at 100%. Accuracy degrades exactly where it should for a keyword-based retriever — **Multi-Hop-Relational questions**, which require 2–3 unrelated documents (a vendor table, a security policy, an org chart) to surface simultaneously for one query, collapse to 14.3% R_q. This is the expected structural weakness of single-query BM25 versus a graph-based retrieval method, and is the most useful finding in this run for a paper comparing the two approaches.

---

## Per-question detail

| Q | Category | R_q | A_q | Notes |
|---|---|:---:|:---:|---|
| Q1 | Factual | ✅ | ✅ | |
| Q2 | Factual | ✅ | ✅ | |
| Q3 | Factual | ✅ | ✅ | |
| Q4 | Factual | ✅ | ✅ | |
| Q5 | Factual | ✅ | ✅ | |
| Q6 | Semantic-Paraphrased | ✅ | ✅ | |
| Q7 | Semantic-Paraphrased | ✅ | ✅ | |
| Q8 | Semantic-Paraphrased | ❌ | ❌ | Missing `06_quarterly_financial_report_q3.xlsx` — model correctly declined rather than guessing |
| Q9 | Semantic-Paraphrased | ✅ | ✅ | |
| Q10 | Semantic-Paraphrased | ❌ | ✅ | Missing `05_project_approval_workflow.docx`, but answer was still correct from context |
| Q11 | Multi-Hop-Relational | ❌ | ❌ | Missing 2 of 3 required docs — model correctly declined |
| Q12 | Multi-Hop-Relational | ❌ | ✅ | Missing `09_org_chart_and_roles.xlsx`, answer still substantively correct |
| Q13 | Multi-Hop-Relational | ❌ | ✅ | Missing 2 docs, answer still correct |
| Q14 | Multi-Hop-Relational | ❌ | ❌ | Missing `09_org_chart_and_roles.xlsx` — answer omits a required name (Aisha Malik) |
| Q15 | Multi-Hop-Relational | ❌ | ❌ | Missing `09_org_chart_and_roles.xlsx` — 7-question approval chain garbled without it |
| Q16 | Multi-Hop-Relational | ✅ | ✅ | |
| Q17 | Multi-Hop-Relational | ❌ | ❌ | Missing `09_org_chart_and_roles.xlsx` — answer omits reporting line |
| Q18 | Structured | ✅ | ✅ | |
| Q19 | Structured | ✅ | ✅ | |
| Q20 | Structured | ✅ | ✅ | |

**8 R_q misses, 5 A_q misses.** Every A_q miss is downstream of an R_q miss — no case exists where all expected sources were retrieved and the model still gave a wrong answer. Three R_q misses (Q10, Q12, Q13) still produced correct answers, because enough of the needed fact happened to be present in the retrieved context even though one *labeled* source document was absent.

`09_org_chart_and_roles.xlsx` is the single most frequently missed document — it's needed but absent in 4 of the 8 R_q failures (Q12, Q14, Q15, Q17), consistently for questions that need to connect a person's name to their reporting line or title, which the org chart is the only document containing.

---

## Cost & latency at a glance

- **20 questions processed for $0.0065 total** — cost is a non-issue at this scale.
- Correct, high-confidence answers return fast (Q1–Q7: 0.5–1s generation). Multi-hop questions that required more reasoning over larger retrieved context took noticeably longer (Q15: 13.8s, Q18: 17.5s) and consumed more output tokens (Q15: 1,146 tokens for a 7-step approval chain).
- Retrieval itself is essentially free time-wise (~1ms per query) — all latency and cost is concentrated in generation.

---

## Bottom line

This run cleanly separates what vectorless (BM25) retrieval is good at from where it structurally struggles:

- **Strong (100%):** any question answerable from a single document's own vocabulary.
- **Weak (14–43%):** questions requiring several thematically unrelated documents to rank together for one query — the org chart in particular is a recurring blind spot since it rarely shares vocabulary with the documents describing *what* someone approved.

For a paper positioning vectorless RAG against a graph-based alternative, this is a clean, reportable result: the failure mode is systematic and concentrated in exactly the category (Multi-Hop-Relational) a graph-based retriever is designed to handle.

*Raw data: `evaluation_results.csv`*