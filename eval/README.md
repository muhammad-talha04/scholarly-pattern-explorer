# Search evaluation

Two files, so a teammate's embedding benchmark can read the judgements without
importing this package.

## Queries — `search_queries.jsonl`

40 student-style queries (AI, ML, and nearby CS). Each line:

| field | meaning |
|---|---|
| `id` | `q01` ... `q40` |
| `query` | what a student would type |
| `field` | broad area, for a per-field breakdown |
| `keywords` | lower-case substrings that signal relevance |
| `topics` | OpenAlex topic `display_name`s that count as highly relevant |
| `openalex_ids` | work ids judged relevance 2 for this query (see qrels) |

`eval/run_search_eval.py` still grades a local corpus from these fields
(recall@k and nDCG@k). A paper scores 2 if its id is in `openalex_ids` or it
carries one of `topics`, and 1 if the title has a keyword or the abstract has
at least two. Queries with no relevant paper in the corpus are skipped.

```bash
python eval/run_search_eval.py --works data/works_v2.jsonl --k 10
ML_EMBEDDER=hash python eval/run_search_eval.py --works data/works_v2.jsonl
```

The hash embedder only checks the plumbing. Report MiniLM numbers when the
model is available. Tests: `ml/tests/test_search_eval.py`.

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

## Judgements — `search_qrels.jsonl`

One row per judged work. Exactly these four fields, so another benchmark can
read the file directly:

```json
{"query_id": "q01", "query": "quantum algorithms for near-term quantum computers", "work_id": "W2741809807", "relevance": 2}
```

`relevance` is 0, 1, or 2. Relevant means greater than 0. Work ids are the
OpenAlex short id (`W...`), the same form `ml.papers.Paper.work_id` uses.

Grades come from the free OpenAlex works search (`type:article`), not from
made-up ids:

- **2** — the primary topic is one of the query's `topics`, and a query keyword
  is in the title. Keywords of 3 characters or fewer must match a whole word
  (`ct` does not match `connectivity`). Longer keywords match as substrings,
  so stems such as `cryptograph` still hit.
- **1** — the primary topic matches, or a keyword is in the title, but not both.
- **0** — a search hit that fails both tests. When the first page was entirely
  on-topic, the 0s are papers OpenAlex returned for a different field, checked
  with the same rule. Each borrowed paper is used for at most three queries.

`eval/score_search.py` indexes works and calls `ml.service.MLService.search`.
It reports **nDCG@10**, **Recall@20**, and **MRR**. nDCG uses gain `2^g - 1`.
Recall and MRR treat relevance above 0 as relevant. Relative paths go through
`ml.paths`, so the score does not depend on the working directory.

```bash
python eval/score_search.py --works data/works_v2.jsonl
python eval/score_search.py --fetch     # pull the judged works from OpenAlex
```

`--fetch` is the only network path. It requests the judged work ids 50 at a
time. The first page is anonymous. Pages after that need the free
`OPENALEX_API_KEY` (repo secret, already set). The pytest
(`ml/tests/test_score_search.py`) uses a tiny in-memory fixture and does not
call OpenAlex.

## Pattern check — `pattern_stability.py`

Compares `ml.incremental.IncrementalMiner` in batches with one full rebuild,
then compares incremental topic assignment (centroids updated as papers
arrive) with a full rebuild (centroids from every labelled paper). It prints
pattern Jaccard and support error, plus topic drift (`1 - mean Jaccard` of
the assigned topic sets) and topic splits (one full-rebuild topic whose
papers received two or more incremental labels).

```bash
python eval/pattern_stability.py
python eval/pattern_stability.py --works data/works_v2.jsonl
```

Test: `ml/tests/test_pattern_stability.py` (offline).
