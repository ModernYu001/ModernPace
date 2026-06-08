"""Question-bank tools (used by agents as ADK FunctionTools).

These thin wrappers read through the curriculum loader, so the agents stay
decoupled from how/where the data is stored. The SAME functions are exposed over
MCP in mcp_server.py to satisfy the challenge's MCP requirement.
"""
from .config import DEFAULT_TOPIC
from .curriculum import load_topic, all_ready_topics, topic_exists


def _resolve(topic: str) -> dict:
    if not topic or not topic_exists(topic):
        topic = DEFAULT_TOPIC
    return load_topic(topic)


def list_topics() -> dict:
    """List the math topics Pace can teach right now (grades 4-12).

    Returns:
        A dict with a list of {id, label, grade} for every ready topic.
    """
    return {"topics": all_ready_topics()}


def get_quiz(topic: str) -> dict:
    """Return the diagnostic quiz for a topic.

    Args:
        topic: topic id, e.g. "quadratic_discriminant" or "fraction_add_sub".

    Returns:
        A dict with the topic label, grade level, and the list of questions
        (prompt, choices, answer, concept).
    """
    t = _resolve(topic)
    return {
        "topic": topic,
        "topic_label": t["topic_label"],
        "grade_level": t["grade_level"],
        "questions": t["questions"],
    }


def get_concept_note(topic: str, concept: str) -> dict:
    """Return a short teaching note for one concept within a topic.

    Args:
        topic: topic id.
        concept: concept key, e.g. "discriminant_zero".

    Returns:
        A dict with the concept key and its explanation.
    """
    t = _resolve(topic)
    note = t["concepts"].get(concept, "No note found for that concept.")
    return {"concept": concept, "note": note}


def get_practice_problem(topic: str) -> dict:
    """Return one practice problem (with model answer) for a topic.

    Args:
        topic: topic id.

    Returns:
        A dict with the practice problem prompt, the model answer, and concept.
    """
    t = _resolve(topic)
    return t["practice"][0]
