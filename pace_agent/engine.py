"""Deterministic engine — the logic that does NOT need an LLM.

Design principle: use code for anything with a ground truth (answer checking,
gap detection, plans, reports, common-phrasing routing); reserve the LLM for the
genuinely open-ended part (Socratic tutoring). This is cheaper, faster, and
removes a whole class of hallucinations (e.g. grading a discriminant question as
if it were fractions).

Everything here is pure Python: no network, no model calls.
"""
import re

from .config import PACE_LANG, DEFAULT_TOPIC
from .curriculum import load_topic, all_ready_topics

# ── answer normalization & matching ──────────────────────────────────────────
def _norm(s: str) -> str:
    s = str(s).strip().lower()
    s = (s.replace("（", "(").replace("）", ")").replace("，", ",")
           .replace("²", "^2").replace("³", "^3").replace("−", "-").replace("×", "*"))
    s = re.sub(r"\s+", "", s)
    return s


def _is_num(s: str) -> bool:
    return bool(re.fullmatch(r"-?\d+(\.\d+)?", _norm(s)))


def _head(s: str):
    """Leading signed number of a string, if any (e.g. '1（重根）' -> '1')."""
    m = re.match(r"-?\d+", _norm(s))
    return m.group(0) if m else None


def answer_is_correct(question: dict, student: str) -> bool:
    """Deterministically decide if a student's free-typed answer is correct.

    Handles value answers, exact choice text, leading-number equality, and
    (only when options aren't themselves numbers) 1-based option index.
    """
    correct = question.get("answer", "")
    choices = question.get("choices") or []
    ns, nc = _norm(student), _norm(correct)
    if not ns:
        return False
    if ns == nc:
        return True
    # student typed a choice's exact text
    for ch in choices:
        if _norm(ch) == ns:
            return ns == nc
    # numeric / leading-token equality (covers '1' vs '1（重根）', '25', etc.)
    h = _head(ns)
    if h is not None and h == _head(nc):
        return True
    # option index, only safe when the options are not bare numbers
    if ns.isdigit() and choices and not all(_is_num(c) for c in choices):
        idx = int(ns) - 1
        if 0 <= idx < len(choices):
            return _norm(choices[idx]) == nc
    return False


def key_is_correct(key: str, student: str) -> bool:
    """Looser match for free-form practice answers against a short answer key."""
    nk, ns = _norm(key), _norm(student)
    if not ns:
        return False
    if nk == ns or nk in ns or ns in nk:
        return True
    h = _head(ns)
    return h is not None and h == _head(nk)


# ── diagnosis (replaces the Diagnostic LLM call) ─────────────────────────────
def diagnose(topic: str, answers: dict) -> dict:
    """answers: {qid: raw student answer}. Returns a structured diagnosis."""
    t = load_topic(topic if topic else DEFAULT_TOPIC)
    per, missed, got = [], [], []
    for q in t["questions"]:
        ok = answer_is_correct(q, answers.get(q["id"], ""))
        per.append({"id": q["id"], "ok": ok, "concept": q["concept"]})
        (got if ok else missed).append(q["concept"])
    gap = missed[0] if missed else None
    gap_qs = [p for p in per if gap and p["concept"] == gap]
    gap_mastery = round(100 * sum(p["ok"] for p in gap_qs) / len(gap_qs)) if gap_qs else 100
    n_ok = sum(p["ok"] for p in per)
    return {
        "topic": topic,
        "topic_label": t["topic_label"],
        "per": per,
        "score": n_ok,
        "total": len(per),
        "overall_mastery": round(100 * n_ok / len(per)) if per else 0,
        "gap": gap,
        "gap_note": t["concepts"].get(gap, "") if gap else "",
        "gap_mastery": gap_mastery,
        "strength_notes": [t["concepts"].get(c, c) for c in dict.fromkeys(got)],
    }


# ── grading practice (replaces Grader + Verifier LLM calls) ──────────────────
def grade_practice(topic: str, student: str) -> dict:
    t = load_topic(topic if topic else DEFAULT_TOPIC)
    prob = t["practice"][0]
    key = prob.get("key", prob["answer"])
    ok = key_is_correct(key, student)
    return {"ok": ok, "problem": prob["prompt"], "answer": prob["answer"], "key": key}


# ── localized templates (replace Planner + Reporter LLM calls) ───────────────
def _lang(lang: str | None = None) -> str:
    """Resolve the template language. Pass an explicit lang (zh/en/ja) to override
    the configured default; ja falls back to en for the fixed templates (the LLM
    Tutor still replies in true Japanese)."""
    l = lang or PACE_LANG
    return l if l in ("zh", "en") else "en"  # ja -> en fallback


def render_diagnosis(d: dict, lang: str | None = None) -> str:
    if _lang(lang) == "zh":
        strengths = "；".join(d["strength_notes"][:2]) or "基础概念"
        if not d["gap"]:
            return (f"诊断：{d['topic_label']}\n太棒了，全部答对（{d['score']}/{d['total']}）！"
                    "可以直接挑战更难的题。")
        return (f"诊断：{d['topic_label']}\n"
                f"得分 {d['score']}/{d['total']}，总体掌握约 {d['overall_mastery']}%。\n"
                f"强项：{strengths}\n"
                f"首要薄弱点：{d['gap_note']}（该点掌握约 {d['gap_mastery']}%）。\n"
                f"建议先把这一点弄懂，加油！")
    strengths = "; ".join(d["strength_notes"][:2]) or "the basics"
    if not d["gap"]:
        return (f"Diagnosis: {d['topic_label']}\nGreat — all correct "
                f"({d['score']}/{d['total']})! Ready for harder problems.")
    return (f"Diagnosis: {d['topic_label']}\n"
            f"Score {d['score']}/{d['total']}, overall mastery ~{d['overall_mastery']}%.\n"
            f"Strengths: {strengths}\n"
            f"Key gap: {d['gap_note']} (~{d['gap_mastery']}% on this).\n"
            f"Let's fix this one first.")


def build_plan(d: dict, lang: str | None = None) -> str:
    note = d["gap_note"] or d["topic_label"]
    if not d["gap"]:
        note = f"{d['topic_label']} 的进阶应用" if _lang(lang) == "zh" else f"advanced {d['topic_label']}"
    if _lang(lang) == "zh":
        return ("\n".join([
            f"Today（Day 1）：弄懂核心薄弱点 —— {note}",
            "Day 2：在该知识点上做 3 道针对性练习",
            "Day 3：用自己的话讲一遍这个知识点（费曼法）",
            "Day 4：做 2 道综合题，混合考查",
            "Day 5：限时小测，巩固并查漏",
        ]))
    return ("\n".join([
        f"Today (Day 1): nail the key gap — {note}",
        "Day 2: 3 targeted practice problems on it",
        "Day 3: explain it in your own words (Feynman)",
        "Day 4: 2 mixed problems",
        "Day 5: a short timed quiz to lock it in",
    ]))


def render_grading(topic: str, g: dict, student: str, lang: str | None = None) -> str:
    t = load_topic(topic if topic else DEFAULT_TOPIC)
    note = t["concepts"].get(t["practice"][0].get("concept", ""), "")
    if _lang(lang) == "zh":
        head = "✅ 正确！" if g["ok"] else "❌ 还不对。"
        body = "做得好，思路清晰。" if g["ok"] else f"正确做法：{g['answer']}"
        tip = f"\n要点：{note}" if note else ""
        return f"{head} {body}{tip}"
    head = "✅ Correct!" if g["ok"] else "❌ Not yet."
    body = "Nicely reasoned." if g["ok"] else f"Correct approach: {g['answer']}"
    tip = f"\nKey idea: {note}" if note else ""
    return f"{head} {body}{tip}"


def build_report(d: dict, g: dict, lang: str | None = None) -> str:
    moved = (d["gap_mastery"], min(100, max(d["gap_mastery"] + 30, 90))) if d["gap"] else (90, 100)
    practice_line_zh = "课堂练习答对了。" if g["ok"] else "课堂练习还需巩固。"
    practice_line_en = "Nailed the practice problem." if g["ok"] else "Still consolidating the practice problem."
    if _lang(lang) == "zh":
        focus = d["gap_note"] or "进阶内容"
        return ("主题：" + d["topic_label"] + "\n"
                "您好，\n"
                f"本周孩子在「{d['topic_label']}」上学习。{practice_line_zh} "
                f"核心薄弱点的掌握度从约 {moved[0]}% 提升到约 {moved[1]}%。"
                f"下一步：继续巩固「{focus}」并做综合练习。")
    focus = d["gap_note"] or "advanced material"
    return ("Subject: " + d["topic_label"] + " — weekly progress\n"
            "Hi there,\n"
            f"This week your child worked on {d['topic_label']}. {practice_line_en} "
            f"Mastery of the key concept moved from ~{moved[0]}% to ~{moved[1]}%. "
            f"Next: keep reinforcing {focus} with mixed practice.")


# ── routing alias table (rule-first; LLM is only the fallback) ────────────────
_ALIASES = {
    "operations_laws": ["运算定律", "乘法分配律", "分配律", "结合律", "交换律", "简便运算", "简便计算", "operation law", "distributive"],
    "fraction_add_sub": ["分数", "通分", "异分母", "约分", "fraction"],
    "percentage": ["百分数", "百分比", "百分之", "折扣", "打折", "percent", "percentage"],
    "rational_number_ops": ["有理数", "负数", "正负", "正负数", "绝对值", "rational number", "negative number"],
    "linear_function": ["一次函数", "斜率", "截距", "直线方程", "linear function", "slope"],
    "quadratic_discriminant": ["判别式", "一元二次方程", "二次方程", "根的个数", "实数根", "discriminant", "quadratic"],
    "exponential_log": ["指数", "对数", "幂", "次方", "log", "logarithm", "exponent"],
    "sequences": ["数列", "等差", "等比", "通项", "求和", "sequence", "arithmetic sequence", "geometric"],
    "derivative_application": ["导数", "求导", "单调", "单调性", "微分", "derivative", "monoton"],
}


def rule_match(text: str):
    """Map free text to a topic id by rules (no LLM). Returns id or None.

    Two passes, longest-match wins:
    1. curated synonym aliases (handles colloquial phrasings);
    2. the topic's own label — if a >=2-char label is contained in the query or
       vice versa — which auto-covers every catalog topic with no hand-tuning.
    """
    nt = _norm(text)
    ready = all_ready_topics()
    ready_ids = {t["id"] for t in ready}
    best, best_len = None, 0
    # pass 1: curated aliases
    for tid, aliases in _ALIASES.items():
        if tid not in ready_ids:
            continue
        for a in aliases:
            na = _norm(a)
            if na and na in nt and len(na) > best_len:
                best, best_len = tid, len(na)
    # pass 2: topic-label match (covers all topics automatically)
    for t in ready:
        nl = _norm(t["label"])
        if len(nl) >= 2 and (nl in nt or nt in nl) and len(nl) > best_len:
            best, best_len = t["id"], len(nl)
    return best
