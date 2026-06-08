"""Scalable curriculum data layer.

Design that keeps the architecture stable as content grows:
- `data/curriculum.json`  — the catalog: every grade (4-12) and its topics.
- `data/topics/<id>.json` — one file per topic, all with the SAME schema.

Agents/tools never read files directly; they go through this loader. To swap
JSON for a database or vector store later, only this module changes — the agents
don't notice. Adding a topic = drop in a new file + a catalog entry. No code.
"""
import json
import os
from functools import lru_cache

_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
_CATALOG = os.path.join(_DATA_DIR, "curriculum.json")
_TOPICS_DIR = os.path.join(_DATA_DIR, "topics")


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    with open(_CATALOG, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=128)
def load_topic(topic_id: str) -> dict:
    """Load one topic file. Raises FileNotFoundError if the topic isn't authored yet."""
    path = os.path.join(_TOPICS_DIR, f"{topic_id}.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def topic_exists(topic_id: str) -> bool:
    return os.path.exists(os.path.join(_TOPICS_DIR, f"{topic_id}.json"))


def all_ready_topics() -> list[dict]:
    """Flat list of topics that have authored questions (ready=true)."""
    out = []
    for grade_key, grade in load_catalog().items():
        for t in grade["topics"]:
            if t.get("ready") and topic_exists(t["id"]):
                out.append(
                    {
                        "id": t["id"],
                        "label": t["label"],
                        "grade": grade["label"],
                        "grade_key": grade_key,
                    }
                )
    return out
