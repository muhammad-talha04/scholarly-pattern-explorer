"""The sampling design, in one place.

Design: a stratified random sample of OpenAlex computer-science articles, one stratum
per publication month, with the same number of papers in every month (PER_MONTH).

* Within a year, equal allocation gives every month the same precision, so monthly
  charts are equally reliable. OpenAlex output differs by month, so each paper carries
  a design weight w = N_month / n_month (OpenAlex total / papers sampled that month).
  Weighted shares and totals are estimates for all of OpenAlex CS, not for the sample.
* Between years, every year has about 12 x PER_MONTH papers; the weights scale each year
  to its own OpenAlex size, so years compare fairly even though output grows ~2x.
* Papers that were not drawn by this design (out_of_sample_ids) stay searchable but get
  weight 0: they never enter a chart, country table, pattern or trend.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from statistics import median

from .paths import DEPLOY_DATA

PER_MONTH = 678


@lru_cache(maxsize=1)
def out_of_sample_ids() -> frozenset[str]:
    """Work ids (``W123``) outside the random sample. File: deploy/data/out_of_sample_ids.txt."""
    path = Path(os.getenv("OUT_OF_SAMPLE_IDS") or DEPLOY_DATA / "out_of_sample_ids.txt")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return frozenset()
    return frozenset(ln.strip().rsplit("/", 1)[-1] for ln in lines if ln.strip() and not ln.startswith("#"))


def in_sample(work_id: str) -> bool:
    return str(work_id).rsplit("/", 1)[-1] not in out_of_sample_ids()


def month_weights(sampled: dict[str, int], population: dict[str, int]) -> dict[str, float]:
    """Design weight per month 'YYYY-MM': OpenAlex total / sampled papers.

    A month with papers but no recorded OpenAlex total gets the median weight of its
    year (or of all months), so it is neither dropped nor counted as 1.
    """
    w = {m: population[m] / n for m, n in sampled.items() if n > 0 and population.get(m)}
    by_year: dict[str, list[float]] = {}
    for m, v in w.items():
        by_year.setdefault(m[:4], []).append(v)
    overall = median(w.values()) if w else 1.0
    for m, n in sampled.items():
        if n > 0 and m not in w:
            w[m] = median(by_year[m[:4]]) if m[:4] in by_year else overall
    return w


if __name__ == "__main__":   # self-check
    w = month_weights({"2020-01": 100, "2020-02": 50, "2020-03": 10}, {"2020-01": 1000, "2020-02": 1000})
    assert w == {"2020-01": 10.0, "2020-02": 20.0, "2020-03": 15.0}, w
    print(len(out_of_sample_ids()), "out-of-sample ids; weights ok")
