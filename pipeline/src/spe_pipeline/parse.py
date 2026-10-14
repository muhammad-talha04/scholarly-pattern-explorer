"""Pure functions turning one OpenAlex work record into normalised rows.

No I/O here so it is trivially testable. Topic *IDs* (e.g. ``T10320``) are the
keys everywhere; display names are attributes only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def short_id(url: str | None) -> str | None:
    """'https://openalex.org/W123' -> 'W123'."""
    return url.rstrip("/").rsplit("/", 1)[-1] if url else None


def reconstruct_abstract(inv: dict[str, list[int]] | None) -> str | None:
    """OpenAlex ships abstracts as an inverted index {word: [positions]}."""
    if not inv:
        return None
    pos: dict[int, str] = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos)) or None


@dataclass
class ParsedWork:
    work: dict[str, Any]
    topics: list[dict[str, Any]] = field(default_factory=list)
    work_topics: list[dict[str, Any]] = field(default_factory=list)
    authors: list[dict[str, Any]] = field(default_factory=list)
    work_authors: list[dict[str, Any]] = field(default_factory=list)
    countries: set[str] = field(default_factory=set)


def parse_work(rec: dict[str, Any]) -> ParsedWork | None:
    wid = short_id(rec.get("id"))
    year = rec.get("publication_year")
    if not wid or year is None:
        return None
    auths = rec.get("authorships") or []
    oa = rec.get("open_access") or {}
    best = rec.get("best_oa_location") or {}
    out = ParsedWork(work={
        "work_id": wid,
        "title": (rec.get("display_name") or rec.get("title") or "")[:1000],
        "abstract": reconstruct_abstract(rec.get("abstract_inverted_index")),
        "pub_year": int(year),
        "pub_date": rec.get("publication_date"),
        "cited_by": rec.get("cited_by_count") or 0,
        "n_authors": len(auths),
        "doi": rec.get("doi"),
        "openalex_url": rec.get("id"),
        "oa_url": best.get("pdf_url") or oa.get("oa_url"),
        "updated_date": rec.get("updated_date"),
    })
    seen_topics: set[str] = set()
    for t in rec.get("topics") or []:
        tid = short_id(t.get("id"))
        if not tid or tid in seen_topics:
            continue
        seen_topics.add(tid)
        out.topics.append({
            "topic_id": tid,
            "display_name": t.get("display_name"),
            "subfield": (t.get("subfield") or {}).get("display_name"),
            "field": (t.get("field") or {}).get("display_name"),
            "domain": (t.get("domain") or {}).get("display_name"),
        })
        out.work_topics.append({"work_id": wid, "topic_id": tid, "score": t.get("score") or 0.0})
    seen_auth: set[str] = set()
    for pos, a in enumerate(auths):
        info = a.get("author") or {}
        aid = short_id(info.get("id"))
        insts = a.get("institutions") or []
        codes = set(a.get("countries") or [])
        codes.update(i.get("country_code") for i in insts)
        out.countries.update(c.upper() for c in codes if c)
        if not aid or aid in seen_auth:
            continue
        seen_auth.add(aid)
        first = insts[0] if insts else {}
        out.authors.append({
            "author_id": aid,
            "display_name": info.get("display_name"),
            "institution": first.get("display_name"),
            "country": (first.get("country_code") or "").upper() or None,
        })
        out.work_authors.append({"work_id": wid, "author_id": aid, "author_pos": pos})
    return out
