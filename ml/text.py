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

# ASCII sentence boundary, plus accented capitals (É…) and CJK full stops.
# Common abbreviations keep their period so "Fig. 1" and "Dr. Smith" stay one sentence.
_ABBREV = re.compile(
    r"\b(?:Fig|Figs|Dr|Mr|Mrs|Ms|Prof|Eq|vs|etc|al)\.|\b(?:e\.g|i\.e)\.",
    re.IGNORECASE,
)
_SENT = re.compile(
    r"(?<=[.!?])\s+(?=[0-9A-Z\u00C0-\u00D6\u00D8-\u00DE])|(?<=[。！？])"
)
# Scripts that are often written without spaces. Overlap is measured on bigrams.
_UNSEGMENTED = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]+")
# A paper can tell a model to ignore its instructions. That sentence is not a summary.
_OVERRIDE = re.compile(
    r"\b(?:ignore|disregard|forget)\b.{0,80}\b(?:instruction|instructions|prompt|prompts)\b"
    r"|\byou are now\b|\bnew instructions\b",
    re.IGNORECASE | re.DOTALL,
)


def sentences(text: str) -> list[str]:
    raw = _ABBREV.sub(lambda m: m.group(0)[:-1] + "\u0001", text or "")
    out = []
    for part in _SENT.split(raw):
        s = part.replace("\u0001", ".").strip()
        if len(s) > 3:
            out.append(s)
    return out


def tokens(text: str) -> list[str]:
    """Word tokens, keeping accented letters, plus bigrams for unsegmented scripts."""
    raw = text or ""
    out = []
    for t in re.findall(r"[^\W_]+", raw.lower()):
        if _UNSEGMENTED.fullmatch(t):
            continue
        if t not in STOP and len(t) > 1:
            out.append(t)
    for run in _UNSEGMENTED.findall(raw):
        if len(run) < 2:
            continue
        out.extend(run[i:i + 2] for i in range(len(run) - 1))
    return out


def _summary_sentences(abstract: str) -> list[str]:
    sents = sentences(abstract)
    kept = [s for s in sents if not _OVERRIDE.search(s)]
    return kept or sents


def extractive_summary(title: str, abstract: str, n: int = 3) -> str:
    """Score sentences by term frequency (title words boosted), keep top-n in order.

    Returns "" when the abstract has no usable sentence. Callers decide what to
    show instead of echoing the title.
    """
    sents = _summary_sentences(abstract)
    if not sents:
        return ""
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


def grounded_in_abstract(text: str, abstract: str) -> bool:
    """True when `text` shares a content word with the abstract itself.

    Instruction-override sentences are not evidence. A model answer that only
    repeats them, or shares nothing with the abstract, is discarded.
    """
    if not text or _OVERRIDE.search(text):
        return False
    body = [s for s in sentences(abstract) if not _OVERRIDE.search(s)]
    have = set(tokens(" ".join(body) if body else abstract))
    got = set(tokens(text))
    return bool(have and got and have & got)


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
