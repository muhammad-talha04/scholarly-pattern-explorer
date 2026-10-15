"""Paper record helpers (OpenAlex work -> flat dict)."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .paths import REPO_ROOT, resolve

# Fixture DOIs such as 10.1234/spe.0 are not registered and 404 at doi.org.
_PLACEHOLDER_DOI = re.compile(r"10\.1234(?:/|$)", re.IGNORECASE)


def abstract_from_inverted_index(inv: dict | None) -> str:
    """OpenAlex ships abstracts as {word: [positions]}; rebuild the text."""
    if not inv:
        return ""
    pos = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))


def short_id(work_id: str) -> str:
    return work_id.rsplit("/", 1)[-1] if work_id else work_id


def is_placeholder_doi(value: str | None) -> bool:
    return bool(value and _PLACEHOLDER_DOI.search(value))


def reader_url(doi: str | None, original_url: str | None, openalex_url: str | None) -> str | None:
    """DOI page when the DOI is real. Otherwise the PDF, landing page, or OpenAlex work."""
    if doi and not is_placeholder_doi(doi):
        url = doi if doi.startswith("http") else f"https://doi.org/{doi}"
        if not is_placeholder_doi(url):
            return url
    for candidate in (original_url, openalex_url):
        if candidate and not is_placeholder_doi(candidate):
            return candidate
    return None


@dataclass
class Paper:
    work_id: str
    title: str = ""
    abstract: str = ""
    pub_year: int | None = None
    doi: str | None = None
    topics: list[str] = field(default_factory=list)
    created: str | None = None   # ISO date the paper entered our corpus
    authors: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    cited_by: int = 0
    original_url: str | None = None

    @property
    def text(self) -> str:
        return f"{self.title}. {self.abstract}".strip(". ").strip()

    @property
    def best_original_url(self) -> str | None:
        return self.original_url or self.doi_url

    @property
    def openalex_url(self) -> str:
        return f"https://openalex.org/{short_id(self.work_id)}"

    @property
    def doi_url(self) -> str | None:
        if not self.doi or is_placeholder_doi(self.doi):
            return None
        d = self.doi
        url = d if d.startswith("http") else f"https://doi.org/{d}"
        return None if is_placeholder_doi(url) else url

    @classmethod
    def from_openalex(cls, w: dict) -> "Paper":
        topics = [t.get("display_name") for t in (w.get("topics") or []) if t.get("display_name")]
        return cls(
            work_id=short_id(w.get("id", "")),
            title=w.get("title") or w.get("display_name") or "",
            abstract=w.get("abstract") or abstract_from_inverted_index(w.get("abstract_inverted_index")),
            pub_year=w.get("publication_year"),
            doi=w.get("doi"),
            topics=topics,
            created=w.get("created_date"),
            authors=[(a.get("author") or {}).get("display_name") for a in w.get("authorships") or []
                     if (a.get("author") or {}).get("display_name")],
            countries=sorted({c for a in w.get("authorships") or [] for c in a.get("countries") or [] if c}),
            cited_by=w.get("cited_by_count") or 0,
            original_url=((w.get("open_access") or {}).get("oa_url")
                          or (w.get("primary_location") or {}).get("landing_page_url")),
        )

    @classmethod
    def from_v2(cls, r: dict) -> "Paper":
        """A row of data/works_v2.jsonl written by pipeline/ingest.py."""
        return cls(
            work_id=short_id(r["id"]), title=r.get("title") or "", abstract=r.get("abstract") or "",
            pub_year=r.get("year"), doi=r.get("doi"), topics=[t for t in r.get("topics") or [] if t],
            created=r.get("date"), authors=[a for a in r.get("authors") or [] if a],
            countries=r.get("countries") or [], cited_by=r.get("cited_by") or 0,
            original_url=r.get("original_url"))

    @classmethod
    def from_record(cls, r: dict) -> "Paper":
        """Accept either a v2 row or a raw OpenAlex work (old data/works.jsonl)."""
        if "abstract_inverted_index" in r or "publication_year" in r:
            return cls.from_openalex(r)
        return cls.from_v2(r)

    def to_dict(self) -> dict:
        return {"work_id": self.work_id, "title": self.title, "abstract": self.abstract,
                "pub_year": self.pub_year, "doi": self.doi, "topics": self.topics,
                "created": self.created, "authors": self.authors, "countries": self.countries,
                "cited_by": self.cited_by, "original_url": self.original_url}


V2_PATH = "data/works_v2.jsonl"
LEGACY_PATHS = ("data/works.jsonl", "data/works_sample.jsonl")


def default_works_path(root: str | Path | None = None) -> Path | None:
    """ML_WORKS_PATH, else data/works_v2.jsonl, else the old JSONL files."""
    env = os.getenv("ML_WORKS_PATH")
    if env:
        return resolve(env)
    root = REPO_ROOT if root is None else Path(root)
    for rel in (V2_PATH, *LEGACY_PATHS):
        p = root / rel
        if p.exists():
            return p
    return None


def read_works(path: str | Path | None = None):
    path = Path(path) if path else default_works_path()
    if path is None:
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield Paper.from_record(json.loads(line))
