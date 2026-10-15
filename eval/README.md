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

`--fetch` is the only network path. The pytest
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
