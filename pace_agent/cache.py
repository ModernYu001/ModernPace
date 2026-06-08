"""Tiny disk-backed cache + run metrics.

- cache: memoizes deterministic-ish LLM calls (router fallback, optional polish)
  across runs, keyed by a hash of (tag, prompt). Tutoring is never cached.
- metrics: counts LLM calls vs. rule/deterministic/cache hits, so we can show
  how much the hybrid design saves.
"""
import hashlib
import json
import os
import threading

_CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", ".pace_cache.json")
_lock = threading.Lock()


class Metrics:
    llm_calls = 0       # actual model invocations
    cache_hits = 0      # served from cache (no model call)
    rule_hits = 0       # routing solved by local rules
    deterministic = 0   # steps done in pure code (no model)

    @classmethod
    def reset(cls):
        cls.llm_calls = cls.cache_hits = cls.rule_hits = cls.deterministic = 0

    @classmethod
    def summary(cls) -> str:
        saved = cls.deterministic + cls.rule_hits + cls.cache_hits
        return (f"LLM calls: {cls.llm_calls}  |  saved by hybrid: {saved} "
                f"(deterministic {cls.deterministic}, rules {cls.rule_hits}, "
                f"cache {cls.cache_hits})")


def _load() -> dict:
    try:
        with open(os.path.abspath(_CACHE_FILE), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(d: dict) -> None:
    try:
        with open(os.path.abspath(_CACHE_FILE), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
    except Exception:
        pass


def _key(tag: str, prompt: str) -> str:
    return hashlib.sha256(f"{tag}\x00{prompt}".encode("utf-8")).hexdigest()


def cache_get(tag: str, prompt: str):
    with _lock:
        return _load().get(_key(tag, prompt))


def cache_put(tag: str, prompt: str, value: str) -> None:
    with _lock:
        d = _load()
        d[_key(tag, prompt)] = value
        _save(d)
