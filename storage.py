"""
storage.py
Lightweight SQLite storage for compliance scan history.
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "scan_history.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create the scan_history table if it doesn't exist."""
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scan_history (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            filename        TEXT NOT NULL,
            scan_timestamp  TEXT NOT NULL,
            page_count      INTEGER DEFAULT 0,
            word_count      INTEGER DEFAULT 0,
            final_score     REAL DEFAULT 0.0,
            overall_status  TEXT DEFAULT '',
            rules_used      TEXT DEFAULT '[]',
            rule_results    TEXT DEFAULT '[]',
            analysis_report TEXT DEFAULT '',
            created_at      TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


def save_scan(
    filename: str,
    scan_timestamp: str,
    page_count: int,
    word_count: int,
    final_score: float,
    overall_status: str,
    rules_used: List[str],
    rule_results: List[Dict[str, Any]],
    analysis_report: str,
) -> int:
    """Save a scan result and return the new row ID."""
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO scan_history
           (filename, scan_timestamp, page_count, word_count,
            final_score, overall_status, rules_used, rule_results, analysis_report)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            filename,
            scan_timestamp,
            page_count,
            word_count,
            final_score,
            overall_status,
            json.dumps(rules_used),
            json.dumps(rule_results),
            analysis_report,
        ),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def get_all_scans() -> List[Dict[str, Any]]:
    """Return all scans, newest first."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM scan_history ORDER BY id DESC"
    ).fetchall()
    conn.close()
    results = []
    for r in rows:
        results.append({
            "id": r["id"],
            "filename": r["filename"],
            "scan_timestamp": r["scan_timestamp"],
            "page_count": r["page_count"],
            "word_count": r["word_count"],
            "final_score": r["final_score"],
            "overall_status": r["overall_status"],
            "rules_used": json.loads(r["rules_used"]),
            "rule_results": json.loads(r["rule_results"]),
            "analysis_report": r["analysis_report"],
        })
    return results


def get_scan_by_id(scan_id: int) -> Optional[Dict[str, Any]]:
    """Return a single scan by ID."""
    conn = _get_conn()
    r = conn.execute(
        "SELECT * FROM scan_history WHERE id = ?", (scan_id,)
    ).fetchone()
    conn.close()
    if not r:
        return None
    return {
        "id": r["id"],
        "filename": r["filename"],
        "scan_timestamp": r["scan_timestamp"],
        "page_count": r["page_count"],
        "word_count": r["word_count"],
        "final_score": r["final_score"],
        "overall_status": r["overall_status"],
        "rules_used": json.loads(r["rules_used"]),
        "rule_results": json.loads(r["rule_results"]),
        "analysis_report": r["analysis_report"],
    }


def delete_scan(scan_id: int):
    """Delete a scan record."""
    conn = _get_conn()
    conn.execute("DELETE FROM scan_history WHERE id = ?", (scan_id,))
    conn.commit()
    conn.close()


def get_scan_count() -> int:
    """Return the total number of stored scans."""
    conn = _get_conn()
    count = conn.execute("SELECT COUNT(*) FROM scan_history").fetchone()[0]
    conn.close()
    return count


# Initialize DB on import
init_db()
