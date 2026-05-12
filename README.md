# 🚀 AI-Accelerated Compliance Pipeline — Enhanced Edition

## What's New (v2)

| Feature | Details |
|---|---|
| **RAG** | Document is chunked → embedded with `all-MiniLM-L6-v2` → stored in FAISS. Each rule retrieves only the top-3 relevant chunks before calling the LLM. |
| **Rule-wise processing** | Rules are split individually; the LLM is called once per rule. |
| **Compliance scoring** | Each rule returns `confidence_score (0–100)`. Final score is the average; status bands: ≥80 COMPLIANT, 50–79 PARTIAL, <50 NON-COMPLIANT. |
| **Structured JSON output** | The LLM is prompted to return strict JSON for every rule. |
| **Testing support** | `test_pipeline.py` runs end-to-end with dummy text — no PDF needed. |

---

## File Changes Summary

```
capstone-2-enhanced/
├── app.py              # MODIFIED  – added score badge display
├── pdf_processor.py    # MODIFIED  – added chunk_text() helper
├── workflow.py         # MODIFIED  – RAG + rule loop + scoring + structured output
├── rag_utils.py        # NEW       – SentenceTransformer + FAISS retriever class
├── test_pipeline.py    # NEW       – unit + end-to-end tests (no PDF required)
└── requirements.txt    # MODIFIED  – added sentence-transformers, faiss-cpu, numpy
```

---

## Installation

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Pull the Ollama model (run once)
ollama pull llama3
```

### New packages to install

| Package | Why |
|---|---|
| `sentence-transformers>=2.7.0` | Generates text embeddings using `all-MiniLM-L6-v2` |
| `faiss-cpu>=1.8.0` | Fast vector similarity search (CPU version) |
| `numpy>=1.24.0` | Required by both of the above |

> **GPU note:** If you have a CUDA GPU, replace `faiss-cpu` with `faiss-gpu` for faster indexing.

---

## Running the App

```bash
streamlit run app.py
```

---

## Running Tests

```bash
python test_pipeline.py
```

No PDF, no Streamlit, no browser — runs fully from the terminal.

---

## How It Works (v2 flow)

```
PDF upload
    │
    ▼
extract_text_from_pdf()          # pdf_processor.py (unchanged)
    │
    ▼
chunk_text()                     # pdf_processor.py (NEW)
    │
    ▼
RAGRetriever.build_index()       # rag_utils.py (NEW) — FAISS index
    │
    ├─ for each rule:
    │       │
    │       ▼
    │   get_relevant_chunks()    # top-3 chunks via cosine similarity
    │       │
    │       ▼
    │   LLM (Ollama llama3)      # returns strict JSON per rule
    │       │
    │       ▼
    │   { rule, status, explanation, confidence_score }
    │
    ▼
Aggregate → final_score, overall_status
    │
    ▼
Structured report → Streamlit UI / download
```

---

## Output Format

Each rule produces:
```json
{
  "rule": "Document must contain a 'Confidentiality' clause.",
  "status": "COMPLIANT",
  "explanation": "The document contains a dedicated Confidentiality section...",
  "confidence_score": 92
}
```

Final report includes:
- Rule-wise status + score + explanation
- Overall compliance score (0–100)
- Overall status: COMPLIANT / PARTIAL / NON-COMPLIANT
- Summary counts
