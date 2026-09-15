from __future__ import annotations

import os
import sqlite3
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
# NPerCo/data/app.db（與 Perfect-Co-Parenting 同層，即 workspace 根目錄）
WORKSPACE_ROOT = PROJECT_ROOT.parent
DEFAULT_DB_PATH = WORKSPACE_ROOT / "data" / "app.db"
SCHEMA_PATH = PROJECT_ROOT / "role_case_task_dbeaver.sql"


def get_db_path() -> str:
    return os.environ.get("DATABASE_PATH", str(DEFAULT_DB_PATH))


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or get_db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


USERS_TABLE_SQL = """
CREATE TABLE users (
    user_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    username       TEXT NOT NULL UNIQUE,
    display_name   TEXT NOT NULL,
    role           TEXT NOT NULL
                   CHECK (role IN ('Student', 'Parent', 'Expert', 'Admin')),
    email          TEXT UNIQUE,
    password_hash  TEXT,
    is_active      INTEGER NOT NULL DEFAULT 1
                   CHECK (is_active IN (0, 1)),
    created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

STUDENT_PARENT_LINKS_SQL = """
CREATE TABLE student_parent_links (
    link_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id     INTEGER NOT NULL,
    parent_id      INTEGER NOT NULL,
    relationship   TEXT,
    is_active      INTEGER NOT NULL DEFAULT 1
                   CHECK (is_active IN (0, 1)),
    created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES users(user_id) ON DELETE CASCADE,
    UNIQUE (student_id, parent_id)
)
"""

CASES_SQL = """
CREATE TABLE cases (
    case_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    case_name      TEXT,
    student_id     INTEGER NOT NULL,
    parent_id      INTEGER NOT NULL,
    expert_id      INTEGER NOT NULL,
    status         TEXT NOT NULL DEFAULT 'active'
                   CHECK (status IN ('active', 'closed')),
    created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES users(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (parent_id) REFERENCES users(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (expert_id) REFERENCES users(user_id) ON DELETE RESTRICT,
    UNIQUE (student_id, parent_id)
)
"""

TASK_ASSIGNMENTS_SQL = """
CREATE TABLE task_assignments (
    assignment_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id        INTEGER NOT NULL,
    assigned_by    INTEGER NOT NULL,
    created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_by) REFERENCES users(user_id) ON DELETE RESTRICT
)
"""


def _rebuild_table(
    conn: sqlite3.Connection,
    table: str,
    create_sql: str,
    columns: list[str],
) -> None:
    """Recreate a table in place without rewriting sibling FK names via RENAME."""
    tmp = f"{table}__rebuild"
    conn.execute(f"DROP TABLE IF EXISTS {tmp}")
    conn.execute(create_sql.replace(f"CREATE TABLE {table}", f"CREATE TABLE {tmp}", 1))
    cols = ", ".join(columns)
    conn.execute(f"INSERT INTO {tmp} ({cols}) SELECT {cols} FROM {table}")
    conn.execute(f"DROP TABLE {table}")
    conn.execute(f"ALTER TABLE {tmp} RENAME TO {table}")


def _migrate_users_admin_role(conn: sqlite3.Connection) -> None:
    """Rebuild users table if CHECK constraint does not allow Admin yet."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'users'"
    ).fetchone()
    if row is None or row["sql"] is None:
        return
    if "'Admin'" in row["sql"] or '"Admin"' in row["sql"]:
        return

    # Create new table first (do NOT rename users away — that rewrites child FKs).
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute("DROP TABLE IF EXISTS users__rebuild")
        conn.execute(
            USERS_TABLE_SQL.replace("CREATE TABLE users", "CREATE TABLE users__rebuild", 1)
        )
        conn.execute(
            """
            INSERT INTO users__rebuild (
                user_id, username, display_name, role, email,
                password_hash, is_active, created_at, updated_at
            )
            SELECT
                user_id, username, display_name, role, email,
                password_hash, is_active, created_at, updated_at
            FROM users
            """
        )
        conn.execute("DROP TABLE users")
        conn.execute("ALTER TABLE users__rebuild RENAME TO users")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")
        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


V_CASE_DETAILS_SQL = """
CREATE VIEW v_case_details AS
SELECT
    c.case_id,
    c.case_name,
    c.status,
    c.student_id,
    s.display_name AS student_name,
    c.parent_id,
    p.display_name AS parent_name,
    c.expert_id,
    e.display_name AS expert_name,
    c.created_at,
    c.updated_at
FROM cases c
JOIN users s ON s.user_id = c.student_id
JOIN users p ON p.user_id = c.parent_id
JOIN users e ON e.user_id = c.expert_id
"""

V_TASK_DETAILS_SQL = """
CREATE VIEW v_task_details AS
SELECT
    t.task_id,
    ta.assignment_id,
    ta.case_id,
    c.case_name,
    c.student_id,
    s.display_name AS student_name,
    c.parent_id,
    p.display_name AS parent_name,
    c.expert_id,
    e.display_name AS expert_name,
    t.title,
    t.content,
    t.deadline,
    t.is_done,
    t.completed_at,
    ta.assigned_by,
    a.display_name AS assigned_by_name,
    a.role AS assigned_by_role,
    ta.created_at AS assigned_at,
    t.created_at,
    t.updated_at
FROM tasks t
JOIN task_assignments ta ON ta.assignment_id = t.assignment_id
JOIN cases c ON c.case_id = ta.case_id
JOIN users s ON s.user_id = c.student_id
JOIN users p ON p.user_id = c.parent_id
JOIN users e ON e.user_id = c.expert_id
JOIN users a ON a.user_id = ta.assigned_by
"""


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {row["name"] for row in rows}


def _recover_orphan_rebuild(conn: sqlite3.Connection, table: str) -> None:
    """Recover from a failed rebuild that left `{table}__rebuild` behind."""
    tmp = f"{table}__rebuild"
    names = _table_names(conn)
    if tmp not in names:
        return
    if table not in names:
        conn.execute(f"ALTER TABLE {tmp} RENAME TO {table}")
        return
    count = conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]
    if count == 0:
        conn.execute(f"DROP TABLE {table}")
        conn.execute(f"ALTER TABLE {tmp} RENAME TO {table}")
    else:
        conn.execute(f"DROP TABLE {tmp}")


def _repair_broken_user_fks(conn: sqlite3.Connection) -> None:
    """Fix DBs broken by the old users rename migration (FK -> users_old_admin_mig)."""
    broken = conn.execute(
        """
        SELECT name, type FROM sqlite_master
        WHERE sql LIKE '%users_old_admin_mig%'
        """
    ).fetchall()
    orphans = {
        name
        for name in (
            "student_parent_links__rebuild",
            "cases__rebuild",
            "task_assignments__rebuild",
            "users__rebuild",
        )
        if name in _table_names(conn)
    }
    if not broken and not orphans:
        return

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        # Views must be dropped before rebuilding referenced tables.
        conn.execute("DROP VIEW IF EXISTS v_task_details")
        conn.execute("DROP VIEW IF EXISTS v_case_details")

        for table in ("users", "student_parent_links", "cases", "task_assignments"):
            _recover_orphan_rebuild(conn, table)

        names = {row["name"] for row in broken if row["type"] == "table"}
        # Re-check after orphan recovery — schema may have recreated empty tables.
        still_broken = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND sql LIKE '%users_old_admin_mig%'"
            )
        }
        names |= still_broken

        if "student_parent_links" in names:
            _rebuild_table(
                conn,
                "student_parent_links",
                STUDENT_PARENT_LINKS_SQL,
                [
                    "link_id",
                    "student_id",
                    "parent_id",
                    "relationship",
                    "is_active",
                    "created_at",
                ],
            )
        if "cases" in names:
            _rebuild_table(
                conn,
                "cases",
                CASES_SQL,
                [
                    "case_id",
                    "case_name",
                    "student_id",
                    "parent_id",
                    "expert_id",
                    "status",
                    "created_at",
                    "updated_at",
                ],
            )
        if "task_assignments" in names:
            _rebuild_table(
                conn,
                "task_assignments",
                TASK_ASSIGNMENTS_SQL,
                ["assignment_id", "case_id", "assigned_by", "created_at"],
            )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_student_parent_student "
            "ON student_parent_links(student_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_student_parent_parent "
            "ON student_parent_links(parent_id)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cases_student ON cases(student_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cases_parent ON cases(parent_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cases_expert ON cases(expert_id)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_assignment_case ON task_assignments(case_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_assignment_assigned_by "
            "ON task_assignments(assigned_by)"
        )
        conn.execute(V_CASE_DETAILS_SQL)
        conn.execute(V_TASK_DETAILS_SQL)
        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _migrate_tasks_is_periodic(conn: sqlite3.Connection) -> None:
    cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(tasks)").fetchall()
    }
    if "is_periodic" in cols:
        return
    conn.execute(
        "ALTER TABLE tasks ADD COLUMN is_periodic INTEGER NOT NULL DEFAULT 0"
    )
    conn.commit()


def init_db(db_path: str | None = None) -> None:
    path = db_path or get_db_path()
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Schema not found: {SCHEMA_PATH}")

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn = get_connection(path)
    try:
        conn.executescript(schema_sql)
        conn.commit()
        _migrate_users_admin_role(conn)
        _repair_broken_user_fks(conn)
        _migrate_tasks_is_periodic(conn)
    finally:
        conn.close()
