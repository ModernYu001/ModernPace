"""Standalone MCP server exposing Pace's question bank.

This satisfies the challenge's Model Context Protocol (MCP) requirement: the same
tools the agents use locally are also served over MCP, so the agent system can
reach curriculum/question data through a standard, swappable protocol.

Run directly (stdio transport):
    python -m pace_agent.mcp_server

Wire it into an agent with ADK's MCPToolset (see README "Turn on MCP"):
    from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
    from mcp import StdioServerParameters
    toolset = MCPToolset(connection_params=StdioServerParameters(
        command="python", args=["-m", "pace_agent.mcp_server"]))
    # then pass tools=[toolset] to an LlmAgent
"""
from mcp.server.fastmcp import FastMCP

from .question_bank import (
    get_quiz,
    get_concept_note,
    get_practice_problem,
    list_topics,
)
from . import engine

mcp = FastMCP("pace-tutor")


@mcp.tool()
def topics() -> dict:
    """List the math topics Pace can teach right now (grades 4-12)."""
    return list_topics()


@mcp.tool()
def route(text: str) -> dict:
    """Map a free-text request (any language, e.g. '我想学分数') to a topic id.

    Returns {topic: id or null}. null means no available topic matches by rule
    (the caller may then fall back to an LLM router).
    """
    return {"topic": engine.rule_match(text)}


@mcp.tool()
def diagnose(topic: str, answers: dict) -> dict:
    """Deterministically diagnose a student from quiz answers.

    Args:
        topic: topic id.
        answers: mapping of question id -> the student's raw answer (e.g. {"q1":"2"}).
    Returns a structured diagnosis (score, gap concept, mastery %, strengths) plus
    a rendered summary card.
    """
    d = engine.diagnose(topic, answers)
    d["card"] = engine.render_diagnosis(d)
    return d


@mcp.tool()
def grade(topic: str, student_answer: str) -> dict:
    """Deterministically grade a student's answer to the topic's practice problem.

    Returns {ok, problem, answer, feedback} — checked against the answer key, so
    no model is involved and the verdict cannot hallucinate.
    """
    g = engine.grade_practice(topic, student_answer)
    g["feedback"] = engine.render_grading(topic, g, student_answer)
    return g


@mcp.tool()
def plan(topic: str, answers: dict) -> dict:
    """Build a short study plan from a diagnosis (deterministic, no model)."""
    d = engine.diagnose(topic, answers)
    return {"plan": engine.build_plan(d)}


@mcp.tool()
def quiz(topic: str) -> dict:
    """Return the diagnostic quiz for a topic (e.g. 'quadratic_discriminant')."""
    return get_quiz(topic)


@mcp.tool()
def concept_note(topic: str, concept: str) -> dict:
    """Return a short teaching note for one concept within a topic."""
    return get_concept_note(topic, concept)


@mcp.tool()
def practice_problem(topic: str) -> dict:
    """Return one practice problem (with model answer) for a topic."""
    return get_practice_problem(topic)


if __name__ == "__main__":
    mcp.run()
