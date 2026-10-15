"""Tiny dependency-free NLP helpers for extractive summaries and grounded QA."""
from __future__ import annotations

import math
import re
from collections import Counter

STOP = set("""a an the and or of to in on for with by from at as is are was were be been being this
that these those it its we our they their which who whom what when where how than then also
not no but into over under such can may might will would should could has have had do does did
using use used based via between among more most less both each other there here i you he she
""".split())

_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT.split(text or "") if len(s.strip()) > 3]


def tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if t not in STOP and len(t) > 1]


def extractive_summary(title: str, abstract: str, n: int = 3) -> str:
    """Score sentences by term frequency (title words boosted), keep top-n in order."""
    sents = sentences(abstract)
    if not sents:
        return title or ""
    if len(sents) <= n:
        return " ".join(sents)
    tf = Counter(tokens(abstract))
    for t in tokens(title):
        tf[t] += 3
    def score(i_s):
        i, s = i_s
        toks = tokens(s)
        if not toks:
            return 0.0
        base = sum(tf[t] for t in toks) / math.sqrt(len(toks))
        return base * (1.15 if i == 0 else 1.0)
    best = sorted(sorted(enumerate(sents), key=score, reverse=True)[:n])
    return " ".join(s for _, s in best)


def best_sentences(question: str, text: str, n: int = 2) -> list[tuple[str, float]]:
    """BM25-lite overlap between the question and each sentence."""
    sents = sentences(text)
    q = set(tokens(question))
    if not sents or not q:
        return []
    df = Counter(t for s in sents for t in set(tokens(s)))
    N = len(sents)
    scored = []
    for s in sents:
        st = tokens(s)
        if not st:
            continue
        sc = sum(math.log(1 + N / df[t]) for t in q if t in st) / math.sqrt(len(st))
        scored.append((s, sc))
    scored.sort(key=lambda x: -x[1])
    return [x for x in scored[:n] if x[1] > 0]
