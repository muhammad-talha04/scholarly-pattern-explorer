"""OpenAlex topics whose field is Computer Science (core subfields kept; education, library and media topics under Information Systems dropped).

OpenAlex files some papers under Computer Science whose topics belong to other fields
(Black Holes, Education Leadership). Gaps and emerging topics keep only the CS ones.
Regenerate ml/data/cs_topics.json from api.openalex.org/topics (field.display_name).
"""
import json
from functools import lru_cache
from pathlib import Path


# OpenAlex files these under Computer Science, but they are not computer science
# (or are catch-all buckets). Hand-picked from the topic list; extend as needed.
NOT_CS = frozenset({
    "Bioethics and Human Rights Issues", "Chaos, Complexity, and Education",
    "Chemical and Environmental Engineering Research", "Cognitive Science and Mapping",
    "Contact Mechanics and Variational Inequalities", "Cultural Insights and Digital Impacts",
    "Digital Communication and Language", "Digital Media and Visual Art",
    "Diverse Interdisciplinary Research Studies", "Diverse Research and Applications",
    "Economic Growth and Development", "Educational Research and Pedagogy",
    "Educational Technology and Pedagogy", "Environmental Engineering and Cultural Studies",
    "Geochemistry and Geologic Mapping", "Healthcare during COVID-19 Pandemic",
    "Law, AI, and Intellectual Property", "Linguistic Studies and Language Acquisition",
    "Music Technology and Sound Studies", "Nonlinear Dynamics and Pattern Formation",
    "Optical measurement and interference techniques", "Organizational and Employee Performance",
    "Psychiatry, Mental Health, Neuroscience", "Scientific Research and Technology",
    "Seismology and Earthquake Studies", "Solar Radiation and Photovoltaics",
    "Thoreau and American Literature", "Transportation Systems and Safety",
})


@lru_cache(maxsize=1)
def cs_topics() -> frozenset[str]:
    f = Path(__file__).with_name("data") / "cs_topics.json"
    return frozenset(json.loads(f.read_text(encoding="utf-8"))) - NOT_CS if f.exists() else frozenset()


def is_cs(name: str) -> bool:
    """True when the topic is a Computer Science topic, or when no list is installed."""
    topics = cs_topics()
    return not topics or name in topics
