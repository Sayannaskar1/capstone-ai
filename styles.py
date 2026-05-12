"""Enterprise SaaS dark theme — Tailwind-inspired slate/indigo palette."""

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --bg-body: #0f172a;
    --bg-card: #1e293b;
    --bg-card-hover: #273548;
    --bg-input: #0f172a;
    --border: #334155;
    --border-hover: #475569;
    --accent: #6366f1;
    --accent-hover: #818cf8;
    --text-primary: #f8fafc;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    --emerald: #10b981;
    --amber: #f59e0b;
    --rose: #f43f5e;
    --radius: 12px;
    --shadow-sm: 0 1px 2px 0 rgba(0,0,0,0.2);
    --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.25), 0 2px 4px -2px rgba(0,0,0,0.2);
    --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.3), 0 4px 6px -4px rgba(0,0,0,0.25);
}

/* ── GLOBAL ─────────────────────────────────────────────── */
html, body, [class*="css"] { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important; }
.stApp { background: var(--bg-body); color: var(--text-secondary); }
header[data-testid="stHeader"] { background: rgba(15,23,42,0.85) !important; backdrop-filter: saturate(180%) blur(14px) !important; border-bottom: 1px solid var(--border) !important; }
#MainMenu, footer { visibility: hidden; }

/* Stop button styling — clean, no container glow */
[data-testid="stStatusWidget"] button, .stStatusWidget button,
button[data-testid="stBaseButton-header"], button[data-testid="baseButton-header"],
[data-testid="stHeader"] button { background: #f43f5e !important; color: white !important; border: none !important; border-radius: 8px !important; font-weight: 700 !important; font-size: 13px !important; padding: 6px 18px !important; box-shadow: none !important; cursor: pointer !important; }
[data-testid="stStatusWidget"] button:hover, .stStatusWidget button:hover,
button[data-testid="stBaseButton-header"]:hover, [data-testid="stHeader"] button:hover { background: #e11d48 !important; }
/* Running progress bar at top */
[data-testid="stDecoration"], .stDecoration { background: linear-gradient(90deg, #6366f1, #f43f5e, #f59e0b) !important; height: 4px !important; }

/* ── SIDEBAR ────────────────────────────────────────────── */
section[data-testid="stSidebar"] { background: var(--bg-card) !important; border-right: 1px solid var(--border) !important; }
section[data-testid="stSidebar"] * { color: var(--text-secondary) !important; }

/* Sidebar Brand */
.sb-brand { display: flex; align-items: center; gap: 10px; padding: 18px 0 20px; margin-bottom: 16px; border-bottom: 1px solid var(--border); }
.sb-brand-icon { width: 36px; height: 36px; background: linear-gradient(135deg, #4f46e5, #7c3aed); border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 18px; box-shadow: 0 4px 12px rgba(79,70,229,0.35); }
.sb-brand-text h3 { font-size: 15px; font-weight: 700; color: var(--text-primary) !important; margin: 0; letter-spacing: -0.01em; }
.sb-brand-text span { font-size: 10px; color: var(--text-muted) !important; letter-spacing: 0.08em; text-transform: uppercase; }

/* Sidebar Section Labels */
.sb-section { font-size: 10px; font-weight: 700; color: var(--text-muted) !important; letter-spacing: 0.1em; text-transform: uppercase; margin: 20px 0 10px 0; }

/* Sidebar Textarea */
section[data-testid="stSidebar"] .stTextArea textarea { background: var(--bg-input) !important; border: 1px solid var(--border) !important; border-radius: var(--radius) !important; color: var(--text-primary) !important; font-size: 12px !important; font-family: 'JetBrains Mono', monospace !important; line-height: 1.7 !important; box-shadow: var(--shadow-sm) !important; }
section[data-testid="stSidebar"] .stTextArea textarea:focus { border-color: var(--accent) !important; box-shadow: 0 0 0 3px rgba(99,102,241,0.15) !important; }

/* File Uploader */
div[data-testid="stFileUploader"] { border: 2px dashed var(--border) !important; border-radius: var(--radius) !important; padding: 28px 16px !important; background: var(--bg-input) !important; transition: all 0.25s ease; }
div[data-testid="stFileUploader"]:hover { border-color: var(--accent) !important; background: rgba(99,102,241,0.04) !important; }
div[data-testid="stFileUploader"] section { background: transparent !important; }
div[data-testid="stFileUploader"] button { background: var(--border) !important; color: var(--text-primary) !important; border: none !important; border-radius: 8px !important; font-weight: 500 !important; }
div[data-testid="stFileUploader"] small { color: var(--text-muted) !important; }

/* Sidebar Button (Primary) */
section[data-testid="stSidebar"] div.stButton > button[kind="primary"] { background: linear-gradient(135deg, #4f46e5, #6366f1) !important; color: white !important; border: none !important; border-radius: var(--radius) !important; font-weight: 700 !important; font-size: 14px !important; padding: 14px !important; width: 100% !important; box-shadow: 0 4px 14px rgba(79,70,229,0.4) !important; transition: all 0.25s ease; letter-spacing: 0.01em; height: 48px !important; }
section[data-testid="stSidebar"] div.stButton > button[kind="primary"]:hover { box-shadow: 0 8px 25px rgba(79,70,229,0.5) !important; transform: translateY(-2px); }

/* Sidebar Button (Secondary) - Matches primary height */
section[data-testid="stSidebar"] div.stButton > button[kind="secondary"] { padding: 14px !important; height: 48px !important; font-size: 16px !important; border-radius: var(--radius) !important; background: var(--bg-input) !important; border: 1px solid var(--border) !important; color: var(--text-primary) !important; transition: all 0.25s ease; width: 100% !important; }
section[data-testid="stSidebar"] div.stButton > button[kind="secondary"]:hover { border-color: var(--text-muted) !important; background: var(--bg-card) !important; transform: translateY(-2px); }

/* Sidebar Info Cards */
.sb-info-card { background: var(--bg-input); border: 1px solid var(--border); border-radius: 10px; padding: 10px 14px; margin-bottom: 8px; }
.sb-info-row { display: flex; justify-content: space-between; align-items: center; padding: 3px 0; font-size: 11px; }
.sb-info-key { color: var(--text-muted) !important; }
.sb-info-val { color: var(--accent-hover) !important; font-weight: 600; font-family: 'JetBrains Mono', monospace; font-size: 10px; }
.sb-dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; margin-right: 6px; }
.sb-dot-green { background: var(--emerald); box-shadow: 0 0 6px rgba(16,185,129,0.5); }

/* ── MAIN HEADER ────────────────────────────────────────── */
.dash-header { display: flex; justify-content: space-between; align-items: center; padding: 0 0 20px 0; margin-bottom: 28px; border-bottom: 1px solid var(--border); }
.dash-header-left h1 { font-size: 26px; font-weight: 800; color: var(--text-primary); margin: 0; letter-spacing: -0.02em; }
.dash-header-left p { font-size: 13px; color: var(--text-muted); margin: 4px 0 0 0; }

/* Status Badge */
.status-badge { display: inline-flex; align-items: center; gap: 8px; padding: 8px 20px; border-radius: 9999px; font-weight: 700; font-size: 13px; text-transform: uppercase; letter-spacing: 0.06em; }
.status-clean { background: rgba(16,185,129,0.12); color: var(--emerald); border: 1px solid rgba(16,185,129,0.25); }
.status-warn { background: rgba(245,158,11,0.12); color: var(--amber); border: 1px solid rgba(245,158,11,0.25); }
.status-flagged { background: rgba(244,63,94,0.12); color: var(--rose); border: 1px solid rgba(244,63,94,0.25); }

/* ── METRIC CARDS ───────────────────────────────────────── */
.metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }
.metric-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px; position: relative; overflow: hidden; box-shadow: var(--shadow-sm); transition: all 0.25s ease; }
.metric-card:hover { transform: translateY(-3px); border-color: var(--border-hover); box-shadow: var(--shadow-md); }
.metric-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px; border-radius: var(--radius) var(--radius) 0 0; }
.mc-blue::before { background: linear-gradient(90deg, #3b82f6, #60a5fa); }
.mc-emerald::before { background: linear-gradient(90deg, #10b981, #34d399); }
.mc-rose::before { background: linear-gradient(90deg, #f43f5e, #fb7185); }
.mc-amber::before { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
.mc-indigo::before { background: linear-gradient(90deg, #6366f1, #818cf8); }
.metric-icon { width: 42px; height: 42px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 20px; margin-bottom: 14px; }
.mi-blue { background: rgba(59,130,246,0.12); }
.mi-emerald { background: rgba(16,185,129,0.12); }
.mi-rose { background: rgba(244,63,94,0.12); }
.mi-amber { background: rgba(245,158,11,0.12); }
.mi-indigo { background: rgba(99,102,241,0.12); }
.metric-label { font-size: 11px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.06em; }
.metric-value { font-size: 30px; font-weight: 800; color: var(--text-primary); margin-top: 4px; line-height: 1; letter-spacing: -0.02em; }
.metric-sub { font-size: 11px; color: var(--text-muted); margin-top: 6px; }

/* ── TABS ───────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] { gap: 0; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); padding: 4px; margin-bottom: 24px; }
.stTabs [data-baseweb="tab"] { border-radius: 8px !important; color: var(--text-muted) !important; font-weight: 600 !important; font-size: 13px !important; padding: 10px 20px !important; border: none !important; background: transparent !important; transition: all 0.15s !important; }
.stTabs [data-baseweb="tab"]:hover { color: var(--text-secondary) !important; background: rgba(255,255,255,0.03) !important; }
.stTabs [aria-selected="true"] { background: rgba(99,102,241,0.12) !important; color: var(--accent-hover) !important; }
.stTabs [data-baseweb="tab-panel"] { padding-top: 0; }
.stTabs [data-baseweb="tab-highlight"] { display: none !important; }

/* ── CHART CONTAINER ────────────────────────────────────── */
.chart-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px; box-shadow: var(--shadow-sm); margin-bottom: 16px; }
.chart-card-title { font-size: 14px; font-weight: 700; color: var(--text-primary); margin-bottom: 4px; }
.chart-card-sub { font-size: 11px; color: var(--text-muted); margin-bottom: 16px; }

/* ── FINDINGS ───────────────────────────────────────────── */
.streamlit-expanderHeader { background: var(--bg-card) !important; border-radius: var(--radius) !important; border: 1px solid var(--border) !important; color: var(--text-primary) !important; font-weight: 600 !important; font-size: 14px !important; padding: 14px 18px !important; box-shadow: var(--shadow-sm) !important; transition: border-color 0.2s !important; }
.streamlit-expanderHeader:hover { border-color: var(--border-hover) !important; }
div[data-testid="stExpanderDetails"] { background: var(--bg-card) !important; border: 1px solid var(--border) !important; border-top: none !important; border-radius: 0 0 var(--radius) var(--radius) !important; padding: 20px !important; margin-top: -4px !important; }

.finding-box { background: var(--bg-input); border: 1px solid var(--border); border-radius: 10px; padding: 18px; }
.finding-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px; gap: 12px; }
.finding-rule { font-size: 14px; font-weight: 600; color: var(--text-primary); line-height: 1.5; flex: 1; }
.finding-pill { padding: 5px 12px; border-radius: 8px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; flex-shrink: 0; white-space: nowrap; }
.pill-pass { background: rgba(16,185,129,0.12); color: var(--emerald); border: 1px solid rgba(16,185,129,0.25); }
.pill-warn { background: rgba(245,158,11,0.12); color: var(--amber); border: 1px solid rgba(245,158,11,0.25); }
.pill-fail { background: rgba(244,63,94,0.12); color: var(--rose); border: 1px solid rgba(244,63,94,0.25); }
.finding-body { font-size: 13px; color: var(--text-secondary); line-height: 1.7; padding: 14px 16px; border-radius: 8px; background: rgba(255,255,255,0.015); border-left: 4px solid var(--border); }
.fb-pass { border-left-color: var(--emerald); }
.fb-fail { border-left-color: var(--rose); }
.fb-warn { border-left-color: var(--amber); }
.finding-meta { display: flex; gap: 16px; margin-top: 12px; font-size: 11px; color: var(--text-muted); }
.finding-meta span { display: flex; align-items: center; gap: 4px; }

/* ── STATUS WIDGET ──────────────────────────────────────── */
div[data-testid="stStatus"] { background: var(--bg-card) !important; border: 1px solid var(--border) !important; border-radius: var(--radius) !important; box-shadow: var(--shadow-md) !important; }
div[data-testid="stStatus"] * { color: var(--text-secondary) !important; }

/* ── EXPORT PANEL ───────────────────────────────────────── */
.export-panel { background: linear-gradient(145deg, var(--bg-card), var(--bg-body)); border: 1px solid var(--border); border-radius: var(--radius); padding: 28px; text-align: center; box-shadow: var(--shadow-md); margin-top: 24px; }
.export-title { font-size: 17px; font-weight: 700; color: var(--text-primary); margin-bottom: 6px; }
.export-sub { font-size: 13px; color: var(--text-muted); margin-bottom: 20px; }

/* Download Buttons */
div.stDownloadButton > button { background: var(--bg-card) !important; color: var(--text-primary) !important; border: 1px solid var(--border) !important; border-radius: 8px !important; font-weight: 600 !important; padding: 10px 20px !important; box-shadow: var(--shadow-sm) !important; transition: all 0.2s !important; }
div.stDownloadButton > button:hover { background: var(--bg-card-hover) !important; border-color: var(--border-hover) !important; transform: translateY(-1px) !important; box-shadow: var(--shadow-md) !important; }

/* ── EMPTY STATE ────────────────────────────────────────── */
.empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 65vh; text-align: center; }
.empty-icon { width: 80px; height: 80px; background: rgba(99,102,241,0.08); border: 1px solid rgba(99,102,241,0.15); border-radius: 20px; display: flex; align-items: center; justify-content: center; font-size: 36px; margin-bottom: 28px; }
.empty-title { font-size: 22px; font-weight: 700; color: var(--text-primary); margin-bottom: 8px; }
.empty-desc { font-size: 14px; color: var(--text-muted); max-width: 420px; line-height: 1.6; }

/* ── SCROLLBAR ──────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--bg-body); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--border-hover); }

/* ── SIDEBAR RULE CHIP ─────────────────────────────────── */
.sb-rule-chip { background: var(--bg-input); border: 1px solid var(--border); border-radius: 10px; padding: 12px 14px; display: flex; align-items: center; justify-content: space-between; }
.sb-rule-chip-left { display: flex; align-items: center; gap: 10px; }
.sb-rule-chip-icon { width: 32px; height: 32px; background: rgba(99,102,241,0.12); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 15px; }
.sb-rule-chip-text { font-size: 12px; font-weight: 600; color: var(--text-primary) !important; }
.sb-rule-chip-sub { font-size: 10px; color: var(--text-muted) !important; margin-top: 1px; }
.sb-rule-count { background: var(--accent); color: white !important; font-size: 11px; font-weight: 800; padding: 2px 8px; border-radius: 6px; min-width: 24px; text-align: center; }

/* ── RULE MANAGER (Main Content) ───────────────────────── */
.rm-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.rm-title { font-size: 18px; font-weight: 700; color: var(--text-primary); display: flex; align-items: center; gap: 10px; }
.rm-title-badge { background: var(--accent); color: white; font-size: 11px; font-weight: 800; padding: 3px 10px; border-radius: 6px; }
.rm-subtitle { font-size: 12px; color: var(--text-muted); margin-top: 2px; }

/* Main-area buttons — compact icon style for rule actions */
div.stButton > button { background: var(--bg-input) !important; color: var(--text-secondary) !important; border: 1px solid var(--border) !important; border-radius: 8px !important; font-size: 14px !important; padding: 6px 10px !important; font-weight: 500 !important; transition: all 0.15s !important; min-height: 38px !important; box-shadow: none !important; }
div.stButton > button:hover { background: var(--bg-card-hover) !important; border-color: var(--border-hover) !important; color: var(--text-primary) !important; }

/* Primary button override (Save / Add) */
div.stButton > button[kind="primary"] { background: linear-gradient(135deg, #4f46e5, #6366f1) !important; color: white !important; border: none !important; box-shadow: 0 2px 8px rgba(79,70,229,0.3) !important; }
div.stButton > button[kind="primary"]:hover { box-shadow: 0 4px 14px rgba(79,70,229,0.45) !important; transform: translateY(-1px); }

/* Main text inputs */
.stTextInput > div > div > input { background: var(--bg-input) !important; border: 1px solid var(--border) !important; border-radius: 8px !important; color: var(--text-primary) !important; font-size: 13px !important; }
.stTextInput > div > div > input:focus { border-color: var(--accent) !important; box-shadow: 0 0 0 3px rgba(99,102,241,0.12) !important; }

/* Selectbox in main + sidebar */
[data-baseweb="select"] { border-radius: 8px !important; }
[data-baseweb="select"] > div { background: var(--bg-input) !important; border: 1px solid var(--border) !important; border-radius: 8px !important; color: var(--text-primary) !important; }

</style>
"""
