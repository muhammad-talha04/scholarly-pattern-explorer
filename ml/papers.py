"""Paper record helpers (OpenAlex work -> flat dict)."""
from __future__ import annotations

from dataclasses import dataclass, field


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


@dataclass
class Paper:
    work_id: str
    title: str = ""
    abstract: str = ""
    pub_year: int | None = None
    doi: str | None = None
    topics: list[str] = field(default_factory=list)
    created: str | None = None   # ISO date the paper entered our corpus

    @property
    def text(self) -> str:
        return f"{self.title}. {self.abstract}".strip(". ").strip()

    @property
    def openalex_url(self) -> str:
        return f"https://openalex.org/{short_id(self.work_id)}"

    @property
    def doi_url(self) -> str | None:
        if not self.doi:
            return None
        d = self.doi
        return d if d.startswith("http") else f"https://doi.org/{d}"

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
        )

    def to_dict(self) -> dict:
        return {"work_id": self.work_id, "title": self.title, "abstract": self.abstract,
                "pub_year": self.pub_year, "doi": self.doi, "topics": self.topics,
                "created": self.created}
