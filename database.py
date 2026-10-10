"""SQLite persistence: criteria, runs and supplier results."""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "rfp.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS evaluation_criteria (
    criterion_id INTEGER PRIMARY KEY,
    name         TEXT NOT NULL,
    description  TEXT NOT NULL,
    weight       REAL NOT NULL CHECK (weight >= 0),
    max_score    REAL NOT NULL CHECK (max_score > 0),
    is_active    INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS rfp_runs (
    rfp_run_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    status     TEXT NOT NULL,
    run_json   TEXT
);
CREATE TABLE IF NOT EXISTS supplier_results (
    rfp_run_id        TEXT NOT NULL REFERENCES rfp_runs(rfp_run_id),
    supplier_name     TEXT NOT NULL,
    submission_date   TEXT NOT NULL,
    experience_rating REAL NOT NULL,
    absolute_score    REAL NOT NULL,
    ppi               REAL NOT NULL,
    final_rank        INTEGER NOT NULL,
    result_json       TEXT NOT NULL,
    PRIMARY KEY (rfp_run_id, supplier_name)
);
"""

SEED_CRITERIA = [
    (1, "Technical Capability", "Architecture, integrations, scalability, technical fit", 30, 10, 1),
    (2, "Implementation Plan", "Timeline, milestones, staffing, risk plan", 20, 10, 1),
    (3, "Commercial Value", "Pricing clarity, total cost, assumptions", 20, 10, 1),
    (4, "Security & Compliance", "Controls, certifications, privacy, auditability", 20, 10, 1),
    (5, "Support & Experience", "Support model, similar projects, references", 10, 10, 1),
]


def connect(db_path=None):
    path = Path(db_path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path=None, reseed=False):
    """Create tables and seed criteria (only if empty, or when reseed=True)."""
    conn = connect(db_path)
    with conn:
        conn.executescript(SCHEMA)
        if reseed:
            conn.execute("DELETE FROM evaluation_criteria")
        if conn.execute("SELECT COUNT(*) FROM evaluation_criteria").fetchone()[0] == 0:
            conn.executemany("INSERT INTO evaluation_criteria VALUES (?,?,?,?,?,?)", SEED_CRITERIA)
    conn.close()


def get_criteria(db_path=None, active_only=True):
    sql = "SELECT * FROM evaluation_criteria"
    if active_only:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY criterion_id"
    conn = connect(db_path)
    try:
        return [dict(r) for r in conn.execute(sql)]
    finally:
        conn.close()


def update_criteria(rows, db_path=None):
    conn = connect(db_path)
    with conn:
        for r in rows:
            conn.execute(
                "UPDATE evaluation_criteria SET weight=?, max_score=?, is_active=? WHERE criterion_id=?",
                (float(r["weight"]), float(r["max_score"]), int(bool(r["is_active"])), int(r["criterion_id"])),
            )
    conn.close()


def new_run_id():
    return f"RFP-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:4].upper()}"


def create_run(run_id, db_path=None):
    conn = connect(db_path)
    with conn:
        conn.execute(
            "INSERT INTO rfp_runs (rfp_run_id, created_at, status) VALUES (?,?,?)",
            (run_id, datetime.now(timezone.utc).isoformat(timespec="seconds"), "RUNNING"),
        )
    conn.close()


def mark_run_failed(run_id, message, db_path=None):
    conn = connect(db_path)
    with conn:
        conn.execute("UPDATE rfp_runs SET status=?, run_json=? WHERE rfp_run_id=?",
                     ("FAILED", json.dumps({"error": message}), run_id))
    conn.close()


def get_run_created_at(run_id, db_path=None):
    conn = connect(db_path)
    try:
        return conn.execute("SELECT created_at FROM rfp_runs WHERE rfp_run_id=?", (run_id,)).fetchone()[0]
    finally:
        conn.close()


def save_run(result, db_path=None):
    """Persist the complete run (run-level JSON + one row per supplier) in one transaction."""
    run_id = result["rfp_run_id"]
    conn = connect(db_path)
    with conn:
        conn.execute("UPDATE rfp_runs SET status=?, run_json=? WHERE rfp_run_id=?",
                     ("COMPLETED", json.dumps(result), run_id))
        for s in result["suppliers"]:
            conn.execute(
                "INSERT OR REPLACE INTO supplier_results VALUES (?,?,?,?,?,?,?,?)",
                (run_id, s["supplier_name"], s["submission_date"], s["experience_rating"],
                 s["absolute_score"], s["ppi"], s["final_rank"], json.dumps(s)),
            )
    conn.close()


def list_runs(db_path=None):
    conn = connect(db_path)
    try:
        return [dict(r) for r in conn.execute(
            "SELECT rfp_run_id, created_at, status FROM rfp_runs ORDER BY created_at DESC")]
    finally:
        conn.close()


def load_run(run_id, db_path=None):
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT run_json, status FROM rfp_runs WHERE rfp_run_id=?", (run_id,)).fetchone()
    finally:
        conn.close()
    if not row or row["status"] != "COMPLETED":
        return None
    return json.loads(row["run_json"])
