"""
eval_suite.py
─────────────────────────────────────────────────────────────────────────────
ComplianceAI — Automated LLM Evaluation Suite
Industry practice: Golden-Set / Ground-Truth Testing

HOW IT WORKS
  Each test case is a "golden sample": a short document text where YOU already
  know the correct answer (expected_status per rule, expected_overall_status).
  The pipeline runs against it, and we compare actual vs expected.

  This is the same approach used by:
    • OpenAI Evals framework
    • DeepEval (LLM evaluation library)
    • RAGAS (RAG evaluation)
    • MLflow model validation
  … all boil down to: known-input → known-expected-output → measure match rate.

METRICS PRODUCED
  Per-rule  : Accuracy, Precision, Recall, F1 per label (COMPLIANT/PARTIAL/NON-COMPLIANT)
  Per-test  : Pass / Fail / Score delta from expected
  Overall   : Exact-match accuracy, mean score error, hallucination rate, consistency

RUN
  python eval_suite.py                  # full suite, prints report
  python eval_suite.py --verbose        # also prints LLM explanations
  python eval_suite.py --json           # machine-readable JSON output
  python eval_suite.py --case TC01      # run a single test case
─────────────────────────────────────────────────────────────────────────────
"""

import sys, os, json, time, argparse
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from workflow import compliance_pipeline, _parse_rules, _determine_overall_status


# ══════════════════════════════════════════════════════════════════════════════
#  1.  GOLDEN TEST CASES  — ground-truth dataset
#      Each case: document text + rules + what the CORRECT answer must be.
#      Rule order in `expected_per_rule` must match rule order in `rules`.
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class RuleExpectation:
    rule: str
    expected_status: str          # "COMPLIANT" | "PARTIAL" | "NON-COMPLIANT"
    rationale: str                # WHY this is the correct answer


@dataclass
class TestCase:
    id: str
    name: str
    document_text: str
    rules: str                    # newline-separated, same format as UI
    expected_per_rule: List[RuleExpectation]
    expected_overall_status: str
    category: str                 # "presence" | "detection" | "scoring" | "edge"


GOLDEN_CASES: List[TestCase] = [

    # ── TC01: Full legal contract — all rules present ──────────────────────
    TestCase(
        id="TC01",
        name="Complete Legal Contract — All Rules Present",
        category="presence",
        document_text="""
        SERVICE AGREEMENT

        This Service Agreement is entered into on January 1, 2024, between
        Acme Corp ("Provider") and Beta Ltd ("Client").

        1. CONFIDENTIALITY
        Both parties shall keep all proprietary information strictly confidential.
        Neither party may disclose confidential data to third parties without
        prior written consent. This obligation survives termination for 5 years.

        2. INDEMNITY
        The Provider shall indemnify and hold harmless the Client against any
        claims, liabilities, and expenses arising from Provider's negligence.

        3. GOVERNING LAW
        This Agreement is governed by the laws of the State of California.
        Disputes shall be resolved in San Francisco County courts.

        4. TERMINATION
        Either party may terminate with 30 days written notice.
        """,
        rules="""1. Document must contain a clearly defined Confidentiality clause.
2. The term Indemnity must be clearly defined with scope.
3. Applicable governing law and jurisdiction must be explicitly stated.
4. Termination conditions and notice period must be specified.""",
        expected_per_rule=[
            RuleExpectation("Document must contain a clearly defined Confidentiality clause.",
                            "COMPLIANT",
                            "Section 1 explicitly defines a confidentiality clause with a 5-year survival."),
            RuleExpectation("The term Indemnity must be clearly defined with scope.",
                            "COMPLIANT",
                            "Section 2 explicitly names Indemnity and defines scope."),
            RuleExpectation("Applicable governing law and jurisdiction must be explicitly stated.",
                            "COMPLIANT",
                            "Section 3 names California law and San Francisco jurisdiction."),
            RuleExpectation("Termination conditions and notice period must be specified.",
                            "COMPLIANT",
                            "Section 4 states 30 days written notice."),
        ],
        expected_overall_status="COMPLIANT",
    ),

    # ── TC02: PII detection — document CONTAINS PII ────────────────────────
    TestCase(
        id="TC02",
        name="PII Detection — PII Present in Document",
        category="detection",
        document_text="""
        EMPLOYEE ONBOARDING RECORD

        Name: John Smith
        Email: john.smith@company.com
        Phone: +1-555-867-5309
        SSN: 123-45-6789
        Date of Birth: 15 March 1990
        Home Address: 42 Elm Street, Springfield, IL 62701

        This employee has been onboarded to the Engineering team as of 2024-01-15.
        """,
        rules="""1. If text content contains PII/personal information (email, phone, SSN etc.)
2. Document must not contain employee home addresses.
3. Encoding consistency UTF-8 across text (only English supported).""",
        expected_per_rule=[
            RuleExpectation("If text content contains PII/personal information (email, phone, SSN etc.)",
                            "NON-COMPLIANT",
                            "Email, phone, SSN, and DOB all explicitly present."),
            RuleExpectation("Document must not contain employee home addresses.",
                            "NON-COMPLIANT",
                            "Full home address on line 6."),
            RuleExpectation("Encoding consistency UTF-8 across text (only English supported)",
                            "COMPLIANT",
                            "All text is plain ASCII/English, no garbled bytes."),
        ],
        expected_overall_status="NON-COMPLIANT",
    ),

    # ── TC03: Clean document — no PII, no violations ───────────────────────
    TestCase(
        id="TC03",
        name="Clean Privacy Document — No PII",
        category="detection",
        document_text="""
        INTERNAL POLICY DOCUMENT v2.1

        This document describes the company's data handling policy.
        All customer records are stored in anonymised form.
        Access is restricted to authorised personnel only.
        No personal identifiers are retained after the 30-day processing window.

        Compliance with GDPR Article 5 is mandatory for all teams.
        """,
        rules="""1. If text content contains PII/personal information (email, phone etc.)
2. No abusive or unlawful language in document.
3. Document must not disclose confidential company financials.""",
        expected_per_rule=[
            RuleExpectation("If text content contains PII/personal information (email, phone etc.)",
                            "COMPLIANT",
                            "No emails, phones, names, or identifiers present."),
            RuleExpectation("No abusive or unlawful language in document.",
                            "COMPLIANT",
                            "Document is professional with no abusive content."),
            RuleExpectation("Document must not disclose confidential company financials.",
                            "COMPLIANT",
                            "No financial figures or proprietary data present."),
        ],
        expected_overall_status="COMPLIANT",
    ),

    # ── TC04: SLA document — all SLA clauses present ───────────────────────
    TestCase(
        id="TC04",
        name="SLA Contract — All SLA Terms Present",
        category="presence",
        document_text="""
        SERVICE LEVEL AGREEMENT

        1. UPTIME GUARANTEE
        The Provider guarantees 99.9% uptime measured monthly, excluding
        scheduled maintenance windows announced 48 hours in advance.

        2. INCIDENT RESPONSE
        Critical incidents (P1) must be acknowledged within 15 minutes and
        resolved within 4 hours. P2 incidents within 2 business days.

        3. PENALTY CLAUSE
        For every hour of downtime exceeding the SLA, the Client receives
        a service credit of 5% of the monthly fee, capped at 30%.

        4. REPORTING
        Uptime metrics are reported monthly via the customer portal dashboard.
        """,
        rules="""1. Uptime or availability SLA percentage must be explicitly defined.
2. Incident response and resolution time targets must be specified.
3. Penalty or credit clauses for SLA breach must be present.
4. Measurement methodology and reporting frequency must be stated.""",
        expected_per_rule=[
            RuleExpectation("Uptime or availability SLA percentage must be explicitly defined.",
                            "COMPLIANT",
                            "99.9% uptime explicitly stated in Section 1."),
            RuleExpectation("Incident response and resolution time targets must be specified.",
                            "COMPLIANT",
                            "P1: 15 min acknowledgement / 4 hr resolution; P2: 2 days."),
            RuleExpectation("Penalty or credit clauses for SLA breach must be present.",
                            "COMPLIANT",
                            "5% credit per hour, capped at 30% explicitly stated."),
            RuleExpectation("Measurement methodology and reporting frequency must be stated.",
                            "COMPLIANT",
                            "Monthly reporting via customer portal stated in Section 4."),
        ],
        expected_overall_status="COMPLIANT",
    ),

    # ── TC05: Incomplete contract — some clauses missing ───────────────────
    TestCase(
        id="TC05",
        name="Incomplete Contract — Missing Key Clauses",
        category="presence",
        document_text="""
        VENDOR AGREEMENT

        This agreement is between XYZ Pvt Ltd ("Vendor") and Client Corp.

        1. PAYMENT
        Payment is due within 45 days of invoice date.

        2. SCOPE OF WORK
        The vendor will provide software development services as described
        in the attached Statement of Work.

        Signed on behalf of both parties.
        """,
        rules="""1. Document must contain a clearly defined Confidentiality clause.
2. Termination conditions and notice period must be specified.
3. Applicable governing law and jurisdiction must be explicitly stated.
4. Dispute resolution mechanism must be stated.""",
        expected_per_rule=[
            RuleExpectation("Document must contain a clearly defined Confidentiality clause.",
                            "NON-COMPLIANT",
                            "No confidentiality clause anywhere in document."),
            RuleExpectation("Termination conditions and notice period must be specified.",
                            "NON-COMPLIANT",
                            "No termination clause present."),
            RuleExpectation("Applicable governing law and jurisdiction must be explicitly stated.",
                            "NON-COMPLIANT",
                            "No governing law mentioned."),
            RuleExpectation("Dispute resolution mechanism must be stated.",
                            "NON-COMPLIANT",
                            "No arbitration or litigation clause present."),
        ],
        expected_overall_status="NON-COMPLIANT",
    ),

    # ── TC06: Edge case — empty-ish document ───────────────────────────────
    TestCase(
        id="TC06",
        name="Edge Case — Near-Empty Document",
        category="edge",
        document_text="""
        DRAFT

        This document is a placeholder. Content will be added later.
        """,
        rules="""1. Document must contain a clearly defined Confidentiality clause.
2. If text content contains PII/personal information (email, phone etc.)""",
        expected_per_rule=[
            RuleExpectation("Document must contain a clearly defined Confidentiality clause.",
                            "NON-COMPLIANT",
                            "Document has no substantive content."),
            RuleExpectation("If text content contains PII/personal information (email, phone etc.)",
                            "COMPLIANT",
                            "No PII in placeholder text."),
        ],
        expected_overall_status="NON-COMPLIANT",
    ),

    # ── TC07: Consistency check — same document, same rules, run 3× ───────
    # (handled separately by run_consistency_test below)
]


# ══════════════════════════════════════════════════════════════════════════════
#  2.  RESULT DATACLASSES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class RuleResult:
    rule: str
    expected_status: str
    actual_status: str
    match: bool
    compliance_score: float
    llm_confidence: int
    explanation: str


@dataclass
class CaseResult:
    case_id: str
    case_name: str
    category: str
    expected_overall: str
    actual_overall: str
    overall_match: bool
    rule_results: List[RuleResult]
    rule_accuracy: float          # fraction of rules correctly classified
    latency_sec: float
    error: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
#  3.  RUNNER
# ══════════════════════════════════════════════════════════════════════════════

def run_case(tc: TestCase, verbose: bool = False) -> CaseResult:
    """Invoke the real pipeline on a golden test case and compare to ground truth."""
    initial_state = {
        "document_text":    tc.document_text,
        "compliance_rules": tc.rules,
        "analysis_report":  "",
        "rule_results":     [],
        "final_score":      0.0,
        "overall_status":   "",
        "pages_text":       [],
        "page_results":     [],
    }

    t0 = time.perf_counter()
    try:
        result = compliance_pipeline.invoke(initial_state)
    except Exception as e:
        latency = time.perf_counter() - t0
        return CaseResult(
            case_id=tc.id, case_name=tc.name, category=tc.category,
            expected_overall=tc.expected_overall_status, actual_overall="ERROR",
            overall_match=False, rule_results=[], rule_accuracy=0.0,
            latency_sec=latency, error=str(e),
        )
    latency = time.perf_counter() - t0

    actual_rules = result.get("rule_results", [])
    rule_results: List[RuleResult] = []
    matches = 0

    for i, exp in enumerate(tc.expected_per_rule):
        if i < len(actual_rules):
            act = actual_rules[i]
            actual_status = act.get("status", "NON-COMPLIANT")
            match = actual_status == exp.expected_status
            if match:
                matches += 1
            rule_results.append(RuleResult(
                rule=exp.rule,
                expected_status=exp.expected_status,
                actual_status=actual_status,
                match=match,
                compliance_score=act.get("compliance_score", 0.0),
                llm_confidence=act.get("llm_confidence", 0),
                explanation=act.get("explanation", ""),
            ))
        else:
            rule_results.append(RuleResult(
                rule=exp.rule, expected_status=exp.expected_status,
                actual_status="MISSING", match=False,
                compliance_score=0.0, llm_confidence=0,
                explanation="Pipeline returned no result for this rule.",
            ))

    rule_accuracy = matches / len(tc.expected_per_rule) if tc.expected_per_rule else 0.0
    actual_overall = result.get("overall_status", "")
    overall_match = actual_overall == tc.expected_overall_status

    return CaseResult(
        case_id=tc.id, case_name=tc.name, category=tc.category,
        expected_overall=tc.expected_overall_status,
        actual_overall=actual_overall,
        overall_match=overall_match,
        rule_results=rule_results,
        rule_accuracy=rule_accuracy,
        latency_sec=latency,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  4.  CONSISTENCY TEST  (same input → same output across N runs)
# ══════════════════════════════════════════════════════════════════════════════

def run_consistency_test(runs: int = 3, verbose: bool = False) -> Dict:
    """
    Runs TC01 (the complete legal contract) N times and checks whether
    the LLM gives the same verdict every time. This tests determinism.
    A good LLM system should be ≥90% consistent at temperature=0.
    """
    tc = GOLDEN_CASES[0]   # TC01 — complete legal contract
    print(f"\n{'─'*60}")
    print(f"  CONSISTENCY TEST — running TC01 × {runs}")
    print(f"{'─'*60}")

    statuses = []
    scores   = []
    for i in range(1, runs + 1):
        res = run_case(tc, verbose=verbose)
        statuses.append(res.actual_overall)
        if res.rule_results:
            avg_score = sum(r.compliance_score for r in res.rule_results) / len(res.rule_results)
            scores.append(avg_score)
        symbol = "✅" if res.overall_match else "❌"
        print(f"  Run {i}: {symbol} {res.actual_overall}  (latency: {res.latency_sec:.1f}s)")

    unique = set(statuses)
    consistency = (1 - (len(unique) - 1) / max(runs - 1, 1)) * 100  # simple consistency %
    score_variance = max(scores) - min(scores) if scores else 0

    print(f"\n  Unique verdicts    : {unique}")
    print(f"  Consistency rate   : {consistency:.0f}%")
    print(f"  Score range        : {min(scores):.1f} – {max(scores):.1f}  (variance: {score_variance:.1f})")
    ideal = "✅ GOOD" if len(unique) == 1 else ("⚠️  MINOR VARIANCE" if len(unique) == 2 else "❌ INCONSISTENT")
    print(f"  Assessment         : {ideal}")

    return {
        "runs": runs, "statuses": statuses, "scores": scores,
        "consistency_pct": consistency, "score_variance": score_variance,
        "assessment": ideal,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  5.  METRICS  (Precision / Recall / F1 per label)
# ══════════════════════════════════════════════════════════════════════════════

def compute_metrics(case_results: List[CaseResult]) -> Dict:
    """
    Compute per-label classification metrics across all rule evaluations.
    Labels: COMPLIANT, PARTIAL, NON-COMPLIANT
    """
    labels = ["COMPLIANT", "PARTIAL", "NON-COMPLIANT"]
    tp = {l: 0 for l in labels}
    fp = {l: 0 for l in labels}
    fn = {l: 0 for l in labels}

    all_rule_results = [rr for cr in case_results for rr in cr.rule_results]
    for rr in all_rule_results:
        exp = rr.expected_status
        act = rr.actual_status
        if act == exp:
            tp[exp] += 1
        else:
            if act in labels:
                fp[act] += 1
            if exp in labels:
                fn[exp] += 1

    metrics = {}
    for l in labels:
        prec = tp[l] / (tp[l] + fp[l]) if (tp[l] + fp[l]) > 0 else 0.0
        rec  = tp[l] / (tp[l] + fn[l]) if (tp[l] + fn[l]) > 0 else 0.0
        f1   = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        metrics[l] = {"precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3),
                       "tp": tp[l], "fp": fp[l], "fn": fn[l]}

    total_rules  = len(all_rule_results)
    correct_rules = sum(1 for rr in all_rule_results if rr.match)
    rule_accuracy = correct_rules / total_rules if total_rules else 0.0

    overall_correct = sum(1 for cr in case_results if cr.overall_match)
    overall_accuracy = overall_correct / len(case_results) if case_results else 0.0

    # Hallucination proxy: LLM said COMPLIANT but truth is NON-COMPLIANT
    false_compliant = sum(
        1 for rr in all_rule_results
        if rr.actual_status == "COMPLIANT" and rr.expected_status == "NON-COMPLIANT"
    )
    hallucination_rate = false_compliant / total_rules if total_rules else 0.0

    avg_latency = sum(cr.latency_sec for cr in case_results) / len(case_results) if case_results else 0.0
    avg_confidence = sum(rr.llm_confidence for rr in all_rule_results) / len(all_rule_results) if all_rule_results else 0.0

    return {
        "per_label":          metrics,
        "rule_accuracy":      round(rule_accuracy, 4),
        "overall_accuracy":   round(overall_accuracy, 4),
        "hallucination_rate": round(hallucination_rate, 4),
        "total_rules_evaluated": total_rules,
        "avg_latency_sec":    round(avg_latency, 2),
        "avg_llm_confidence": round(avg_confidence, 1),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  6.  REPORT PRINTER
# ══════════════════════════════════════════════════════════════════════════════

def _status_icon(match: bool) -> str:
    return "✅ PASS" if match else "❌ FAIL"


def print_report(case_results: List[CaseResult], metrics: Dict, verbose: bool = False):
    W = 70
    print("\n" + "═" * W)
    print("  ComplianceAI — LLM EVALUATION REPORT")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * W)

    for cr in case_results:
        icon = _status_icon(cr.overall_match)
        print(f"\n  [{cr.case_id}] {cr.case_name}")
        print(f"  Category : {cr.category}   |   Latency: {cr.latency_sec:.1f}s")
        if cr.error:
            print(f"  ❌ ERROR: {cr.error}")
            continue
        print(f"  Overall  : expected={cr.expected_overall}  actual={cr.actual_overall}  {icon}")
        print(f"  Rule accuracy: {cr.rule_accuracy*100:.0f}%  ({sum(r.match for r in cr.rule_results)}/{len(cr.rule_results)} rules correct)")
        if verbose:
            print()
            for i, rr in enumerate(cr.rule_results, 1):
                sym = "✅" if rr.match else "❌"
                print(f"    Rule {i}: {sym}  exp={rr.expected_status}  act={rr.actual_status}  conf={rr.llm_confidence}%")
                print(f"           {rr.rule[:80]}")
                print(f"           → {rr.explanation[:100]}")
        print(f"  {'─'*64}")

    print("\n" + "═" * W)
    print("  AGGREGATE METRICS")
    print("═" * W)
    print(f"  Overall (verdict) accuracy : {metrics['overall_accuracy']*100:.1f}%  "
          f"({sum(cr.overall_match for cr in case_results)}/{len(case_results)} test cases)")
    print(f"  Per-rule classification    : {metrics['rule_accuracy']*100:.1f}%  "
          f"({int(metrics['rule_accuracy']*metrics['total_rules_evaluated'])}/{metrics['total_rules_evaluated']} rules)")
    print(f"  Hallucination rate         : {metrics['hallucination_rate']*100:.1f}%  "
          f"(COMPLIANT given when truth is NON-COMPLIANT)")
    print(f"  Avg LLM confidence         : {metrics['avg_llm_confidence']:.1f}%")
    print(f"  Avg latency per case       : {metrics['avg_latency_sec']:.1f}s")

    print("\n  Per-Label Metrics (Precision / Recall / F1):")
    print(f"  {'Label':<18} {'Precision':>10} {'Recall':>10} {'F1':>10}")
    print(f"  {'─'*50}")
    for label, m in metrics["per_label"].items():
        print(f"  {label:<18} {m['precision']:>10.3f} {m['recall']:>10.3f} {m['f1']:>10.3f}")

    print("\n  INTERPRETATION GUIDE")
    print(f"  {'─'*64}")
    ha = metrics['hallucination_rate']
    ra = metrics['rule_accuracy']
    oa = metrics['overall_accuracy']
    print(f"  Rule accuracy {ra*100:.0f}%   → {'✅ Good (>80%)' if ra>=0.8 else '⚠️  Needs improvement (<80%)'}")
    print(f"  Overall accuracy {oa*100:.0f}% → {'✅ Good (>80%)' if oa>=0.8 else '⚠️  Needs improvement (<80%)'}")
    print(f"  Hallucination {ha*100:.1f}%   → {'✅ Low (<10%)' if ha<0.1 else '⚠️  High - model is too lenient'}")
    print("═" * W + "\n")


# ══════════════════════════════════════════════════════════════════════════════
#  7.  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="ComplianceAI LLM Evaluation Suite")
    parser.add_argument("--verbose",     action="store_true", help="Show per-rule LLM explanations")
    parser.add_argument("--json",        action="store_true", help="Also write results to eval_results.json")
    parser.add_argument("--case",        default=None,        help="Run only one case by ID (e.g. TC01)")
    parser.add_argument("--consistency", action="store_true", help="Run consistency test (3 runs of TC01)")
    parser.add_argument("--runs",        type=int, default=3, help="Number of runs for consistency test")
    args = parser.parse_args()

    cases_to_run = GOLDEN_CASES
    if args.case:
        cases_to_run = [tc for tc in GOLDEN_CASES if tc.id == args.case.upper()]
        if not cases_to_run:
            print(f"❌ No case found with id '{args.case}'. Available: {[tc.id for tc in GOLDEN_CASES]}")
            sys.exit(1)

    print(f"\n🛡️  ComplianceAI Evaluation Suite")
    print(f"   Running {len(cases_to_run)} golden test case(s)...\n")

    case_results = []
    for tc in cases_to_run:
        print(f"  ⏳  Running {tc.id}: {tc.name} ...", end="", flush=True)
        cr = run_case(tc, verbose=args.verbose)
        case_results.append(cr)
        icon = "✅" if cr.overall_match else "❌"
        print(f"  {icon}  ({cr.latency_sec:.1f}s)")

    metrics = compute_metrics(case_results)
    print_report(case_results, metrics, verbose=args.verbose)

    if args.consistency:
        run_consistency_test(runs=args.runs, verbose=args.verbose)

    if args.json:
        output = {
            "generated_at":  datetime.now().isoformat(),
            "metrics":       metrics,
            "cases":         [asdict(cr) for cr in case_results],
        }
        with open("eval_results.json", "w") as f:
            json.dump(output, f, indent=2)
        print(f"  📄 Results written to eval_results.json\n")


if __name__ == "__main__":
    main()
