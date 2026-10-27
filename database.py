# database.py - SQLite connection and automatic table creation
import os
import sqlite3

# The database file sits next to this script (can be overridden for testing)
DB_PATH = os.environ.get("STUDYBUDDY_DB") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "studybuddy.db")


def get_db():
    """Open a connection. Rows can be read by column name (row['task_title'])."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # enforce relationships
    return conn


def init_db():
    """Create the tables if they do not exist yet (runs on every start)."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS subjects (
            subject_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_name TEXT NOT NULL,
            description  TEXT
        );
        CREATE TABLE IF NOT EXISTS tasks (
            task_id          INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id       INTEGER NOT NULL,
            task_title       TEXT NOT NULL,
            task_description TEXT,
            task_type        TEXT NOT NULL DEFAULT 'Assignment',
            deadline         TEXT NOT NULL,
            priority         TEXT NOT NULL DEFAULT 'Medium',
            status           TEXT NOT NULL DEFAULT 'Pending',
            created_at       TEXT NOT NULL,
            FOREIGN KEY (subject_id) REFERENCES subjects (subject_id)
        );
        CREATE TABLE IF NOT EXISTS study_sessions (
            session_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id  INTEGER NOT NULL,
            topic       TEXT NOT NULL,
            study_date  TEXT NOT NULL,
            start_time  TEXT NOT NULL,
            end_time    TEXT NOT NULL,
            notes       TEXT,
            FOREIGN KEY (subject_id) REFERENCES subjects (subject_id)
        );
    """)
    # Upgrade an older database that was created without the task_type column
    columns = [row["name"] for row in conn.execute("PRAGMA table_info(tasks)")]
    if "task_type" not in columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN task_type TEXT NOT NULL DEFAULT 'Assignment'")
    conn.commit()
    conn.close()
