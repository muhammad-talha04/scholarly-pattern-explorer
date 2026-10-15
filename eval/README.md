# Search evaluation (owner: michal)

`search_queries.jsonl`: 35 realistic student queries across the fields in our
corpus (quantum, medical AI, NLP, AI methods, optimisation, energy, security,
robotics, education, AI and society). Topic names come from the topics in
`docs/data/*_patterns.csv`, so they match OpenAlex topic `display_name`s.

Each line has these fields:

| field | meaning |
|---|---|
| `id` | `q01` ... |
| `query` | what a student would type |
| `field` | broad area, for per-field breakdowns |
| `keywords` | lower-case substrings that signal relevance |
| `topics` | OpenAlex topic names that count as highly relevant |
| `openalex_ids` | hand-checked relevant work IDs. **Empty for now**: the repo has no work data with IDs, and we do not make IDs up. Fill these in from `data/works_v2.jsonl` once it is ingested. |

## Relevance and metrics
Each paper's grade is computed from the corpus (see `run_search_eval.py`):
2 if it is in `openalex_ids` or has one of the `topics`; 1 if the title has a
keyword or the abstract has at least 2 keywords; 0 otherwise.

- `recall@k`: relevant papers in the top k divided by all relevant papers in the corpus.
- `recall_capped@k`: the same, divided by min(relevant, k), so large topics can still score 1.
- `ndcg@k`: graded nDCG with gain 2^g - 1.

Queries with no relevant paper in the corpus are skipped and reported.

## Run
```bash
python eval/run_search_eval.py --works data/works_v2.jsonl --k 10 --out eval/report.json
ML_EMBEDDER=hash python eval/run_search_eval.py --works data/works_v2.jsonl  # offline smoke only
```
The hash embedder is only there to check the plumbing. Its scores mean
nothing. Report numbers from the real all-MiniLM-L6-v2 model.
Tests: `ml/tests/test_search_eval.py`.

## Embedding benchmark (model comparison)

Separate from the keyword grades above. This one reads a hand-labelled CSV:

```
query_id,query,work_id,relevance
```

`relevance` is a number. Above 0 counts as relevant for recall@10. nDCG@10
uses the grade (`2^grade - 1`). Rows that share a `query_id` must use the same
query text. A repeated work id keeps the higher grade. Papers that are not
listed for a query are grade 0, and a listed id that is missing from the
corpus counts as a miss.

`eval/benchmark_queries.csv` and `eval/benchmark_sample_papers.json` are a
tiny example so the harness runs before a real labelled set exists. Replace
the CSV (and point `--papers` at the corpus) when that set is ready.

```bash
python -m ml.benchmark --queries eval/benchmark_queries.csv --papers eval/benchmark_sample_papers.json --out eval/benchmark_report.json
ML_EMBEDDER=hash python -m ml.benchmark   # offline smoke; ignore the scores
```

Models: `sentence-transformers/all-MiniLM-L6-v2` (default), `BAAI/bge-small-en-v1.5`,
`intfloat/e5-small-v2`. All three are 384-d. SPECTER2 is omitted because it is
768-d and needs the adapters library. The default changes only if another
model is at least 0.05 higher on both recall@10 and nDCG@10.

### Results on the tiny sample

CPU run of the real weights on the 24-paper sample (`eval/benchmark_report.json`):

| model | recall@10 | nDCG@10 |
|---|---|---|
| sentence-transformers/all-MiniLM-L6-v2 | 1.0 | 0.9974 |
| BAAI/bge-small-en-v1.5 | 1.0 | 0.9974 |
| intfloat/e5-small-v2 | 1.0 | 0.9974 |

Decision: **keep `all-MiniLM-L6-v2`**. No model leads by 0.05 on both metrics.
The tie is in the metrics, not in the vectors. On the protein query every
model ranks W06, W07, W09, W08 in that order (a translation paper sits above
the grade-1 docking paper, which is why nDCG is 0.9974 rather than 1). The
fifth hit differs: W02 for MiniLM and bge, W18 for e5. Recall@10 cannot
separate them on a 24-paper corpus. Replace the CSV with the hand-labelled
set before treating a difference as a reason to change the default.

Tests: `ml/tests/test_benchmark.py`. The real MiniLM index/search/galaxy path
is `ml/tests/test_embedder_real.py` (`ML_RUN_REAL_EMBED=1`).
