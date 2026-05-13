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
    pages_text:       List[Tuple[int, str]]
    page_results:     List[Dict[str, Any]]


# ── 2. LLM ────────────────────────────────────────────────────────────────────
# NOTE: Do NOT import streamlit here — it causes a circular import crash.
# Streamlit Cloud auto-exports Secrets as env vars, so os.getenv() works.
groq_api_key = os.getenv("GROQ_API_KEY")

# llama-3.3-70b-versatile: 70 B parameters — significantly more accurate than
# the 8 B instant model for nuanced compliance reasoning (legal clauses, SLA
# percentages, PII detection). Groq free tier: 6 000 TPM.
llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.0, api_key=groq_api_key)


# ── 3. Helpers ────────────────────────────────────────────────────────────────
def _parse_rules(text: str) -> List[str]:
    rules = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        cleaned = re.sub(r"^\d+[\.)\\-]\s*", "", line)
        if cleaned:
            rules.append(cleaned)
    return rules


_STATUS_WEIGHT = {"COMPLIANT": 1.0, "PARTIAL": 0.5, "NON-COMPLIANT": 0.0}

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
    """NON-COMPLIANT if any detection-type rule is violated, else threshold-based."""
    if any(r["status"] == "NON-COMPLIANT" and r.get("rule_type") == "detection"
           for r in rule_results):
        return "NON-COMPLIANT"
    if score >= 80:
        return "COMPLIANT"
    if score >= 50:
        return "PARTIAL"
    return "NON-COMPLIANT"


def _compute_score(status: str) -> float:
    """Purely status-based: COMPLIANT=100, PARTIAL=50, NON-COMPLIANT=0."""
    return round(_STATUS_WEIGHT.get(status, 0.0) * 100, 2)


# ── 4. Prompt (per-rule context from FAISS) ───────────────────────────────────
def _build_prompt() -> PromptTemplate:
    return PromptTemplate.from_template(
        "You are a senior compliance officer performing a formal document audit.\n"
        "For EACH rule below, the most relevant document excerpts have been retrieved "
        "using semantic search. Evaluate each rule using ONLY its provided excerpts.\n"
        "Respond ONLY with a valid JSON array — no prose, no markdown fences.\n\n"
        "{rules_with_contexts}\n\n"
        "EVALUATION INSTRUCTIONS:\n"
        "  COMPLIANT     — The excerpts fully satisfy this rule.\n"
        "  PARTIAL       — The excerpts partially satisfy this rule.\n"
        "  NON-COMPLIANT — The rule is not satisfied at all in the excerpts.\n\n"
        "CRITICAL LOGIC:\n"
        "  • 'Must contain / must define / must state / must specify' rules:\n"
        "    → COMPLIANT  if the required content is clearly present in the excerpts.\n"
        "    → NON-COMPLIANT if completely absent.\n"
        "  • 'Must NOT contain / No X / Flag if X found' rules:\n"
        "    → COMPLIANT  if X is NOT found (absence = good).\n"
        "    → NON-COMPLIANT if X IS found.\n"
        "  • SLA / legal: look for explicit clauses, percentages, timeframes, legal terms.\n"
        "  • PII: flag only clearly and explicitly present personal data.\n"
        "  • Encoding: flag only garbled bytes or non-Latin scripts — not symbols like +,-,@.\n"
        "  • Do NOT invent violations. Judge only from what the excerpts show.\n\n"
        "OUTPUT FORMAT — one JSON object per rule, in the SAME order as listed:\n"
        '[{{"rule":"<exact rule text>","status":"<COMPLIANT|PARTIAL|NON-COMPLIANT>",'
        '"explanation":"<one concise sentence citing the evidence or its absence>",'
        '"llm_confidence":<0-100>}}]'
    )


# ── 5. JSON helpers ───────────────────────────────────────────────────────────
def _extract_json_array(text: str) -> list:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return [result]
    except json.JSONDecodeError:
        pass

    s, e = text.find("["), text.rfind("]")
    if s != -1 and e > s:
        try:
            result = json.loads(text[s:e+1])
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    objects = []
    for m in re.finditer(r'\{[^{}]*\}', text):
        try:
            objects.append(json.loads(m.group()))
        except json.JSONDecodeError:
            continue
    if objects:
        return objects

    raise json.JSONDecodeError("No valid JSON array found", text, 0)


def _normalize_result(r: dict, rule: str) -> Dict[str, Any]:
    r.setdefault("rule", rule)
    r.setdefault("status", "NON-COMPLIANT")
    r.setdefault("explanation", "No explanation provided.")
    r.setdefault("llm_confidence", 50)
    r["status"] = r["status"].upper().strip()
    if r["status"] not in _STATUS_WEIGHT:
        r["status"] = "NON-COMPLIANT"
    r["compliance_score"] = _compute_score(r["status"])
    return r


# ── 6. LLM call with per-rule FAISS contexts ──────────────────────────────────
def _call_llm(rules: List[str], rules_with_contexts: str) -> List[Dict[str, Any]]:
    """Single LLM call with FAISS-retrieved per-rule document excerpts."""
    prompt = _build_prompt()
    raw = (prompt | llm).invoke({"rules_with_contexts": rules_with_contexts}).content.strip()

    try:
        results = _extract_json_array(raw)
        normalized = []
        for i, rule in enumerate(rules):
            if i < len(results):
                normalized.append(_normalize_result(results[i], rule))
            else:
                normalized.append({
                    "rule": rule, "status": "NON-COMPLIANT",
                    "explanation": "LLM did not return a result for this rule.",
                    "llm_confidence": 0, "compliance_score": 0.0,
                })
        return normalized
    except json.JSONDecodeError:
        return [{
            "rule": rule, "status": "NON-COMPLIANT",
            "explanation": f"Parse error — raw response: {raw[:120]}",
            "llm_confidence": 0, "compliance_score": 0.0,
        } for rule in rules]


# ── 7. Main pipeline node ─────────────────────────────────────────────────────
def check_compliance(state: PipelineState) -> dict:
    """
    Full RAG pipeline:
      1. Extract full document text (already done upstream by pdf_processor).
      2. Chunk text into 250-word overlapping segments.
      3. Build a FAISS index (TF-IDF, no torch) over all chunks.
      4. For each compliance rule, retrieve the top-3 most relevant chunks.
      5. Send ALL rules with their per-rule excerpts in ONE LLM call.
      6. Aggregate scores → final verdict.
    """
    from pdf_processor import chunk_text
    from rag_utils import FAISSRetriever

    rules      = _parse_rules(state["compliance_rules"])
    full_text  = state.get("document_text", "")
    pages_text = state.get("pages_text", [])

    # ── Chunk the entire document (no truncation) ─────────────────────────────
    # chunk_size=250 words × ~1.3 tokens/word ≈ 325 tokens per chunk
    # top_k=3 chunks per rule × 5 rules = 15 chunks × 325 ≈ 4,875 context tokens
    # + prompt overhead (~400) + response (~500) ≈ 5,775 tokens — within 6k TPM
    chunks = chunk_text(full_text, chunk_size=250, overlap=40)
    if not chunks:
        chunks = [full_text[:8000]] if full_text else ["(empty document)"]

    # ── Build FAISS index ─────────────────────────────────────────────────────
    retriever = FAISSRetriever(chunks)

    # ── Per-rule context retrieval ────────────────────────────────────────────
    rules_with_contexts = ""
    for i, rule in enumerate(rules, 1):
        excerpts = retriever.query(rule, top_k=3)
        excerpts_text = "\n\n".join(f"[Excerpt {j+1}]: {e}" for j, e in enumerate(excerpts))
        rules_with_contexts += (
            f"\n---\nRule {i}: {rule}\n"
            f"Relevant Document Excerpts:\n{excerpts_text}\n"
        )

    # ── Single LLM call ───────────────────────────────────────────────────────
    raw_results = _call_llm(rules, rules_with_contexts)

    # ── Build structured rule_results ─────────────────────────────────────────
    rule_results: List[Dict[str, Any]] = []
    for i, rule in enumerate(rules):
        r         = raw_results[i] if i < len(raw_results) else {}
        status    = r.get("status", "NON-COMPLIANT")
        conf      = int(r.get("llm_confidence", 0))
        score     = r.get("compliance_score", 0.0)
        exp       = r.get("explanation", "")
        rule_type = "presence" if _is_presence_rule(rule) else "detection"

        rule_results.append({
            "rule":             rule,
            "status":           status,
            "explanation":      exp,
            "llm_confidence":   conf,
            "compliance_score": score,
            "rule_type":        rule_type,
        })

    # ── Final score & status ──────────────────────────────────────────────────
    final_score    = round(sum(r["compliance_score"] for r in rule_results)
                           / max(len(rule_results), 1), 2)
    overall_status = _determine_overall_status(final_score, rule_results)

    n_c  = sum(1 for r in rule_results if r["status"] == "COMPLIANT")
    n_p  = sum(1 for r in rule_results if r["status"] == "PARTIAL")
    n_nc = sum(1 for r in rule_results if r["status"] == "NON-COMPLIANT")

    # ── Text report ───────────────────────────────────────────────────────────
    lines = [
        "## Compliance Analysis Report\n",
        f"**Overall Status:** {overall_status}",
        f"**Final Compliance Score:** {final_score}/100\n",
        "---", "### Rule Results\n",
    ]
    for i, r in enumerate(rule_results, 1):
        emoji = {"COMPLIANT": "✅", "PARTIAL": "⚠️", "NON-COMPLIANT": "❌"}.get(r["status"], "❓")
        lines.append(
            f"**Rule {i}:** {r['rule']}\n"
            f"- {emoji} {r['status']} | Score: {r['compliance_score']}/100 "
            f"| Confidence: {r['llm_confidence']}%\n"
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
        "page_results":     [],
        "pages_text":       pages_text,
    }


# ── 8. LangGraph pipeline ─────────────────────────────────────────────────────
workflow = StateGraph(PipelineState)
workflow.add_node("analyze_compliance", check_compliance)
workflow.set_entry_point("analyze_compliance")
workflow.add_edge("analyze_compliance", END)
compliance_pipeline = workflow.compile()
