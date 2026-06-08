"""Rate-limit failover across the model pool AND the API-key pool.

`FailoverLlm` wraps both pools as a single ADK model. On each request it tries
(model × api_key) candidates in order; if one returns a rate-limit / quota error
(HTTP 429 / RESOURCE_EXHAUSTED) BEFORE producing output, it transparently moves
on. Order: for each model, try each key first — so a rate-limited request first
switches to the NEXT API KEY, and only switches model once all keys are spent.

Because it's a normal ADK `BaseLlm`, this works everywhere — the scripted demo,
`adk web`, and `adk run`. Combined with the round-robin starting order
(config.next_model_order / next_key_order), the pools are load-spread under
normal conditions and self-healing under limits.
"""
import logging
from functools import cached_property

from google.adk.models.base_llm import BaseLlm
from google.adk.models.google_llm import Gemini
from google.genai import Client, types

from .config import next_model_order, next_key_order

logger = logging.getLogger("pace.failover")

# Pin the Gemini Developer API version that the model ids resolve on (matches the
# bare client used by list_models.py, which lists/uses these models fine).
_HTTP = lambda: types.HttpOptions(api_version="v1beta")


class _KeyedGemini(Gemini):
    """A Gemini bound to a specific API key (empty -> use environment default)."""

    api_key: str = ""

    @cached_property
    def api_client(self) -> Client:
        if self.api_key:
            return Client(api_key=self.api_key, http_options=_HTTP())
        return Client(http_options=_HTTP())


# Cache of underlying clients, keyed by (model, api_key).
_CLIENTS: dict[tuple[str, str], _KeyedGemini] = {}


def _client(model_name: str, api_key: str) -> _KeyedGemini:
    k = (model_name, api_key)
    if k not in _CLIENTS:
        _CLIENTS[k] = _KeyedGemini(model=model_name, api_key=api_key)
    return _CLIENTS[k]


def _mask(key: str) -> str:
    if not key:
        return "env-default"
    return f"...{key[-4:]}"


def _should_failover(err: Exception) -> bool:
    """True if we should try the next model/key.

    Covers rate limits/quota (429 / RESOURCE_EXHAUSTED) AND availability errors
    (404 not-found / model not supported), so a wrong or unavailable model id in
    the pool is skipped instead of crashing the run.
    """
    s = f"{type(err).__name__} {err}".lower()
    needles = [
        # rate limits / quota
        "429", "resource_exhausted", "resourceexhausted", "quota",
        "rate limit", "ratelimit", "too many requests",
        # availability / wrong id
        "404", "not_found", "not found", "not supported", "is not supported",
        # transient server-side
        "500", "503", "unavailable", "overloaded",
    ]
    return any(n in s for n in needles)


class FailoverLlm(BaseLlm):
    """An ADK model that fails over across models and API keys on rate limits."""

    models: list[str] = []
    api_keys: list[str] = [""]

    def __init__(self, **data):
        models = data.get("models") or []
        data.setdefault("model", models[0] if models else "failover")
        super().__init__(**data)

    async def generate_content_async(self, llm_request, stream: bool = False):
        last_err: Exception | None = None
        for model_name in self.models:
            for key in self.api_keys:
                produced = False
                try:
                    async for resp in _client(model_name, key).generate_content_async(
                        llm_request, stream=stream
                    ):
                        produced = True
                        yield resp
                    return  # finished cleanly
                except Exception as err:  # noqa: BLE001
                    # Fail over only for rate limits, and only if nothing was
                    # emitted yet (mid-stream retry would duplicate output).
                    if _should_failover(err) and not produced:
                        last_err = err
                        logger.warning(
                            "[failover] model=%s key=%s failed -> next | %s",
                            model_name,
                            _mask(key),
                            str(err),
                        )
                        continue
                    raise
        if last_err is not None:
            logger.error("[failover] all models x keys failed")
            raise last_err


def make_model() -> FailoverLlm:
    """Build a FailoverLlm whose primary model+key are next in the rotation."""
    return FailoverLlm(models=next_model_order(), api_keys=next_key_order())
