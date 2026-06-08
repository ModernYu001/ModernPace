"""End-to-end demo of the HYBRID Pace loop.

Engineering principle: deterministic code for anything with a ground truth
(routing hits, diagnosis, grading, plan, report); the LLM only for the
open-ended Tutor dialogue. The run prints a metrics line showing how many model
calls were made vs. saved by the hybrid design.

    python -m pace_agent.demo

Reads config from .env automatically (see README / .env.example).
"""
import asyncio
import os

from google.adk.runners import InMemoryRunner
from google.genai import types

from .config import APP_NAME, DEFAULT_TOPIC, API_KEYS
from .question_bank import get_quiz, get_practice_problem
from .curriculum import all_ready_topics
from .agents import make_router, make_tutor
from . import engine
from .cache import Metrics, cache_get, cache_put

USER_ID = "student_demo"


def banner(step: str, title: str) -> None:
    print("\n" + "=" * 64)
    print(f"  [{step}]  {title}")
    print("=" * 64)


async def ask(agent, prompt: str) -> str:
    """Run a single-shot agent and return its final text (counts as 1 LLM call)."""
    Metrics.llm_calls += 1
    runner = InMemoryRunner(agent=agent, app_name=APP_NAME)
    session = await runner.session_service.create_session(app_name=APP_NAME, user_id=USER_ID)
    message = types.Content(role="user", parts=[types.Part(text=prompt)])
    final = ""
    async for event in runner.run_async(user_id=USER_ID, session_id=session.id, new_message=message):
        if event.is_final_response() and event.content and event.content.parts:
            final = event.content.parts[0].text or final
    return final.strip()


async def route_topic(text: str):
    """Rule-first routing. Returns a topic id, or None if nothing matches.

    1) local alias rules (no model call); 2) cached LLM fallback; 3) validate.
    """
    hit = engine.rule_match(text)
    if hit:
        Metrics.rule_hits += 1
        return hit
    cached = cache_get("router", text)
    if cached is not None:
        Metrics.cache_hits += 1
        raw = cached
    else:
        raw = await ask(make_router(), f"Student request: {text}")
        cache_put("router", text, raw)
    cand = raw.split()[0].strip(" .,:;`\"'") if raw else ""
    if cand.upper() == "NONE":
        return None
    ready = {t["id"] for t in all_ready_topics()}
    return cand if cand in ready else None


async def tutor_dialogue(agent, opening_context: str, max_turns: int = 6) -> str:
    """The one genuinely open-ended step — kept on the LLM."""
    runner = InMemoryRunner(agent=agent, app_name=APP_NAME)
    session = await runner.session_service.create_session(app_name=APP_NAME, user_id=USER_ID)

    async def turn(text: str) -> str:
        Metrics.llm_calls += 1
        msg = types.Content(role="user", parts=[types.Part(text=text)])
        out = ""
        async for ev in runner.run_async(user_id=USER_ID, session_id=session.id, new_message=msg):
            if ev.is_final_response() and ev.content and ev.content.parts:
                out = ev.content.parts[0].text or out
        return out.strip()

    tutor_msg = await turn(opening_context)
    print(f"\nPace 👩‍🏫: {tutor_msg}")
    for _ in range(max_turns):
        student = input("\nYou ✍️  (type 'done' to finish): ").strip()
        if not student or student.lower() == "done":
            break
        tutor_msg = await turn(student)
        print(f"\nPace 👩‍🏫: {tutor_msg}")
    return "Student worked through the concept with Socratic guidance."


def collect_answers(topic: str) -> dict:
    """Show the topic's quiz and collect the student's answers into {qid: ans}."""
    quiz = get_quiz(topic)
    print(f"\n  Topic: {quiz['topic_label']}  ({quiz['grade_level']})")
    answers = {}
    for q in quiz["questions"]:
        print(f"\n  {q['id']}. {q['prompt']}")
        for c in (q.get("choices") or []):
            print(f"      - {c}")
        answers[q["id"]] = input("  你的答案: ").strip()
    return answers


def scripted_answers() -> dict:
    """Pre-filled answers for the classic discriminant recording (2 mistakes)."""
    return {"q1": "2", "q2": "2", "q3": "2", "q4": "b^2-4ac", "q5": "25"}


async def main() -> None:
    Metrics.reset()
    if not (any(k for k in API_KEYS) or os.getenv("GOOGLE_GENAI_USE_VERTEXAI")):
        print("⚠️  No API key found. Add GOOGLE_API_KEY or PACE_API_KEYS to .env "
              "(see .env.example) before running.")
        return

    print("\n🎓  Pace — your personal AI study coach  (hybrid: code for facts, LLM for tutoring)")

    # ── 0. Routing (rule-first) ──────────────────────────────────────────────
    banner("0/5", "Router — what do you want to learn? (rules first, LLM only if needed)")
    labels = {t["id"]: t["label"] for t in all_ready_topics()}
    print("  可选主题：", "，".join(labels.values()))
    topic = None
    while topic is None:
        want = input("\n  你想学什么？(直接回车 = 默认演示：判别式)\n  > ").strip()
        if not want:
            topic = DEFAULT_TOPIC
            print("  → 默认演示：一元二次方程的判别式")
            answers = scripted_answers()
            break
        matched = await route_topic(want)
        if matched is None:
            print(f"  ⚠️  暂时没有和『{want}』匹配的主题，请换个说法或从列表里选；回车用默认。")
            continue
        topic = matched
        print(f"  → 主题：{labels.get(topic, topic)}  ({topic})")
        answers = collect_answers(topic)

    # ── 1. Diagnose (deterministic) ──────────────────────────────────────────
    banner("1/5", "Diagnosis — deterministic from the answer key (no LLM)")
    d = engine.diagnose(topic, answers)
    Metrics.deterministic += 1
    print(engine.render_diagnosis(d))

    # ── 2. Plan (template) ───────────────────────────────────────────────────
    banner("2/5", "Plan — generated from the gap (no LLM)")
    Metrics.deterministic += 1
    print(engine.build_plan(d))

    # ── 3. Tutor (LLM — the part that needs it) ──────────────────────────────
    banner("3/5", "Tutor — Socratic one-on-one (LLM; type your answers)")
    transcript = await tutor_dialogue(
        make_tutor(),
        f"Topic: {topic}. Diagnosis:\n{engine.render_diagnosis(d)}\n\n"
        "Begin tutoring the key gap with one opening question.",
    )

    # ── 4. Grade (deterministic, verified by construction) ───────────────────
    banner("4/5", "Grade — checked against the answer key (no LLM, no hallucination)")
    prob = get_practice_problem(topic)
    student_practice = input(f"\nPractice — {prob['prompt']}\nYour answer: ").strip()
    g = engine.grade_practice(topic, student_practice)
    Metrics.deterministic += 1
    print(engine.render_grading(topic, g, student_practice))

    # ── 5. Parent report (template) ──────────────────────────────────────────
    banner("5/5", "Parent report — generated from the facts (no LLM)")
    Metrics.deterministic += 1
    print(engine.build_report(d, g))

    print("\n✅  Full loop complete: route → diagnose → plan → tutor → grade → report.")
    print("📊  " + Metrics.summary())


if __name__ == "__main__":
    asyncio.run(main())
