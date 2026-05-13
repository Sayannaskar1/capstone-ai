import json
import re
from typing import TypedDict, List, Dict, Any, Tuple

import os
from dotenv import load_dotenv

load_dotenv()

from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, END



# ── 1. State ───────────────────────────────────────────────────────────────────
class PipelineState(TypedDict):
    document_text:    str
    compliance_rules: str
    analysis_report:  str
    rule_results:     List[Dict[str, Any]]
    final_score:      float
    overall_status:   str
    pages_text:       List[Tuple[int, str]]   # kept for page-citation only
    page_results:     List[Dict[str, Any]]    # kept for API compat, always []


# ── 2. LLM ────────────────────────────────────────────────────────────────────
import streamlit as st

# Safely fetch API key prioritizing Streamlit secrets for cloud deployment, then local env
try:
    groq_api_key = st.secrets.get("GROQ_API_KEY", os.getenv("GROQ_API_KEY"))
except FileNotFoundError:
    groq_api_key = os.getenv("GROQ_API_KEY")

llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.0, api_key=groq_api_key)


# ── 3. Helpers ────────────────────────────────────────────────────────────────
def _parse_rules(text: str) -> List[str]:
    rules = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        cleaned = re.sub(r"^\d+[\.)\-]\s*", "", line)
        if cleaned:
            rules.append(cleaned)
    return rules


_STATUS_WEIGHT = {"COMPLIANT": 1.0, "PARTIAL": 0.5, "NON-COMPLIANT": 0.0}
_STATUS_RANK   = {"NON-COMPLIANT": 0, "PARTIAL": 1, "COMPLIANT": 2}

_PRESENCE_KEYWORDS = (
    "must contain", "must be present", "must be defined", "must be stated",
    "must be specified", "must include", "must have", "must state",
    "must mention", "must specify", "clearly defined", "explicitly defined",
    "explicitly stated", "must be clearly", "must be listed", "must be provided",
    "must be documented", "must be outlined", "must be detailed",
)
_DETECTION_KEYWORDS = (
    "flag any", "flag if", "report as non-compliant if found",
    "must not contain", "must not include", "detect", "identify any",
    "non-compliant if found", "report as non-compliant",
)


def _is_presence_rule(rule_text: str) -> bool:
    t = rule_text.lower()
    if any(kw in t for kw in _DETECTION_KEYWORDS):
        return False
    return any(kw in t for kw in _PRESENCE_KEYWORDS)


def _determine_overall_status(score: float, rule_results: List[Dict]) -> str:
    # Any detection rule violation forces NON-COMPLIANT regardless of score
    if any(r["status"] == "NON-COMPLIANT" and r.get("rule_type") == "detection"
           for r in rule_results):
        return "NON-COMPLIANT"
    if score >= 80:
        return "COMPLIANT"
    if score >= 50:
        return "PARTIAL"
    return "NON-COMPLIANT"


def _compute_score(status: str, confidence: int) -> float:
    """Score is purely status-based: COMPLIANT=100, PARTIAL=50, NON-COMPLIANT=0.
    Confidence is displayed separately as a reliability indicator."""
    return round(_STATUS_WEIGHT.get(status, 0.0) * 100, 2)


# ── BATCHED prompt: evaluate ALL rules in ONE call ─────────────────────────────
def _build_batch_prompt() -> PromptTemplate:
    return PromptTemplate.from_template(
        "You are a senior compliance officer performing a formal document audit. "
        "Read the document text carefully and evaluate it against EVERY rule listed below. "
        "Respond ONLY with a valid JSON array — no prose, no markdown.\n\n"
        "RULES TO EVALUATE:\n{rules_text}\n\n"
        "DOCUMENT TEXT:\n{context}\n\n"
        "EVALUATION INSTRUCTIONS:\n"
        "For each rule, determine the status using ONLY these three values:\n"
        "  COMPLIANT     — The document fully satisfies this rule.\n"
        "  PARTIAL       — The document partially satisfies this rule (some elements present, some missing).\n"
        "  NON-COMPLIANT — The document does not satisfy this rule at all.\n\n"
        "CRITICAL LOGIC:\n"
        "  • 'Must contain / must define / must state / must specify' rules:\n"
        "    → COMPLIANT if the required content is clearly present in the text.\n"
        "    → NON-COMPLIANT if the required content is completely absent.\n"
        "  • 'Must NOT contain / No X / Flag if X found' rules:\n"
        "    → COMPLIANT if X is NOT present (absence = good).\n"
        "    → NON-COMPLIANT if X IS found in the text.\n"
        "  • For SLA / legal docs: look for explicit clauses, percentages, timeframes, and legal terms.\n"
        "  • For PII rules: only flag data that is explicitly and clearly present.\n"
        "  • For encoding/UTF-8: only flag garbled bytes or non-Latin scripts. Symbols like +,-,@,digits are valid UTF-8.\n"
        "  • Do NOT invent violations. Base your judgment only on the text provided.\n"
        "  • llm_confidence (0-100): how confident you are in your verdict.\n\n"
        "OUTPUT FORMAT — return ONLY this JSON array, one object per rule, in the same order:\n"
        '[{{"rule":"<exact rule text>","status":"<COMPLIANT|PARTIAL|NON-COMPLIANT>",'
        '"explanation":"<one concise sentence citing evidence or lack thereof>","llm_confidence":<0-100>}}]'
    )


def _extract_json_array(text: str) -> list:
    """Extract a JSON array from LLM output, with fallback strategies."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    # Try direct parse
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return [result]
    except json.JSONDecodeError:
        pass

    # Find array brackets
    s = text.find("[")
    e = text.rfind("]")
    if s != -1 and e > s:
        try:
            result = json.loads(text[s:e+1])
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    # Find individual JSON objects
    objects = []
    for m in re.finditer(r'\{[^{}]*\}', text):
        try:
            obj = json.loads(m.group())
            objects.append(obj)
        except json.JSONDecodeError:
            continue
    if objects:
        return objects

    raise json.JSONDecodeError("No valid JSON array found", text, 0)


def _extract_json(text: str) -> dict:
    """Extract a single JSON object (fallback for single-rule mode)."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    s, e = text.find("{"), text.rfind("}")
    if s != -1 and e > s:
        try:
            return json.loads(text[s:e+1])
        except json.JSONDecodeError:
            pass
    if s != -1:
        frag = text[s:]
        missing = frag.count("{") - frag.count("}")
        if missing > 0:
            try:
                return json.loads(frag + "}" * missing)
            except json.JSONDecodeError:
                pass
    raise json.JSONDecodeError("No valid JSON", text, 0)


def _normalize_result(r: dict, rule: str) -> Dict[str, Any]:
    """Normalize a single rule result dict."""
    r.setdefault("rule", rule)
    r.setdefault("status", "NON-COMPLIANT")
    r.setdefault("explanation", "No explanation provided.")
    r.setdefault("llm_confidence", 50)
    r["status"] = r["status"].upper().strip()
    if r["status"] not in _STATUS_WEIGHT:
        r["status"] = "NON-COMPLIANT"
    r["compliance_score"] = _compute_score(r["status"], int(r["llm_confidence"]))
    return r


def _call_llm_batch(rules: List[str], context: str) -> List[Dict[str, Any]]:
    """Evaluate ALL rules in a single LLM call (fast)."""
    rules_text = "\n".join(f"{i+1}. {r}" for i, r in enumerate(rules))
    prompt = _build_batch_prompt()
    raw = (prompt | llm).invoke({"rules_text": rules_text, "context": context}).content.strip()

    try:
        results = _extract_json_array(raw)
        # Normalize and pair with rules
        normalized = []
        for i, rule in enumerate(rules):
            if i < len(results):
                normalized.append(_normalize_result(results[i], rule))
            else:
                normalized.append({
                    "rule": rule, "status": "NON-COMPLIANT",
                    "explanation": "LLM did not return result for this rule.",
                    "llm_confidence": 0, "compliance_score": 0.0,
                })
        return normalized
    except json.JSONDecodeError:
        # Fallback: return error for all rules
        return [{
            "rule": rule, "status": "NON-COMPLIANT",
            "explanation": f"Batch parse error: {raw[:120]}",
            "llm_confidence": 0, "compliance_score": 0.0,
        } for rule in rules]


# ── 4. Main pipeline node ─────────────────────────────────────────────────────
def check_compliance(state: PipelineState) -> dict:
    """
    FAST BATCHED APPROACH:
    - Retrieve relevant chunks via RAG
    - Evaluate ALL rules in a SINGLE LLM call (not one-per-rule)
    - Aggregate scores → final verdict
    - Pages used ONLY to cite where violations / clauses were found
    """
    from pdf_processor import chunk_text

    rules      = _parse_rules(state["compliance_rules"])
    full_text  = state.get("document_text", "")
    pages_text = state.get("pages_text", [])

    # ── Text Truncation to respect Groq Free Tier (6,000 TPM) ──────────────
    # RAG (FAISS) destroys the chronological structure of the document and causes 
    # the LLM to hallucinate on negative compliance rules. Instead, we simply 
    # truncate the document to the first ~15,000 characters (approx 4,000 tokens).
    # This ensures the LLM reads the first 4-5 pages perfectly in order, without 
    # crashing the Groq API.
    # ── Smart context sampling: head + tail covers most legal/SLA docs ───────
    # Legal and SLA documents often have key clauses at the END (termination,
    # penalties, jurisdiction). Taking only the first N chars misses these.
    # We sample the beginning (overview/definitions) + end (specific clauses).
    MAX_HEAD = 12000   # ~3,000 tokens — covers intro, scope, key definitions
    MAX_TAIL = 4000    # ~1,000 tokens — covers final clauses, SLA tables, penalties
    if len(full_text) <= MAX_HEAD + MAX_TAIL:
        context = full_text
    else:
        head = full_text[:MAX_HEAD]
        tail = full_text[-MAX_TAIL:]
        context = head + "\n\n[... middle section omitted for brevity ...]\n\n" + tail

    # ── Single batched LLM call for ALL rules ────────────────────────────────
    raw_results = _call_llm_batch(rules, context)

    rule_results: List[Dict[str, Any]] = []
    for i, rule in enumerate(rules):
        r         = raw_results[i] if i < len(raw_results) else {}
        status    = r.get("status", "NON-COMPLIANT")
        conf      = int(r.get("llm_confidence", 0))
        score     = r.get("compliance_score", 0.0)
        exp       = r.get("explanation", "")
        is_pres   = _is_presence_rule(rule)
        rule_type = "presence" if is_pres else "detection"
        summary = exp

        rule_results.append({
            "rule":             rule,
            "status":           status,
            "explanation":      summary,
            "llm_confidence":   conf,
            "compliance_score": score,
            "rule_type":        rule_type,
        })

    # ── Final score and status ───────────────────────────────────────────────
    final_score    = round(sum(r["compliance_score"] for r in rule_results)
                           / max(len(rule_results), 1), 2)
    overall_status = _determine_overall_status(final_score, rule_results)

    n_c  = sum(1 for r in rule_results if r["status"] == "COMPLIANT")
    n_p  = sum(1 for r in rule_results if r["status"] == "PARTIAL")
    n_nc = sum(1 for r in rule_results if r["status"] == "NON-COMPLIANT")

    # ── Text report ──────────────────────────────────────────────────────────
    lines = [
        f"## Compliance Analysis Report\n",
        f"**Overall Status:** {overall_status}",
        f"**Final Compliance Score:** {final_score}/100\n",
        "---", "### Rule Results\n",
    ]
    for i, r in enumerate(rule_results, 1):
        e = {"COMPLIANT": "✅", "PARTIAL": "⚠️", "NON-COMPLIANT": "❌"}.get(r["status"], "❓")
        lines.append(
            f"**Rule {i}:** {r['rule']}\n"
            f"- {e} {r['status']} | Score: {r['compliance_score']}/100\n"
            f"- {r['explanation']}\n"
        )
    lines += [
        "---", "### Summary\n",
        f"Compliant: {n_c}  Partial: {n_p}  Non-Compliant: {n_nc}",
        f"**Overall: {final_score}/100 → {overall_status}**",
    ]

    return {
        "analysis_report":  "\n".join(lines),
        "rule_results":     rule_results,
        "final_score":      final_score,
        "overall_status":   overall_status,
        "page_results":     [],       # not used — kept for state compat
        "pages_text":       pages_text,
    }


# ── 5. Graph ──────────────────────────────────────────────────────────────────
workflow = StateGraph(PipelineState)
workflow.add_node("analyze_compliance", check_compliance)
workflow.set_entry_point("analyze_compliance")
workflow.add_edge("analyze_compliance", END)
compliance_pipeline = workflow.compile()
