"""Minimal web UI for Pace.

A tiny FastAPI backend that drives the full loop. Deterministic steps
(route / quiz / diagnose / plan / grade / report) use the engine; the Tutor
chat uses the LLM. Same capabilities are also exposed over MCP (mcp_server.py).

Run from the project root (the `pace/` folder):
    pip install -r requirements.txt
    uvicorn web.server:app --reload --port 8000
Then open http://localhost:8000
"""
import os
import uuid

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from google.adk.runners import InMemoryRunner
from google.genai import types

from pace_agent.config import APP_NAME
from pace_agent.question_bank import get_quiz, get_practice_problem
from pace_agent.curriculum import all_ready_topics
from pace_agent.agents import make_tutor
from pace_agent import engine

app = FastAPI(title="Pace")
_HERE = os.path.dirname(__file__)
_tutors: dict = {}  # session id -> (runner, adk_session_id)


@app.get("/")
def index():
    return FileResponse(os.path.join(_HERE, "index.html"))


@app.get("/api/topics")
def api_topics():
    return {"topics": all_ready_topics()}


class RouteIn(BaseModel):
    text: str


@app.post("/api/route")
def api_route(b: RouteIn):
    return {"topic": engine.rule_match(b.text)}


@app.get("/api/quiz")
def api_quiz(topic: str):
    return get_quiz(topic)


class DiagIn(BaseModel):
    topic: str
    answers: dict


@app.post("/api/diagnose")
def api_diagnose(b: DiagIn):
    d = engine.diagnose(b.topic, b.answers)
    return {"card": engine.render_diagnosis(d), "plan": engine.build_plan(d), "raw": d}


@app.get("/api/practice")
def api_practice(topic: str):
    p = get_practice_problem(topic)
    return {"prompt": p["prompt"]}


class GradeIn(BaseModel):
    topic: str
    answer: str


@app.post("/api/grade")
def api_grade(b: GradeIn):
    g = engine.grade_practice(b.topic, b.answer)
    return {"ok": g["ok"], "feedback": engine.render_grading(b.topic, g, b.answer)}


class ReportIn(BaseModel):
    topic: str
    answers: dict
    ok: bool


@app.post("/api/report")
def api_report(b: ReportIn):
    d = engine.diagnose(b.topic, b.answers)
    return {"report": engine.build_report(d, {"ok": b.ok})}


class TutorIn(BaseModel):
    session: str = ""
    topic: str = ""
    diagnosis: str = ""
    message: str = ""


async def _run(runner, sid, adk_sid, text):
    msg = types.Content(role="user", parts=[types.Part(text=text)])
    out = ""
    async for ev in runner.run_async(user_id=sid, session_id=adk_sid, new_message=msg):
        if ev.is_final_response() and ev.content and ev.content.parts:
            out = ev.content.parts[0].text or out
    return out.strip()


@app.post("/api/tutor")
async def api_tutor(b: TutorIn):
    sid = b.session or str(uuid.uuid4())
    if sid not in _tutors:
        runner = InMemoryRunner(agent=make_tutor(), app_name=APP_NAME)
        s = await runner.session_service.create_session(app_name=APP_NAME, user_id=sid)
        _tutors[sid] = (runner, s.id)
        opening = (f"Topic: {b.topic}. Diagnosis:\n{b.diagnosis}\n\n"
                   "Begin tutoring the key gap with one opening question.")
        reply = await _run(runner, sid, s.id, opening)
    else:
        runner, adk_sid = _tutors[sid]
        reply = await _run(runner, sid, adk_sid, b.message)
    return {"session": sid, "reply": reply}
