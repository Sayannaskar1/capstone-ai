# --- NEW CODE START ---
"""
test_pipeline.py
Standalone test module for the enhanced compliance pipeline.
Run with: python test_pipeline.py

No PDF upload or Streamlit required — uses a small dummy text.
"""

import json
import sys
import os

# Ensure the project root is on the path when running from any directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pdf_processor import chunk_text
from rag_utils import RAGRetriever
from workflow import compliance_pipeline, _parse_rules, _determine_overall_status


# ─── Dummy document ───────────────────────────────────────────────────────────
DUMMY_TEXT = """
SERVICE AGREEMENT

This Service Agreement ("Agreement") is entered into as of January 1, 2024,
between Acme Corp ("Provider") and Beta Ltd ("Client").

1. CONFIDENTIALITY
Both parties agree to keep all proprietary information strictly confidential.
Neither party shall disclose any confidential data to third parties without
prior written consent. This confidentiality obligation survives the termination
of this Agreement for a period of five (5) years.

2. INDEMNITY
The Provider shall indemnify, defend, and hold harmless the Client from and
against any claims, liabilities, damages, and expenses (including reasonable
attorney fees) arising out of the Provider's negligence or wilful misconduct.

3. GOVERNING LAW
This Agreement shall be governed by and construed in accordance with the laws
of the State of California, without regard to its conflict-of-law principles.
Any disputes shall be resolved exclusively in the state or federal courts
located in San Francisco County, California.

4. PAYMENT TERMS
Invoices are due within 30 days of issuance. Late payments attract a 1.5%
monthly interest charge.
"""

# ─── Sample compliance rules ──────────────────────────────────────────────────
SAMPLE_RULES = """1. Document must contain a 'Confidentiality' clause.
2. The term 'Indemnity' must be clearly defined.
3. Applicable governing law must be stated."""


def test_chunking():
    """Test that chunking produces non-empty, reasonably sized chunks."""
    print("\n[TEST] Chunking ...")
    chunks = chunk_text(DUMMY_TEXT, chunk_size=100, overlap=20)
    assert len(chunks) >= 1, "Expected at least one chunk"
    for c in chunks:
        assert isinstance(c, str) and len(c) > 0, "Chunk must be a non-empty string"
    print(f"  ✅ Produced {len(chunks)} chunk(s). First chunk preview: {chunks[0][:80]}...")


def test_rag_retrieval():
    """Test that the RAG retriever returns relevant chunks."""
    print("\n[TEST] RAG Retrieval ...")
    chunks = chunk_text(DUMMY_TEXT, chunk_size=100, overlap=20)
    retriever = RAGRetriever(chunks)
    results = retriever.get_relevant_chunks("confidentiality clause", top_k=2)
    assert len(results) >= 1, "Expected at least one retrieved chunk"
    print(f"  ✅ Retrieved {len(results)} chunk(s) for query 'confidentiality clause'.")
    for i, r in enumerate(results, 1):
        print(f"     Chunk {i}: {r[:100]}...")


def test_rule_parsing():
    """Test that rules are correctly split into individual items."""
    print("\n[TEST] Rule Parsing ...")
    rules = _parse_rules(SAMPLE_RULES)
    assert len(rules) == 3, f"Expected 3 rules, got {len(rules)}"
    print(f"  ✅ Parsed {len(rules)} rules:")
    for r in rules:
        print(f"     - {r}")


def test_scoring_thresholds():
    """Test the overall status thresholds."""
    print("\n[TEST] Scoring Thresholds ...")
    assert _determine_overall_status(85) == "COMPLIANT"
    assert _determine_overall_status(65) == "PARTIAL"
    assert _determine_overall_status(40) == "NON-COMPLIANT"
    print("  ✅ Thresholds: 85→COMPLIANT, 65→PARTIAL, 40→NON-COMPLIANT")


def test_pipeline():
    """
    End-to-end pipeline test using dummy text and sample rules.
    Prints rule-wise results and final score without requiring a PDF.
    """
    print("\n" + "=" * 60)
    print("  END-TO-END PIPELINE TEST")
    print("=" * 60)

    initial_state = {
        "document_text": DUMMY_TEXT,
        "compliance_rules": SAMPLE_RULES,
        "analysis_report": "",
        "rule_results": [],
        "final_score": 0.0,
        "overall_status": "",
    }

    result = compliance_pipeline.invoke(initial_state)

    print("\n📋 Rule-wise Results:")
    for idx, r in enumerate(result["rule_results"], 1):
        print(f"\n  Rule {idx}: {r['rule']}")
        print(f"    Status            : {r['status']}")
        print(f"    Compliance Score  : {r['compliance_score']}/100")
        print(f"    LLM Confidence    : {r['llm_confidence']}/100")
        print(f"    Explanation       : {r['explanation']}")

    print("\n" + "-" * 60)
    print(f"  Final Compliance Score : {result['final_score']}/100")
    print(f"  Overall Status         : {result['overall_status']}")
    print("-" * 60)

    # Basic assertions
    assert "rule_results" in result and len(result["rule_results"]) == 3
    assert 0 <= result["final_score"] <= 100
    assert result["overall_status"] in ("COMPLIANT", "PARTIAL", "NON-COMPLIANT")
    print("\n✅ All pipeline assertions passed.\n")


if __name__ == "__main__":
    test_chunking()
    test_rag_retrieval()
    test_rule_parsing()
    test_scoring_thresholds()
    test_pipeline()
    print("🎉 All tests completed successfully.")
# --- NEW CODE END ---
