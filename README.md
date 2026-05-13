# 🛡️ ComplianceAI — Enterprise PDF Compliance Scanner

> *An AI-powered, enterprise-grade SaaS application that automatically scans PDF documents for compliance violations, PII exposure, and policy issues using a local Large Language Model — all in under 10 seconds.*

---

## 📖 Table of Contents

1. [What is this project?](#what-is-this-project)
2. [Key Technologies Explained](#key-technologies-explained)
3. [System Architecture](#system-architecture)
4. [How the Complete Workflow Works](#how-the-complete-workflow-works)
5. [File-by-File Breakdown](#file-by-file-breakdown)
6. [Installation & Setup](#installation--setup)
7. [Running the Application](#running-the-application)
8. [How to Use the UI](#how-to-use-the-ui)
9. [Understanding the Compliance Score](#understanding-the-compliance-score)
10. [Performance Design Decisions](#performance-design-decisions)
11. [Dependencies Reference](#dependencies-reference)

---

## What is this project?

Imagine you are a legal or compliance officer at a company. Every week, dozens of PDF documents land on your desk — contracts, NDAs, HR policies, supplier agreements. You need to check each one against a list of rules:

- *"Does this contract have a confidentiality clause?"*
- *"Does this document expose any employee email addresses or phone numbers?"*
- *"Is there any abusive language?"*
- *"Is the text encoding valid UTF-8 with only English content?"*

Doing this manually is slow, expensive, and error-prone. **ComplianceAI automates this entirely.** You upload a PDF, click one button, and within seconds you get:

- A compliance score out of 100
- A verdict: COMPLIANT / PARTIAL / NON-COMPLIANT
- A breakdown of every rule — passed, failed, or partially met
- Visual charts showing the risk distribution
- A downloadable professional PDF report
- A history of all your previous scans

The entire analysis is powered by a **Cloud LLM API** (Llama 3 via Groq), making it lightning-fast and ready for cloud deployment.

---

## Key Technologies Explained

Before diving into how the project works, here is a plain-English explanation of every major technology used.

### 🐍 Python
The entire backend is written in Python 3.9+. Python is the dominant language for AI/ML development because of its extensive ecosystem of libraries for data processing, machine learning, and web development.

### 🌐 Streamlit
**Streamlit** is a Python library that lets you build interactive web applications using only Python code — no HTML, JavaScript, or CSS required (though you can inject custom CSS, which this project does extensively). When you run `streamlit run app.py`, it starts a local web server and renders the UI in your browser. Every time a user clicks a button or uploads a file, the entire Python script re-runs from top to bottom, and Streamlit updates only the parts of the UI that changed.

### 🚀 Groq + Llama 3
**Groq** is a cloud platform that runs Large Language Models (LLMs) on specialized hardware (LPUs) at blistering speeds.

**Llama 3** is a state-of-the-art open-source LLM created by Meta. In this project, Llama 3 acts as the compliance officer that reads document text and decides whether each compliance rule is satisfied.

### ⛓️ LangChain
**LangChain** is a framework that makes it easier to build applications powered by LLMs. Instead of manually formatting prompts and parsing LLM responses, LangChain provides clean abstractions. In this project we use two components:

- **`ChatGroq`** (from `langchain-groq`): A connector that lets Python talk to the Groq Cloud API.
- **`PromptTemplate`** (from `langchain-core`): A template system where you define a prompt with placeholders like `{rules_text}` and `{context}`, then fill them in at runtime.

The key pattern used is called **LCEL (LangChain Expression Language)**, written as `prompt | llm`. This is a "pipe" operator — the output of the prompt flows into the LLM, just like a Unix pipe.

### 🕸️ LangGraph
**LangGraph** is built on top of LangChain and lets you define AI workflows as **graphs** — a set of nodes (steps) connected by edges (transitions). Think of it like a flowchart that your AI follows.

In this project, the graph is simple: one node called `analyze_compliance` that does all the work, then connects to END. But LangGraph is designed for complex multi-step agents where the AI might loop back, make decisions, or call tools. Using LangGraph here provides a clean, extensible architecture that can grow.

The graph has a **typed state** (`PipelineState`) — a Python dictionary that carries all data between nodes: the document text, the rules, the results, and the final score. Every node receives this state and returns updates to it.

### 🔍 FAISS + Sentence Transformers (RAG)
**RAG** stands for *Retrieval-Augmented Generation*. The idea is simple: instead of feeding the entire document to the LLM (which would be too slow and exceed API limits), you:

1. **Split** the document into small chunks (e.g., 500-word pieces)
2. **Embed** each chunk — convert it into a list of numbers (a "vector") that captures its meaning
3. **Index** all these vectors in a fast database (FAISS)
4. When you have a question, **embed the question** and find the chunks with the most similar vectors
5. Feed only those relevant chunks to the LLM

> **Note on API Limits:** Groq Cloud's Free Tier enforces a strict **6,000 Tokens Per Minute (TPM)** limit. A standard 50-page PDF can easily exceed 50,000 tokens. Therefore, RAG (using FAISS) is absolutely mandatory to extract only the top ~4,000 tokens of relevant text so the app doesn't crash the API.

### 📊 Plotly
**Plotly** is a data visualization library that creates interactive, beautiful charts — gauges, radar charts, donut charts, bar charts. All charts in the Dashboard tab are rendered using Plotly.

### 📄 ReportLab
**ReportLab** is a Python library for programmatically generating PDF files. It gives complete control over layout, fonts, colors, and tables. The "Export" tab uses ReportLab to generate a professional, branded PDF compliance report.

### 🗄️ SQLite
**SQLite** is a lightweight, file-based database that requires no server installation. It stores everything in a single `.db` file (`scan_history.db`). This project uses it via Python's built-in `sqlite3` module to persist the scan history between sessions.

### 🖼️ PyMuPDF (fitz)
**PyMuPDF** (imported as `fitz`) is a high-performance library for reading PDF files. It extracts plain text from each page of a PDF extremely fast — far faster than alternatives like PyPDF2.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        BROWSER (localhost:8501)                     │
│  ┌─────────────────┐          ┌──────────────────────────────────┐  │
│  │    SIDEBAR       │          │         MAIN CONTENT AREA        │  │
│  │                  │          │                                  │  │
│  │  • File Upload   │  ──────► │  Landing Page / Scan Results     │  │
│  │  • Rules         │          │  ┌──────────────────────────┐   │  │
│  │  • Run Scan      │          │  │ 📈 Dashboard (Charts)    │   │  │
│  │  • History 📂    │          │  │ 🔍 Detailed Findings      │   │  │
│  └─────────────────┘          │  │ ⚙️  Rules Tab            │   │  │
│                                │  │ 📥 Export (PDF)           │   │  │
│                                │  └──────────────────────────┘   │  │
│                                └──────────────────────────────────┘  │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │ Python (Streamlit)
┌──────────────────────────────────▼──────────────────────────────────┐
│                          app.py (Controller)                        │
│                                                                     │
│  • Manages UI state (st.session_state)                              │
│  • Orchestrates all modules                                         │
│  • Runs pipeline in background thread                               │
└────┬──────────┬──────────┬──────────┬──────────────────────────────┘
     │          │          │          │
     ▼          ▼          ▼          ▼
pdf_        workflow.  storage.   report_
processor   py         py         generator.py
(Extract)   (AI)       (SQLite)   (PDF export)
     │          │
     │          ▼
     │      Groq Cloud API (Llama 3)
     │
     ▼
styles.py  (all CSS/theming)
```

---

## How the Complete Workflow Works

Here is the **exact step-by-step journey** of what happens when you click "🚀 Run Scan":

### Step 1: PDF Upload & Caching
The user selects a PDF from the sidebar file uploader. `app.py` reads the raw bytes of the file and computes an **MD5 hash** (a unique fingerprint) of the file content. This hash is used as a cache key — if you upload the same file twice, `pdf_processor.py` is only called once. The result is cached by Streamlit's `@st.cache_data` decorator.

### Step 2: Text Extraction (`pdf_processor.py`)
`extract_all()` opens the PDF using PyMuPDF exactly once and iterates through every page, collecting:
- The full concatenated text of all pages
- A list of `(page_number, page_text)` tuples for citation purposes
- The total page count and word count

### Step 3: Background Thread Launch (`app.py`)
The compliance pipeline is a **blocking operation** — it calls an LLM and waits for a response. If we ran it directly in the Streamlit main thread, the UI would freeze completely and the Stop button would not work.

To solve this, `app.py` uses Python's `concurrent.futures.ThreadPoolExecutor` to run the pipeline in a separate thread. The main thread enters a polling loop, calling `progress_box.caption()` every 0.3 seconds. This Streamlit API call is what enables the Stop button to work — when you click Stop, Streamlit raises a `StopException` the next time a Streamlit API call is made.

### Step 4: FAISS Vector Retrieval (`workflow.py` + `rag_utils.py`)
To ensure the LLM receives the most relevant information without exceeding Groq's 6,000-token Free Tier limit, the document is split into 500-word chunks. These chunks are embedded using `sentence-transformers` and indexed in FAISS. All compliance rules are combined into a single query to retrieve the top 6 most relevant chunks (~4000 tokens).

### Step 5: Batched LLM Call (`workflow.py`)
All compliance rules are sent to Llama 3 in a **single prompt**. This is the most important performance optimization. The prompt looks like this:

```
You are a precise compliance officer. Evaluate the document text
below against ALL the given rules. Respond ONLY with a valid JSON array.

Rules to evaluate:
1. If text content contains PII/personal information (email, phone etc.)
2. Encoding consistency UTF-8 across text
...

Document Text:
[sampled text here]

Respond with ONLY this JSON array:
[{"rule":"...","status":"COMPLIANT|PARTIAL|NON-COMPLIANT","explanation":"...","llm_confidence":0-100}]
```

The LLM is configured with `temperature=0.1` (very deterministic, minimal creativity), `num_predict=256` (maximum 256 tokens in response), and `num_ctx=1024` (1024-token context window for speed).

### Step 6: JSON Parsing with Fallbacks (`workflow.py`)
LLMs do not always produce perfectly formatted JSON. `_extract_json_array()` uses three fallback strategies:
1. Direct `json.loads()` parse
2. Find `[` and `]` brackets and parse just that slice
3. Use regex to find individual `{...}` objects and collect them

This triple-fallback approach makes the system robust against imperfect LLM output.

### Step 7: Scoring & Classification (`workflow.py`)
For each rule result, the system:
- Maps `COMPLIANT → 1.0`, `PARTIAL → 0.5`, `NON-COMPLIANT → 0.0`
- Multiplies by `llm_confidence` (0–100): `score = weight × confidence`
- Classifies rules as **"presence"** rules (must contain X) vs **"detection"** rules (must NOT contain X) using keyword matching
- Final score = average of all rule scores
- **Critical rule:** If ANY detection rule is NON-COMPLIANT, the overall status is forced to NON-COMPLIANT regardless of the average score

### Step 8: Page Citation (`workflow.py`)
After the LLM call, the system does a fast keyword scan over each page's text to find which pages contain evidence related to each rule. This adds page numbers to the findings (e.g., "Violation found (page [3, 7]): ...") without making any additional LLM calls.

### Step 9: Saving to History (`app.py` + `storage.py`)
Once the scan completes, `app.py` calls `storage.save_scan()` which inserts a row into the SQLite `scan_history` table with the filename, timestamp, score, status, rules used, and full JSON results. This happens automatically after every successful scan.

### Step 10: UI Rendering (`app.py`)
The results page is rendered as four tabs:
- **📈 Dashboard**: Plotly charts — a compliance gauge, a donut chart of pass/fail/partial, a radar chart of rule categories, and a bar chart of individual rule scores
- **🔍 Detailed Findings**: Each rule displayed as an expandable card with its status badge, confidence score, risk level, and explanation
- **⚙️ Rules**: The current ruleset used for this scan
- **📥 Export**: A "Download PDF Report" button that generates and delivers a professional PDF using ReportLab

---

## File-by-File Breakdown

### `app.py` — The Orchestrator (819 lines)
This is the brain of the entire application. Every time the browser page refreshes, this file runs from top to bottom. It:

- **Configures the page** (`st.set_page_config`) with title, icon, and layout
- **Injects custom CSS** from `styles.py` to completely override Streamlit's default look
- **Manages session state** — Streamlit's `st.session_state` is like a persistent dictionary that survives page reruns. It stores: current scan results, document statistics, active compliance rules, the rule editor toggle state, history toggle state, and the current filename
- **Renders the Sidebar** — file uploader, compliance rules widget, rule preset selector, Run/History buttons, and system info
- **Manages the Rule Editor** — a standalone toggle section completely independent of the scan execution
- **Launches the pipeline** in a background thread using `concurrent.futures`
- **Renders the History View** when the 📂 button is pressed
- **Renders the Landing Page** when no scan results are present
- **Renders all four results tabs** with their Plotly charts and findings

### `workflow.py` — The AI Pipeline (330 lines)
This is where the actual intelligence lives. It defines:

- **`PipelineState`**: A TypedDict (typed dictionary) that defines the exact structure of data flowing through the LangGraph pipeline
- **`llm`**: The configured ChatGroq connection to Llama 3 on the Groq Cloud
- **`_parse_rules()`**: Parses the multi-line rules string into a clean list, stripping numbering
- **`_is_presence_rule()`**: Uses keyword matching to classify a rule as "presence" (must have X) or "detection" (must not have X)
- **`_build_batch_prompt()`**: Constructs the carefully engineered LangChain PromptTemplate with detailed instructions for the LLM
- **`_extract_json_array()`**: Robust JSON parser with three fallback strategies
- **`_call_llm_batch()`**: The core function — builds the prompt, calls the LLM, parses the response
- **`check_compliance()`**: The LangGraph node function that orchestrates everything and builds the final results dictionary
- **LangGraph Graph Definition**: At the bottom, a `StateGraph` is created, the single node is added, and it is compiled into `compliance_pipeline` — the object that `app.py` calls with `.invoke()`

### `styles.py` — The Visual Identity (200 lines)
Contains a large string of custom CSS injected into the Streamlit page via `st.markdown(..., unsafe_allow_html=True)`. It defines:

- **CSS custom properties** (variables) for the entire color palette: `--bg-body`, `--accent`, `--rose`, `--emerald`, etc.
- **Sidebar overrides**: Custom file uploader, buttons, brand section, info cards
- **Main area components**: Metric cards, chart cards, finding boxes, status badges
- **Tab styling**: Custom tab bar appearance
- **Stop button styling**: Makes the Streamlit Stop button a bright red color
- **Animations**: Float, pulse-glow, and gradient-shift keyframe animations for the landing page

### `pdf_processor.py` — Document Extraction (80 lines)
A focused, efficient module with one job: extract text from PDFs fast.

- **`extract_all()`**: The primary function. Opens the PDF once with PyMuPDF, iterates every page, collects text and returns a dictionary with `full_text`, `pages` list, `page_count`, and `word_count`. This single-open approach is important — opening a PDF is expensive, and older approaches opened it multiple times.
- **`chunk_text()`**: Splits text into overlapping word-based chunks for RAG (available for use if RAG is re-enabled)
- Backward-compatible wrappers `extract_text_from_pdf()` and `extract_pages()` maintained for legacy code

### `storage.py` — Scan History Database (145 lines)
A clean SQLite database interface with no external dependencies beyond Python's standard library.

- **`init_db()`**: Creates the `scan_history` table if it does not exist. Called automatically on import.
- **`save_scan()`**: Inserts a complete scan record. `rule_results` and `rules_used` are stored as JSON strings using `json.dumps()`
- **`get_all_scans()`**: Returns all scans ordered newest-first, deserializing the JSON fields back into Python objects
- **`get_scan_by_id()`**: Retrieves a single scan by its primary key
- **`delete_scan()`**: Removes a scan record
- **WAL mode**: The database uses Write-Ahead Logging (`PRAGMA journal_mode=WAL`) for better concurrent access performance

### `report_generator.py` — PDF Export (349 lines)
Generates a polished, multi-section PDF report using ReportLab's "platypus" (page layout and typography using scripts) engine.

The report contains five sections:
1. **Cover header** — dark branded banner with document name and generation timestamp
2. **Overall verdict card** — a summary table with the overall status, score, and count of compliant/partial/non-compliant rules
3. **Rule-by-rule analysis table** — every rule with its status badge, score, confidence, risk level, and explanation
4. **Risk distribution table** — counts of HIGH/MEDIUM/LOW risk rules with color-coded rows
5. **Footer** — generation attribution

### `rag_utils.py` — Vector Search Engine (72 lines)
Implements the RAG retrieval mechanism (currently not called in the main pipeline but fully functional).

- **`get_embedding_model()`**: Lazy-loads the `all-MiniLM-L6-v2` SentenceTransformer model exactly once using a module-level singleton pattern
- **`RAGRetriever`**: A class that takes a list of text chunks, encodes them all into embeddings using the sentence transformer, normalizes them with `faiss.normalize_L2()`, and builds a `IndexFlatIP` (inner product / cosine similarity) FAISS index. The `get_relevant_chunks()` method encodes a query and returns the top-k most similar chunks.

### `test_pipeline.py` — End-to-End Tests (available)
Unit and integration tests that run without needing a PDF or a browser. Validates the pipeline logic with dummy text.

---

## Installation & Setup

### Prerequisites
- Python 3.9 or higher
- macOS / Linux / Windows with WSL

### Step 1: Clone or Download the Project
```bash
git clone https://github.com/Sayannaskar1/capstone-ai.git
cd capstone-ai
```

### Step 2: Set up a Virtual Environment & Install Dependencies
It is highly recommended to use a Python virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
pip install -r requirements.txt
```

This installs:
| Package | Purpose |
|---------|---------|
| `streamlit` | Web UI framework |
| `langgraph` | AI workflow graph engine |
| `langchain-groq` | Groq Cloud API connector |
| `langchain-core` | Prompt templates and LCEL |
| `python-dotenv` | Load environment variables |
| `pymupdf` | PDF text extraction |
| `sentence-transformers` | Text embedding model |
| `faiss-cpu` | Vector similarity search |
| `numpy` | Numerical arrays (required by FAISS) |
| `reportlab` | PDF report generation |
| `plotly` | Interactive charts |

### Step 3: Configure Groq API Key
This project uses the Groq Cloud API to run Llama 3 for extremely fast inference.

1. Go to [console.groq.com](https://console.groq.com/) and create a free account
2. Generate an API Key
3. Set the API key in your environment. You can do this by creating a `.env` file in the project directory:

```bash
echo "GROQ_API_KEY=your_api_key_here" > .env
```

*(Note: If deploying to Streamlit Community Cloud, add this key to your app's Advanced Settings > Secrets).*

---

## Running the Application

```bash
streamlit run app.py
```

Open your browser to `http://localhost:8501`

---

## How to Use the UI

### Running a Scan
1. In the **sidebar**, click the file uploader and select a PDF document
2. Optionally, click **✏️ Edit Rules** to customize what the AI checks for
3. Click **🚀 Run Scan** — the status box will show elapsed time
4. When complete, the results appear in four tabs

### Managing Rules
- Click **✏️ Edit Rules** in the sidebar to open the Rule Editor
- Use the ✏️ icon next to any rule to edit it inline
- Use the 🗑 icon to delete a rule
- Type a new rule in the input box and click ＋ to add it
- Click **✕ Close** when done
- You can also select a **Rule Preset** from the dropdown (General Compliance, Legal Contracts, SLA Compliance)

### Viewing Scan History
- Click the **📂** button (next to Run Scan) to open the History view
- All past scans appear with their filename, status, and score
- Click **View Report** on any past scan to reload it into the full dashboard

### Exporting a Report
- After a scan, go to the **📥 Export** tab
- Click **Download PDF Report** to download a professionally formatted report

---

## Understanding the Compliance Score

| Score Range | Status | Meaning |
|-------------|--------|---------|
| 80 – 100 | ✅ COMPLIANT | Document satisfies all or nearly all rules |
| 50 – 79 | ⚠️ PARTIAL | Document partially meets requirements |
| 0 – 49 | ❌ NON-COMPLIANT | Document has significant violations |

**Important override:** If ANY rule classified as a "detection" rule (e.g., "must NOT contain PII") returns NON-COMPLIANT, the overall status is forced to NON-COMPLIANT regardless of the average score. This ensures that hard prohibitions cannot be masked by other passing rules.

**Individual rule score formula:**
```
rule_score = status_weight × llm_confidence
  where status_weight: COMPLIANT=1.0, PARTIAL=0.5, NON-COMPLIANT=0.0
  and llm_confidence: 0–100 (the AI's self-reported certainty)
```

**Final score** = average of all individual rule scores.

---

## Performance Design Decisions

The pipeline is optimized for sub-10-second latency while maintaining full document coverage:

| Optimization | Description | Time Saved |
|-------------|--------|-----------|
| Batched LLM Call | All rules are evaluated in a single prompt rather than one-by-one | ~30s |
| FAISS Inner Product | Uses `IndexFlatIP` (cosine similarity) for lightning-fast retrieval over L2 distance | ~1s |
| Reduced `num_ctx` | Context window strictly limited to 1024 tokens to speed up inference | ~4s |
| Reduced `num_predict` | Max generation limited to 256 tokens | ~5s |
| Eager Model Loading | `SentenceTransformer` model is cached on `app.py` startup to prevent UI freezing | UX improvement |
| Deterministic Engine | LLM runs with `temperature=0.0` for perfectly reproducible output across runs | Consistency |

---

## Dependencies Reference

```
streamlit          — Web app framework
langgraph          — AI workflow graph (StateGraph)
langchain-groq     — Groq Cloud LLM connector
langchain-core     — PromptTemplate, LCEL pipe operator
python-dotenv      — Environment variable loading
pymupdf            — PDF text extraction (fitz)
sentence-transformers — Text embeddings (all-MiniLM-L6-v2)
faiss-cpu          — Vector similarity index
numpy              — Numerical arrays
reportlab          — PDF generation
plotly             — Interactive charts
sqlite3            — Built-in Python, no install needed
```

---

*Built with ❤️ using LangGraph, Groq, Streamlit, and Python.*
