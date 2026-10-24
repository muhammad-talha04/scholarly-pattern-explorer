"""OpenAlex topics whose field is Computer Science (core subfields kept; education, library and media topics under Information Systems dropped).

OpenAlex files some papers under Computer Science whose topics belong to other fields
(Black Holes, Education Leadership). Gaps and emerging topics keep only the CS ones.
Regenerate ml/data/cs_topics.json from api.openalex.org/topics (field.display_name).
"""
import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def cs_topics() -> frozenset[str]:
    f = Path(__file__).with_name("data") / "cs_topics.json"
    return frozenset(json.loads(f.read_text(encoding="utf-8"))) if f.exists() else frozenset()


def is_cs(name: str) -> bool:
    """True when the topic is a Computer Science topic, or when no list is installed."""
    topics = cs_topics()
    return not topics or name in topics
