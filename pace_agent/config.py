"""Central config. Override via env vars (loaded from .env if present)."""
import itertools
import os
import threading

# Load a local .env automatically so keys/settings live in one file — no need to
# `export` them. (ADK's `adk web`/`adk run` also auto-load .env; this makes the
# plain `python -m pace_agent.demo` path behave the same.)
try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv()                            # walk up from this file (pace/.env)
    load_dotenv(find_dotenv(usecwd=True))    # and from the current working dir
except ImportError:
    pass

# ── Model pool + rotation ────────────────────────────────────────────────────
# Models are rotated round-robin across agents/calls to spread load and dodge
# per-model rate limits. Override the pool with PACE_MODELS (comma-separated).
#
# ⚠️ Use the EXACT model id strings your backend accepts. Confirm availability
# with `python list_models.py`. FailoverLlm transparently skips any id that the
# backend rejects (404 / not supported), so an extra entry is safe.
_DEFAULT_MODELS = "gemini-2.5-flash,gemini-3-flash-preview,gemini-3.1-flash-lite,gemini-2.5-flash-lite"
MODELS = [m.strip() for m in os.getenv("PACE_MODELS", _DEFAULT_MODELS).split(",") if m.strip()]

# Back-compat single model (also used as fallback if the pool is empty).
MODEL = os.getenv("PACE_MODEL", MODELS[0] if MODELS else "gemini-2.5-flash")

# ── API key pool ─────────────────────────────────────────────────────────────
# Multiple keys are rotated round-robin and used for failover on rate limits.
# Set PACE_API_KEYS (comma-separated); falls back to GOOGLE_API_KEY; "" means
# "let the client read the environment / default credentials".
_keys_env = os.getenv("PACE_API_KEYS", "")
API_KEYS = [k.strip() for k in _keys_env.split(",") if k.strip()] or [
    os.getenv("GOOGLE_API_KEY", "")
]

_POOL = MODELS or [MODEL]
_cycle = itertools.cycle(_POOL)
_lock = threading.Lock()
_start = 0
_key_start = 0


def next_model() -> str:
    """Return the next single model in the rotation (thread-safe round-robin)."""
    with _lock:
        return next(_cycle)


def next_model_order() -> list[str]:
    """Return the full pool rotated so a different model leads each call.

    The first element is the round-robin "primary"; the rest are the failover
    order. e.g. pool [A,B,C] yields [A,B,C], then [B,C,A], then [C,A,B]...
    """
    global _start
    with _lock:
        n = len(_POOL)
        order = _POOL[_start:] + _POOL[:_start]
        _start = (_start + 1) % n
        return order


def next_key_order() -> list[str]:
    """Return the API-key pool rotated so a different key leads each call.

    The first element is the round-robin "primary" key; the rest are the
    failover order used when a key is rate-limited.
    """
    global _key_start
    with _lock:
        n = len(API_KEYS)
        order = API_KEYS[_key_start:] + API_KEYS[:_key_start]
        _key_start = (_key_start + 1) % n
        return order


# ── Language ─────────────────────────────────────────────────────────────────
# Interaction language: zh (default) / en / ja. Agents reply in this language
# regardless of the language the question bank is authored in.
PACE_LANG = os.getenv("PACE_LANG", "zh")
LANG_NAMES = {"zh": "Chinese", "en": "English", "ja": "Japanese"}


def lang_directive(lang: str | None = None) -> str:
    """A sentence appended to every agent instruction to fix the reply language.

    Pass an explicit `lang` (zh/en/ja) to override the configured default — this
    lets the web UI switch language per request without redeploying.
    """
    name = LANG_NAMES.get(lang or PACE_LANG, "Chinese")
    return f"\n\nAlways reply to the student in {name}, in a natural, native tone."


APP_NAME = "pace"
DEFAULT_TOPIC = os.getenv("PACE_TOPIC", "quadratic_discriminant")
