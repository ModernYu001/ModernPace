# Pace — a personal AI study coach

> Diagnose the gap → plan the path → tutor Socratically → grade the work →
> report to parents. A full one-on-one tutoring loop, for about the price of a
> single tutoring hour a month.

[![Built with Google ADK](https://img.shields.io/badge/Built%20with-Google%20ADK-4285F4)](https://google.github.io/adk-docs/)
[![Gemini](https://img.shields.io/badge/Reasoning-Gemini-8E75B2)](https://ai.google.dev/)
[![MCP](https://img.shields.io/badge/Tools-MCP-000000)](https://modelcontextprotocol.io/)
[![Cloud Run](https://img.shields.io/badge/Deploy-Cloud%20Run-4285F4)](https://cloud.google.com/run)

Built for the **Google for Startups AI Agents Challenge (Track 1: Build)**.

**Live demo:** https://pace-427211099336.asia-northeast1.run.app  ·  **Repo:** https://github.com/ModernYu001/ModernPace

---

## Why Pace

A good human tutor does five things: figures out *exactly* what you don't get,
makes a plan, teaches without just handing over answers, checks your work, and
keeps your parents in the loop. Pace is a multi-agent system that does all five —
in any of grades 4–12, in Chinese, English, or Japanese.

The design bet: **use deterministic code for everything that has a ground truth,
and spend the LLM only on the one genuinely open-ended part — the Socratic
tutoring dialogue.** That makes Pace cheaper, faster, and immune to a whole class
of hallucinations (e.g. grading a discriminant question as if it were fractions).

---

## Architecture at a glance

Pace ships **two interchangeable execution paths over one shared core**:

```
            ┌──────────────────── shared core ────────────────────┐
            │  curriculum.py  →  data/curriculum.json + topics/    │
            │  engine.py      →  deterministic logic (ground truth)│
            │  question_bank  →  tools, ALSO served over MCP       │
            └──────────────────────────────────────────────────────┘
                      ▲                               ▲
        ┌─────────────┴─────────────┐   ┌─────────────┴──────────────┐
        │  PATH 1 · Hybrid engine   │   │  PATH 2 · ADK multi-agent  │
        │  demo.py / web/server.py  │   │  agent.py  (root_agent)    │
        │  code for facts, LLM for  │   │  coordinator delegates to  │
        │  the Tutor only           │   │  7 specialists over A2A    │
        └───────────────────────────┘   └────────────────────────────┘
```

- **Path 1 (Hybrid)** is the polished demo surface (`web/server.py` web UI and
  `demo.py` CLI). Deterministic steps run in `engine.py`; only the Tutor calls
  Gemini.
- **Path 2 (Multi-agent)** is the ADK coordinator in `agent.py`: a root agent
  that delegates to seven specialist `LlmAgent`s via ADK's in-framework
  **Agent2Agent (A2A)** transfer. Run it with `adk web` / `adk run`.

Both paths read the same curriculum and the same tools — so the MCP server, the
115-topic question bank, and the failover model layer are shared.

**Mandatory-tech mapping:** **ADK** (agents + orchestration) · **Gemini / Vertex
AI** (reasoning) · **A2A** (ADK multi-agent transfer in `agent.py`) · **MCP**
(`mcp_server.py`) · **Cloud Run** (`Dockerfile` + `deploy.sh`).

---

## What's inside

```
pace/
├── pace_agent/
│   ├── agent.py            # root_agent coordinator — A2A path (adk web / adk run)
│   ├── agents.py           # the 7 specialist LlmAgents (factory functions)
│   ├── engine.py           # deterministic logic: diagnose / grade / plan / report / route
│   ├── curriculum.py       # data layer: loads catalog + per-topic files (swappable)
│   ├── question_bank.py    # tools the agents call (quiz / concept / practice / list)
│   ├── mcp_server.py       # the SAME tools served over MCP (mandatory tech)
│   ├── failover.py         # FailoverLlm: model-pool × key-pool rotation + 429 failover
│   ├── cache.py            # tiny disk cache + run metrics (LLM calls saved)
│   ├── config.py           # model pool, key pool, language, defaults (.env-driven)
│   ├── demo.py             # scripted end-to-end CLI demo (good for the video)
│   └── route.py            # natural-language → topic id (standalone)
├── web/
│   ├── server.py           # FastAPI backend driving the full loop (Cloud Run target)
│   └── index.html          # single-file front end
├── data/
│   ├── curriculum.json     # catalog: grades 4–12 and their topics
│   └── topics/<id>.json    # 115 authored topics (questions / concepts / practice)
├── Dockerfile              # container image for Cloud Run
├── deploy.sh               # one-command Cloud Run deploy
├── requirements.txt
└── .env.example
```

---

## Setup (5 minutes)

```bash
cd pace
python -m venv .venv && source .venv/bin/activate     # optional
pip install -r requirements.txt
cp .env.example .env                                  # then add your key
```

Get a **free Gemini API key** from [Google AI Studio](https://aistudio.google.com/apikey).
Everything lives in `.env` — the app auto-loads it (python-dotenv), so you do
**not** need to `export` anything. A typical `.env`:

```ini
GOOGLE_API_KEY=primary_key
PACE_API_KEYS=key_1,key_2,key_3
PACE_MODELS=gemini-2.5-flash,gemini-3-flash-preview,gemini-3.1-flash-lite,gemini-2.5-flash-lite
PACE_LANG=zh
```

> `.env` is git-ignored — it holds real API keys. Confirm your model ids with
> `python list_models.py` (FailoverLlm safely skips any id the backend rejects).

---

## Run it

**A) Web UI (the demo surface — also what deploys to Cloud Run):**
```bash
uvicorn web.server:app --reload --port 8000
# open http://localhost:8000
```

**B) Scripted full-loop CLI demo (good for recording):**
```bash
python -m pace_agent.demo
```
Runs route → diagnose → plan → tutor → grade → report. The Tutor step is
interactive, so the Socratic back-and-forth shows live. It prints a metrics line,
e.g. `📊 LLM calls: 4 | saved by hybrid: 5 (deterministic 4, rules 1, cache 0)`.

**C) ADK multi-agent path (shows A2A — coordinator delegating to specialists):**
```bash
adk web              # pick `pace_agent`, chat with the coordinator
adk run pace_agent   # same, in the terminal
```

**D) Topic routing only (natural language → topic):**
```bash
python -m pace_agent.route "我想学分数"      # -> fraction_add_sub
python -m pace_agent.route                    # interactive
```

### Hybrid design — LLM only where it earns its keep

| Step | How it runs | LLM? |
|------|-------------|------|
| Routing | local alias table → LLM fallback (cached) | only on a miss |
| Diagnosis | compares answers to the key; gap from `concept` tags | no |
| Plan | template from the detected gap | no |
| **Tutor** | open-ended Socratic dialogue | **yes** |
| Grade | compares to the answer `key` (deterministic) | no |
| Parent report | template filled from the facts | no |

A full session drops from ~10–11 model calls to roughly the number of tutor
turns. See `engine.py` (pure-Python logic) and `cache.py` (cache + metrics).

---

## Turn on MCP (for the "mandatory tech" checkbox)

The question bank is also a real MCP server (stdio transport):
```bash
python -m pace_agent.mcp_server
```
Wire it into an agent in place of the local tools:
```python
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from mcp import StdioServerParameters

toolset = MCPToolset(connection_params=StdioServerParameters(
    command="python", args=["-m", "pace_agent.mcp_server"]))
# pass tools=[toolset] to an LlmAgent (e.g. in agents.py)
```

---

## Deploy to Cloud Run (prototype → production)

Two supported paths.

**1) The web UI as a container (recommended — it's the demo surface).**
A `Dockerfile` and a one-command `deploy.sh` are included.

```bash
# one-time
gcloud auth login
gcloud config set project <YOUR_PROJECT_ID>
gcloud services enable run.googleapis.com cloudbuild.googleapis.com

# deploy (reads keys/models from .env, passes them as runtime env vars)
./deploy.sh
# or: PROJECT=my-proj REGION=asia-east1 ./deploy.sh
```

`deploy.sh` builds from source with Cloud Build, deploys an `--allow-unauthenticated`
service named `pace`, and injects `GOOGLE_API_KEY`, `PACE_API_KEYS`, `PACE_MODELS`,
and `PACE_LANG` from your local `.env` via a temporary, git-ignored env file that
is deleted on exit. For production, swap that for **Secret Manager**:
```bash
gcloud run deploy pace --source . --region us-central1 --allow-unauthenticated \
  --set-secrets GOOGLE_API_KEY=pace-gemini-key:latest
```

**2) The ADK agent app (the `adk web` surface):**
```bash
adk deploy cloud_run pace_agent      # follow the prompts (project, region)
```

Put the resulting URL at the top of this README and say "live on Cloud Run" in
the demo video — it's a judging signal.

---

## Demo path (matches the video storyboard)

Scenario: an 8th-grader prepping for an algebra quiz.

1. Quiz → Diagnostic finds the gap is **the discriminant** (not "algebra").
2. Planner builds a 5-day plan and highlights today.
3. Tutor uses Socratic questions so the student reaches the idea themselves.
4. Grader checks a practice problem and explains the mistake.
5. Parent-Reporter writes a weekly progress summary.

---

## Reliability: model + key rotation with automatic failover

Pace runs on a **pool of models and a pool of API keys, both rotated round-robin**
to spread load and dodge per-model/per-key rate limits:

```ini
PACE_MODELS=gemini-2.5-flash,gemini-3-flash-preview,gemini-3.1-flash-lite,gemini-2.5-flash-lite
PACE_API_KEYS=key_1,key_2,key_3      # falls back to GOOGLE_API_KEY
```

Each agent is backed by a `FailoverLlm` (`failover.py`) wrapping both pools. On a
rate-limit/quota error (HTTP 429 / RESOURCE_EXHAUSTED) — or an unavailable/wrong
model id (404) — it transparently retries the next candidate: **switching to the
next API key first** (same model), and only switching model once every key is
spent. This is why the demo keeps working even if a key gets throttled live, and
why an extra speculative model id in the pool is harmless. Pin a single model with
`PACE_MODEL=...` if needed.

---

## Languages

```ini
PACE_LANG=zh     # 中文 (default)
PACE_LANG=en     # English
PACE_LANG=ja     # 日本語
```
Agents reply in this language regardless of the language the question bank is
authored in.

---

## Topics (grades 4–12)

The catalog lives in `data/curriculum.json`. **All 115 topics across the 9 grades
are authored and ready** (人教版 aligned), each with diagnostic questions, concept
notes, and practice problems with answer keys:

| Grade | Ready topics |
|-------|--------------|
| 小学四年级 | 15 / 15 |
| 小学五年级 | 16 / 16 |
| 小学六年级 | 10 / 10 |
| 初中一年级 | 12 / 12 |
| 初中二年级 | 10 / 10 |
| 初中三年级 | 10 / 10 |
| 高中一年级 | 19 / 19 |
| 高中二年级 | 16 / 16 |
| 高中三年级 | 7 / 7 |

Run `python -m pace_agent.route` to list every available topic. Pick one for the
demo with `PACE_TOPIC=fraction_add_sub`.

---

## Add a new topic (no code changes)

1. Create `data/topics/<your_id>.json` with the same schema as an existing file
   (`topic_label`, `grade_level`, `questions[]`, `concepts{}`, `practice[]`).
2. Add an entry under the right grade in `data/curriculum.json` with `"ready": true`.

That's it — the agents and MCP tools pick it up automatically. **Content is data,
not code**, so growing the curriculum never touches the architecture. Later
optimizations (a topic-router agent, a vector store behind `curriculum.py`,
difficulty adaptation) are additive and isolated.

---

## Notes / next steps
- Swap `PACE_MODEL=gemini-2.5-pro` for deeper tutoring if latency allows.
- Safety: responses are age-appropriate, "teach the method not the answer", and
  parent-visible — see the Tutor instruction in `agents.py`.
- `data/questions.json` is the old single-file format, superseded by
  `data/curriculum.json` + `data/topics/` (safe to delete).
