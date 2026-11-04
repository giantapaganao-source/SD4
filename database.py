# database.py - SQLite connection and automatic table creation
import os
import sqlite3

from turso_serverless import IntegrityError as TursoIntegrityError

TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")
DB_PATH = os.environ.get("STUDYBUDDY_DB") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "studybuddy.db")


class _NamedRow:
    def __init__(self, values, columns):
        self._values = values
        self._indexes = {name: index for index, name in enumerate(columns)}

    def __getitem__(self, key):
        if isinstance(key, str):
            key = self._indexes[key]
        return self._values[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)


class _RemoteCursor:
    def __init__(self, cursor):
        self._cursor = cursor
        self._columns = [column[0] for column in (cursor.description or ())]

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def _row(self, values):
        return _NamedRow(values, self._columns) if values is not None else None

    def fetchone(self):
        return self._row(self._cursor.fetchone())

    def fetchall(self):
        return [self._row(values) for values in self._cursor.fetchall()]

    def __iter__(self):
        return iter(self.fetchall())


class _RemoteConnection:
    def __init__(self, connection):
        self._connection = connection

    def execute(self, statement, parameters=()):
        return _RemoteCursor(self._connection.execute(statement, parameters))

    def __getattr__(self, name):
        return getattr(self._connection, name)


def is_integrity_error(error):
    """Recognize constraint errors from the supported SQLite-compatible drivers."""
    return isinstance(error, (sqlite3.IntegrityError, TursoIntegrityError)) or (
        isinstance(error, ValueError) and "constraint failed" in str(error).lower()
    )


def get_db():
    """Open a local SQLite or hosted Turso connection."""
    if bool(TURSO_DATABASE_URL) != bool(TURSO_AUTH_TOKEN):
        raise RuntimeError(
            "Set both TURSO_DATABASE_URL and TURSO_AUTH_TOKEN to use Turso."
        )

    if TURSO_DATABASE_URL and TURSO_AUTH_TOKEN:
        if TURSO_DATABASE_URL.startswith("libsql://"):
            import libsql

            conn = libsql.connect(
                database=TURSO_DATABASE_URL,
                auth_token=TURSO_AUTH_TOKEN,
            )
        elif TURSO_DATABASE_URL.startswith(("https://", "http://")):
            import turso_serverless

            conn = turso_serverless.connect(
                TURSO_DATABASE_URL,
                auth_token=TURSO_AUTH_TOKEN,
            )
        else:
            raise RuntimeError(
                "TURSO_DATABASE_URL must use libsql://, https://, or http://."
            )
        return _RemoteConnection(conn)
    else:
        if os.environ.get("VERCEL"):
            raise RuntimeError(
                "TURSO_DATABASE_URL and TURSO_AUTH_TOKEN must be set on Vercel."
            )
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON")

    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the tables if they do not exist yet (runs on every start)."""
    conn = get_db()
    schema = (
        """CREATE TABLE IF NOT EXISTS users (
            user_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            nickname  TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS subjects (
            subject_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_name TEXT NOT NULL,
            description  TEXT,
            user_id      INTEGER REFERENCES users (user_id)
        )""",
        """CREATE TABLE IF NOT EXISTS tasks (
            task_id          INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id       INTEGER NOT NULL,
            task_title       TEXT NOT NULL,
            task_description TEXT,
            task_type        TEXT NOT NULL DEFAULT 'Assignment',
            deadline         TEXT NOT NULL,
            deadline_time    TEXT NOT NULL DEFAULT '23:59',
            priority         TEXT NOT NULL DEFAULT 'Medium',
            status           TEXT NOT NULL DEFAULT 'Pending',
            created_at       TEXT NOT NULL,
            FOREIGN KEY (subject_id) REFERENCES subjects (subject_id)
        )""",
        """CREATE TABLE IF NOT EXISTS study_sessions (
            session_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id  INTEGER NOT NULL,
            topic       TEXT NOT NULL,
            study_date  TEXT NOT NULL,
            start_time  TEXT NOT NULL,
            end_time    TEXT NOT NULL,
            notes       TEXT,
            FOREIGN KEY (subject_id) REFERENCES subjects (subject_id)
        )""",
    )
    for statement in schema:
        conn.execute(statement)

    # Upgrade an older database that was created without the task_type column
    columns = [row["name"] for row in conn.execute("PRAGMA table_info(tasks)")]
    if "task_type" not in columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN task_type TEXT NOT NULL DEFAULT 'Assignment'")
    if "deadline_time" not in columns:
        conn.execute(
            "ALTER TABLE tasks ADD COLUMN deadline_time TEXT NOT NULL DEFAULT '23:59'"
        )
    columns = [row["name"] for row in conn.execute("PRAGMA table_info(subjects)")]
    if "user_id" not in columns:
        conn.execute("ALTER TABLE subjects ADD COLUMN user_id INTEGER REFERENCES users (user_id)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_nickname_unique "
                 "ON users (nickname COLLATE NOCASE)")
    conn.execute("CREATE INDEX IF NOT EXISTS subjects_user_id ON subjects (user_id)")
    conn.commit()
    conn.close()
