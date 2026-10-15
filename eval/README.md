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
