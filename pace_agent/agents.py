"""The five specialized Pace agents, as factory functions.

Each call returns a FRESH LlmAgent instance (in ADK an agent can have only one
parent, so the coordinator and the scripted demo each need their own copies).

`output_key` makes an agent write its result into session state so later agents
can read it. Every instruction is suffixed with a language directive so replies
come back in the configured language (zh / en / ja).
"""
from google.adk.agents import LlmAgent

from .config import lang_directive
from .failover import make_model
from .question_bank import (
    get_quiz,
    get_concept_note,
    get_practice_problem,
    list_topics,
)

_L = lang_directive()


def make_router() -> LlmAgent:
    """Maps a student's free-text request (any language) to a topic id."""
    return LlmAgent(
        name="router_agent",
        model=make_model(),
        description="Maps a student's free-text request to the best-matching topic id.",
        instruction=(
            "You route a student's request to ONE topic.\n"
            "1. Call list_topics() to see the available topics (id, label, grade).\n"
            "2. Match ONLY if one of the listed topics genuinely covers the "
            "request (it may be in any language, e.g. '我想学分数' -> a fractions "
            "topic). Judge by the actual math concept, not loose word overlap.\n"
            "3. If a topic truly matches, reply with ONLY its id (e.g. "
            "fraction_add_sub) — no other text.\n"
            "4. If NONE of the listed topics is about the requested concept "
            "(e.g. the student asks for a topic we don't have), reply with exactly "
            "NONE. Do NOT force an unrelated topic."
            # NOTE: no language directive — this agent returns an id or NONE.
        ),
        tools=[list_topics],
    )


def make_grade_verifier() -> LlmAgent:
    """Second-pass check that corrects a weak model's grading against ground truth."""
    return LlmAgent(
        name="grade_verifier",
        model=make_model(),
        description="Verifies and corrects a grading against the known correct answer.",
        instruction=(
            "You produce the FINAL grading feedback. You are given: the problem, "
            "the CORRECT answer, the student's answer, and a draft feedback.\n"
            "Decide strictly by comparing the student's answer to the CORRECT "
            "answer — do not trust the draft if it conflicts or talks about a "
            "different problem.\n"
            "Output: start with 'Correct' or 'Not yet', then one short line with "
            "the right method/answer. Under 80 words." + _L
        ),
    )


def make_diagnostic() -> LlmAgent:
    return LlmAgent(
        name="diagnostic_agent",
        model=make_model(),
        description="Assesses a student with a short quiz and pinpoints the exact gap.",
        instruction=(
            "You are Pace's Diagnostic agent. (You can call list_topics() to see "
            "available topics across grades 4-12.)\n"
            "1. Call get_quiz(topic) to fetch the diagnostic questions.\n"
            "2. You will be given the student's answers. Compare them to the "
            "correct answers and identify WHICH SPECIFIC CONCEPT they are weak on "
            "(use the `concept` field of each missed question) — not a vague "
            "'needs work on math', but the precise sub-skill.\n"
            "3. Output a short, friendly 'diagnosis card' with: Strengths, the ONE "
            "key gap to fix first, and an estimated mastery % for that concept. "
            "Keep it under 80 words." + _L
        ),
        tools=[get_quiz, list_topics],
        output_key="diagnosis",
    )


def make_planner() -> LlmAgent:
    return LlmAgent(
        name="planner_agent",
        model=make_model(),
        description="Turns a diagnosis into a short, adaptive daily study plan.",
        instruction=(
            "You are Pace's Planner agent. Read the diagnosis you are given and "
            "build a focused 5-day study plan that targets the identified gap "
            "first.\n"
            "- One short line per day (Day 1..Day 5).\n"
            "- Clearly mark Today (Day 1).\n"
            "- Keep each day achievable in ~15 minutes.\n"
            "Output only the plan, no preamble." + _L
        ),
        output_key="plan",
    )


def make_tutor(lang: str | None = None) -> LlmAgent:
    """The heart of the demo: Socratic one-on-one tutoring.

    `lang` (zh/en/ja) overrides the configured default so the web UI can switch
    the tutoring language per session without a redeploy.
    """
    return LlmAgent(
        name="tutor_agent",
        model=make_model(),
        description="Teaches one-on-one with Socratic questioning, never just giving the answer.",
        instruction=(
            "You are Pace's Tutor agent — a warm, patient one-on-one tutor, "
            "teaching the gap concept from the diagnosis.\n\n"
            "GOLDEN RULES:\n"
            "1. NEVER hand over the final answer immediately. Guide the student to "
            "it with ONE small leading question at a time.\n"
            "2. Respond to what the student actually said.\n"
            "3. If they're stuck, give a small hint, not the answer.\n"
            "4. When they get it, affirm warmly and move one step forward.\n"
            "5. Plain language, encouraging tone, short messages (2-4 sentences).\n"
            "6. You may call get_concept_note(topic, concept) to ground a hint.\n\n"
            "Begin with ONE question that surfaces the student's current thinking."
            + lang_directive(lang)
        ),
        tools=[get_concept_note],
    )


def make_grader() -> LlmAgent:
    return LlmAgent(
        name="grader_agent",
        model=make_model(),
        description="Checks a student's answer to a problem and explains any mistake.",
        instruction=(
            "You are Pace's Grader agent. You may call get_practice_problem(topic) "
            "to get a problem and its model answer. Given the student's answer:\n"
            "- State clearly: Correct or Not yet.\n"
            "- If not yet, point to the exact step that went wrong and show the "
            "right method briefly.\n"
            "- End with one short encouraging sentence. Under 90 words." + _L
        ),
        tools=[get_practice_problem],
        output_key="grading",
    )


def make_reporter() -> LlmAgent:
    return LlmAgent(
        name="reporter_agent",
        model=make_model(),
        description="Writes a short, clear weekly progress report for the parent.",
        instruction=(
            "You are Pace's Parent-Reporter agent. Using the diagnosis, the plan, "
            "and how tutoring/grading went, write a SHORT weekly progress report "
            "for the PARENT (not the student).\n"
            "Format as a brief message:\n"
            "- Subject line\n"
            "- 2-3 sentences: what improved (use before -> after on the key "
            "concept) and what's next. Start with a neutral greeting like "
            "'Hi there,' (do not invent a name).\n"
            "- Warm, plain, no jargon. Under 90 words." + _L
        ),
        output_key="report",
    )
