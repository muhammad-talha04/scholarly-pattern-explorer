"""
STEP 1 (offline): make fake-but-realistic data so you can build the whole
project before you ever touch the internet.

Why this matters: if you start by fighting an API, you will spend three days on
HTTP errors and zero days on data mining. Build the pipeline on fake data first,
prove it works, THEN swap in the real OpenAlex download. Same file format, so
nothing downstream changes.

The fake data deliberately contains a story your miner should rediscover:
  - "Expert Systems + Fuzzy Logic" is common early, then dies out
  - "Deep Learning + Computer Vision" explodes after 2012
  - "Large Language Models + Transformers" only exists from 2019
If your sliding-window miner does not find those three, something is broken.

Run:  python make_sample_data.py
Out:  data/works_sample.jsonl
"""
from __future__ import annotations

import json
import random
from pathlib import Path

random.seed(42)

# (topics that travel together, first year alive, last year alive, base weight)
CLUSTERS = [
    (["Expert Systems", "Fuzzy Logic", "Knowledge Representation"], 2000, 2014, 1.0),
    (["Deep Learning", "Computer Vision", "Image Classification"], 2012, 2026, 2.2),
    (["Large Language Models", "Transformers", "Natural Language Processing"], 2019, 2026, 2.6),
    (["Frequent Pattern Mining", "Association Rules", "Data Streams"], 2000, 2026, 0.9),
    (["Visual Analytics", "Information Visualization", "Human-Computer Interaction"], 2004, 2026, 1.1),
    (["Social Network Analysis", "Graph Mining", "Community Detection"], 2006, 2026, 1.3),
    (["Bioinformatics", "Genomics", "Protein Structure"], 2000, 2026, 1.2),
    (["Cloud Computing", "Distributed Systems", "MapReduce"], 2008, 2020, 1.0),
]
FIELDS = {
    "Expert Systems": "Computer Science", "Fuzzy Logic": "Mathematics",
    "Knowledge Representation": "Computer Science", "Deep Learning": "Computer Science",
    "Computer Vision": "Computer Science", "Image Classification": "Computer Science",
    "Large Language Models": "Computer Science", "Transformers": "Computer Science",
    "Natural Language Processing": "Computer Science", "Frequent Pattern Mining": "Computer Science",
    "Association Rules": "Computer Science", "Data Streams": "Computer Science",
    "Visual Analytics": "Computer Science", "Information Visualization": "Computer Science",
    "Human-Computer Interaction": "Computer Science", "Social Network Analysis": "Social Sciences",
    "Graph Mining": "Computer Science", "Community Detection": "Mathematics",
    "Bioinformatics": "Biology", "Genomics": "Biology", "Protein Structure": "Biology",
    "Cloud Computing": "Engineering", "Distributed Systems": "Computer Science",
    "MapReduce": "Computer Science",
}
INSTITUTIONS = [
    ("University of Manitoba", "CA"), ("University of Toronto", "CA"),
    ("Tsinghua University", "CN"), ("IIT Delhi", "IN"),
    ("GC University Faisalabad", "PK"), ("University of Tokyo", "JP"),
]

# 240 authors, each loyal to one cluster -> gives the co-authorship graph communities
AUTHORS = [
    {
        "id": f"https://openalex.org/A{5000 + i}",
        "display_name": f"Author {i:03d}",
        "cluster": i % len(CLUSTERS),
        "institution": INSTITUTIONS[i % len(INSTITUTIONS)],
    }
    for i in range(240)
]


def alive_clusters(year):
    return [c for c in CLUSTERS if c[1] <= year <= c[2]]

def make_work(idx, year):
    """Build one paper in the SAME JSON shape the real OpenAlex API returns."""
    live = alive_clusters(year)
    weights = [c[3] * (1.6 if c[1] > 2010 and year >= c[1] + 2 else 1.0) for c in live]
    cluster = random.choices(live, weights=weights, k=1)[0]
    ci = CLUSTERS.index(cluster)

    # most topics come from the paper's own cluster, occasionally one wanders in
    topics = random.sample(cluster[0], random.randint(2, len(cluster[0])))
    if random.random() < 0.18:
        other = random.choice(alive_clusters(year))
        topics.append(random.choice(other[0]))
    topics = list(dict.fromkeys(topics))

    own = [a for a in AUTHORS if a["cluster"] == ci]
    team = random.sample(own, min(len(own), random.randint(1, 4)))
    if random.random() < 0.25:                      # cross-community collaboration
        team.append(random.choice(AUTHORS))
    seen, unique_team = set(), []                   # never list an author twice
    for a in team:
        if a["id"] not in seen:
            seen.add(a["id"])
            unique_team.append(a)
    team = unique_team

    return {
        "id": f"https://openalex.org/W{idx}",
        "display_name": f"A study of {' and '.join(topics[:2])} ({year})",
        "publication_year": year,
        "cited_by_count": max(0, int(random.gauss(18, 22))),
        "topics": [
            {
                "id": f"https://openalex.org/T{abs(hash(t)) % 90000}",
                "display_name": t,
                "score": round(random.uniform(0.45, 0.99), 3),
                "field": {"display_name": FIELDS[t]},
                "domain": {"display_name": "Physical Sciences"},
            }
            for t in topics
        ],
        "authorships": [
            {
                "author_position": "first" if k == 0 else "middle",
                "author": {"id": a["id"], "display_name": a["display_name"]},
                "institutions": [
                    {"display_name": a["institution"][0], "country_code": a["institution"][1]}
                ],
            }
            for k, a in enumerate(team)
        ],
    }


def main(n_works=12000, first_year=2000, last_year=2026):
    out_dir = Path("data")
    out_dir.mkdir(exist_ok=True)
    path = out_dir / "works_sample.jsonl"

    # more papers published in later years, like the real world
    years = list(range(first_year, last_year + 1))
    year_weights = [1.0 + 0.12 * (y - first_year) for y in years]

    with path.open("w", encoding="utf-8") as fh:
        for i in range(n_works):
            year = random.choices(years, weights=year_weights, k=1)[0]
            fh.write(json.dumps(make_work(1000000 + i, year)) + "\n")

    print(f"wrote {n_works} fake works -> {path}")
    print("next:  python build_db.py --input data/works_sample.jsonl")


if __name__ == "__main__":
    main()

