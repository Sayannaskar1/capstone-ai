import json
import re
from typing import TypedDict, List, Dict, Any, Tuple

from langchain_community.chat_models import ChatOllama
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, END

from rag_utils import RAGRetriever, get_embedding_model


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


# ── 2. LLM (reduced num_predict for speed) ────────────────────────────────────
llm = ChatOllama(model="llama3", temperature=0.1, num_predict=256, num_ctx=1024)


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
    return round(_STATUS_WEIGHT.get(status, 0.0) * confidence, 2)


# ── BATCHED prompt: evaluate ALL rules in ONE call ─────────────────────────────
def _build_batch_prompt() -> PromptTemplate:
    return PromptTemplate.from_template(
        "You are a precise compliance officer. Evaluate the document text "
        "below against ALL the given rules. Respond ONLY with a valid JSON array.\n\n"
        "Rules to evaluate:\n{rules_text}\n\n"
        "Document Text:\n{context}\n\n"
        "Instructions:\n"
        "- For EACH rule, produce one JSON object in the array.\n"
        "- status: COMPLIANT / PARTIAL / NON-COMPLIANT\n"
        "  * COMPLIANT     = rule fully satisfied anywhere in the document\n"
        "  * PARTIAL       = rule partially addressed but incomplete\n"
        "  * NON-COMPLIANT = rule violated or requirement absent\n"
        "- llm_confidence: 0-100\n"
        "- Be literal. Do NOT invent violations not in the text.\n"
        "- For encoding/UTF-8: +,-,@,digits,phone formats are valid UTF-8. "
        "  Only flag actual garbled bytes or foreign-language paragraph scripts.\n"
        "- For PII rules: flag only data clearly and explicitly present.\n"
        "- explanation: one crisp sentence.\n\n"
        "Respond with ONLY this JSON array (one object per rule, same order):\n"
        '[{{"rule":"<rule text>","status":"<COMPLIANT|PARTIAL|NON-COMPLIANT>",'
        '"explanation":"<one sentence>","llm_confidence":<0-100>}}]'
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

    # ── Fast context sampling: beginning + middle + end (no RAG overhead) ──
    text_len = len(full_text)
    sample_size = 500
    beginning = full_text[:sample_size]
    middle = full_text[text_len // 2 : text_len // 2 + sample_size] if text_len > sample_size * 2 else ""
    end = full_text[-sample_size:] if text_len > sample_size else ""
    context = f"{beginning}\n...\n{middle}\n...\n{end}".strip()

    # ── Single batched LLM call for ALL rules ────────────────────────────────
    raw_results = _call_llm_batch(rules, context)

    # ── Build rule_results with page citations ───────────────────────────────
    def _find_pages_with_evidence(rule: str, status: str) -> List[int]:
        """Quick keyword scan to find pages where relevant content lives."""
        if not pages_text:
            return []
        keywords = [w.lower() for w in re.findall(r'\b\w{5,}\b', rule)
                    if w.lower() not in {"shall", "must", "should", "document",
                                         "contains", "contain", "following", "report",
                                         "compliant", "present", "found"}][:6]
        evidence_pages = []
        for pg_num, pg_text in pages_text:
            pg_lower = pg_text.lower()
            if sum(1 for kw in keywords if kw in pg_lower) >= max(1, len(keywords) // 3):
                evidence_pages.append(pg_num)
        return evidence_pages

    rule_results: List[Dict[str, Any]] = []
    for i, rule in enumerate(rules):
        r         = raw_results[i] if i < len(raw_results) else {}
        status    = r.get("status", "NON-COMPLIANT")
        conf      = int(r.get("llm_confidence", 0))
        score     = r.get("compliance_score", 0.0)
        exp       = r.get("explanation", "")
        is_pres   = _is_presence_rule(rule)
        rule_type = "presence" if is_pres else "detection"

        # Page citation — text scan only, no LLM
        evidence_pages = _find_pages_with_evidence(rule, status)

        if status == "COMPLIANT" and evidence_pages:
            summary = f"Satisfied (page {evidence_pages}): {exp}"
        elif status == "NON-COMPLIANT" and evidence_pages:
            summary = f"Violation found (page {evidence_pages}): {exp}"
        else:
            summary = exp

        rule_results.append({
            "rule":             rule,
            "status":           status,
            "explanation":      summary,
            "llm_confidence":   conf,
            "compliance_score": score,
            "rule_type":        rule_type,
            "evidence_pages":   evidence_pages,
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
