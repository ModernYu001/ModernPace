"""Coordinator agent — the entry point ADK discovers as `root_agent`.

Run it with the built-in dev UI:   adk web
or in the terminal:                adk run pace_agent

The coordinator delegates to the five specialized sub-agents over ADK's
multi-agent transfer (the in-framework realization of Agent2Agent / A2A).
For a scripted, recording-friendly run of the full loop, use demo.py instead.
"""
from google.adk.agents import LlmAgent

from .failover import make_model
from .agents import (
    make_router,
    make_diagnostic,
    make_planner,
    make_tutor,
    make_grader,
    make_grade_verifier,
    make_reporter,
)

root_agent = LlmAgent(
    name="pace_coordinator",
    model=make_model(),
    description="Pace — a personal AI study coach that diagnoses, plans, tutors, grades, and reports.",
    instruction=(
        "You are Pace, a personal AI study coach for a middle-school student. "
        "The default topic is the quadratic discriminant.\n\n"
        "Run this flow by delegating to your specialist sub-agents in order:\n"
        "0. router_agent — if the student says what they want to learn, map it to a topic.\n"
        "1. diagnostic_agent — quiz the student and find the gap.\n"
        "2. planner_agent — build a short daily plan for that gap.\n"
        "3. tutor_agent — teach the gap Socratically (multi-turn).\n"
        "4. grader_agent — check a practice answer and explain.\n"
        "5. grade_verifier — double-check the grading against the correct answer.\n"
        "6. reporter_agent — write the parent's weekly progress report.\n\n"
        "Hand off to the right specialist for each step. Keep the student engaged "
        "and never reveal answers the tutor should be drawing out."
    ),
    sub_agents=[
        make_router(),
        make_diagnostic(),
        make_planner(),
        make_tutor(),
        make_grader(),
        make_grade_verifier(),
        make_reporter(),
    ],
)
