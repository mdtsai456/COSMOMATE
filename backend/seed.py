from __future__ import annotations

import os
import sqlite3
from datetime import date, timedelta

import bcrypt


SEED_PASSWORD = "password123"


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _user_id(conn: sqlite3.Connection, username: str) -> int | None:
    row = conn.execute(
        "SELECT user_id FROM users WHERE username = ?", (username,)
    ).fetchone()
    return None if row is None else int(row["user_id"])


def _ensure_user(
    conn: sqlite3.Connection,
    username: str,
    display_name: str,
    role: str,
    email: str,
    password_hash: str,
) -> int:
    existing = _user_id(conn, username)
    if existing is not None:
        return existing
    conn.execute(
        """
        INSERT INTO users (username, display_name, role, email, password_hash)
        VALUES (?, ?, ?, ?, ?)
        """,
        (username, display_name, role, email, password_hash),
    )
    uid = _user_id(conn, username)
    assert uid is not None
    return uid


def _ensure_link(
    conn: sqlite3.Connection,
    student_id: int,
    parent_id: int,
    relationship: str,
) -> None:
    row = conn.execute(
        """
        SELECT link_id FROM student_parent_links
        WHERE student_id = ? AND parent_id = ?
        """,
        (student_id, parent_id),
    ).fetchone()
    if row is not None:
        return
    conn.execute(
        """
        INSERT INTO student_parent_links (student_id, parent_id, relationship)
        VALUES (?, ?, ?)
        """,
        (student_id, parent_id, relationship),
    )


def _ensure_case(
    conn: sqlite3.Connection,
    case_name: str,
    student_id: int,
    parent_id: int,
    expert_id: int,
) -> int:
    row = conn.execute(
        "SELECT case_id FROM cases WHERE case_name = ?", (case_name,)
    ).fetchone()
    if row is not None:
        return int(row["case_id"])
    conn.execute(
        """
        INSERT INTO cases (case_name, student_id, parent_id, expert_id, status)
        VALUES (?, ?, ?, ?, 'active')
        """,
        (case_name, student_id, parent_id, expert_id),
    )
    created = conn.execute(
        "SELECT case_id FROM cases WHERE case_name = ?", (case_name,)
    ).fetchone()
    assert created is not None
    return int(created["case_id"])


S001_DEMO_SENTINEL = "穩定作息練習"

# 30 天心情（舊→新）：前半偏穩定正向，近 14 天走弱後略回升，讓 EWMA 顯示下降。
S001_MOOD_DAYS: list[tuple[str, str] | None] = [
    ("happy", "今天練習很順利，睡得比較好。"),
    ("calm", "下午有點累，晚上還算平靜。"),
    ("happy", "和家人一起吃飯，心情不錯。"),
    ("okay", "功課普通，沒有特別起伏。"),
    ("calm", "呼吸練習有幫上忙。"),
    ("happy", "被稱讚有進步，很開心。"),
    ("calm", "作息有跟上，感覺穩定。"),
    ("happy", "完成任務後有成就感。"),
    ("okay", "白天還好，晚上有點煩。"),
    None,  # 缺記一筆，模擬漏填
    ("calm", "散步後比較放鬆。"),
    ("happy", "今天狀態很好。"),
    ("okay", "平平常常的一天。"),
    ("calm", "睡前記得做放鬆。"),
    ("happy", "週末過得愉快。"),
    ("calm", "新的一週開始，還算穩。"),
    ("okay", "有點提不起勁，但有完成作業。"),
    ("calm", "專家說可以放慢步調。"),
    ("okay", "心情普通，不太想說話。"),
    ("sad", "和同學鬧不愉快，很難過。"),
    ("okay", "有比較好一點，但還是悶。"),
    ("sad", "晚上睡不著，一直想事情。"),
    ("angry", "被念了好幾次，很生氣。"),
    ("sad", "生氣過後變得低落。"),
    ("okay", "勉強完成任務，沒有力氣多寫。"),
    ("sad", "不太想出門，只想待在房裡。"),
    None,
    ("angry", "又因為螢幕時間被唸。"),
    ("sad", "知道自己該做，可是做不到。"),
    ("okay", "今天有回穩一點，至少有寫札記。"),
]


def _running_under_pytest() -> bool:
    return bool(os.environ.get("PYTEST_CURRENT_TEST"))


def _recurring_dates(start: date, times_per_week: int, weeks: int) -> list[date]:
    dates: list[date] = []
    for week in range(weeks):
        for session in range(times_per_week):
            offset = week * 7 + (session * 7) // times_per_week
            dates.append(start + timedelta(days=offset))
    return dates


def _insert_assignment(
    conn: sqlite3.Connection,
    case_id: int,
    assigned_by: int,
    created_at: str,
    items: list[tuple[str, str | None, str | None, int, str | None, str]],
) -> list[int]:
    cur = conn.execute(
        """
        INSERT INTO task_assignments (case_id, assigned_by, created_at)
        VALUES (?, ?, ?)
        """,
        (case_id, assigned_by, created_at),
    )
    assignment_id = int(cur.lastrowid)
    task_ids: list[int] = []
    for title, content, deadline, is_periodic, completed_at, task_created in items:
        inserted = conn.execute(
            """
            INSERT INTO tasks (
                assignment_id, title, content, deadline, is_periodic,
                completed_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                assignment_id,
                title,
                content,
                deadline,
                is_periodic,
                completed_at,
                task_created,
                completed_at or task_created,
            ),
        )
        task_ids.append(int(inserted.lastrowid))
    return task_ids


def _clear_case_tasks(conn: sqlite3.Connection, case_id: int) -> None:
    conn.execute("DELETE FROM notifications WHERE case_id = ?", (case_id,))
    conn.execute(
        """
        DELETE FROM tasks
        WHERE assignment_id IN (
            SELECT assignment_id FROM task_assignments WHERE case_id = ?
        )
        """,
        (case_id,),
    )
    conn.execute("DELETE FROM task_assignments WHERE case_id = ?", (case_id,))


def _ensure_case_s001_demo_content(conn: sqlite3.Connection) -> None:
    """Fill Case-S001 with a 30-day mood/task timeline for 狀態追蹤."""
    if _running_under_pytest():
        return

    row = conn.execute(
        """
        SELECT case_id, student_id, parent_id, expert_id
        FROM cases
        WHERE case_name = 'Case-S001'
        """
    ).fetchone()
    if row is None:
        return

    case_id = int(row["case_id"])
    student_id = int(row["student_id"])
    parent_id = int(row["parent_id"])
    expert_id = int(row["expert_id"])

    already = conn.execute(
        """
        SELECT 1
        FROM tasks t
        JOIN task_assignments ta ON ta.assignment_id = t.assignment_id
        WHERE ta.case_id = ? AND t.title = ?
        LIMIT 1
        """,
        (case_id, S001_DEMO_SENTINEL),
    ).fetchone()
    if already is not None:
        return

    today = date.today()
    start = today - timedelta(days=len(S001_MOOD_DAYS) - 1)

    for offset, entry in enumerate(S001_MOOD_DAYS):
        if entry is None:
            continue
        mood, note = entry
        entry_date = (start + timedelta(days=offset)).isoformat()
        stamped = f"{entry_date} 21:10:00"
        conn.execute(
            """
            INSERT INTO mood_journals (
                case_id, student_id, entry_date, mood, note, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(case_id, entry_date) DO UPDATE SET
                mood = excluded.mood,
                note = excluded.note,
                updated_at = excluded.updated_at
            """,
            (case_id, student_id, entry_date, mood, note, stamped, stamped),
        )

    _clear_case_tasks(conn, case_id)

    expert_items: list[tuple[str, str | None, str | None, int, str | None, str]] = []
    parent_items: list[tuple[str, str | None, str | None, int, str | None, str]] = []

    daily_catalog = [
        ("寫下三件小事", "把今天發生的三件小事寫下來，不一定要正面。", "expert"),
        ("準時上床", "22:30 前上床，手機放到客廳。", "parent"),
        ("短散步 15 分鐘", "出門走一圈，回來在札記寫一句話。", "expert"),
        ("整理書包", "睡前把明天要用的東西放進書包。", "parent"),
        ("情緒辨識練習", "選一個情緒詞，寫下為什麼會有這種感覺。", "expert"),
        ("一起吃晚餐", "晚餐時不滑手機，講一件今天的事。", "parent"),
    ]

    def stamp(day: date, hour: str) -> str:
        return f"{day.isoformat()} {hour}"

    for offset in range(len(S001_MOOD_DAYS)):
        day = start + timedelta(days=offset)
        days_ago = (today - day).days
        pair = (offset % 3) * 2
        expert_spec = daily_catalog[pair]
        parent_spec = daily_catalog[pair + 1]
        if days_ago >= 14:
            expert_done, parent_done = True, True
        elif days_ago >= 7:
            expert_done, parent_done = True, offset % 3 != 0
        elif days_ago >= 3:
            expert_done, parent_done = offset % 2 == 0, offset % 2 == 1
        else:
            expert_done, parent_done = False, False
        if days_ago == 0:
            expert_done, parent_done = True, False
        for spec, done, bucket in (
            (expert_spec, expert_done, expert_items),
            (parent_spec, parent_done, parent_items),
        ):
            title, content, _role = spec
            bucket.append(
                (
                    title,
                    content,
                    stamp(day, "18:00:00"),
                    0,
                    stamp(day, "19:40:00") if done else None,
                    stamp(day, "09:00:00"),
                )
            )

    breath_dates = _recurring_dates(today - timedelta(days=27), 3, 4)
    total_breath = len(breath_dates)
    for index, day in enumerate(breath_dates, start=1):
        days_ago = (today - day).days
        done = days_ago >= 2
        expert_items.append(
            (
                "正念呼吸",
                f"每次 10分鐘（第 {index}/{total_breath} 次）",
                stamp(day, "18:00:00"),
                1,
                stamp(day, "18:25:00") if done else None,
                stamp(day, "08:30:00"),
            )
        )

    # Sentinel：用來判斷示範資料是否已寫入，避免重開伺服器重複插入。
    expert_items.insert(
        0,
        (
            S001_DEMO_SENTINEL,
            "連續一週把起床、吃飯、睡覺時間寫下來。",
            stamp(start, "18:00:00"),
            0,
            stamp(start, "19:15:00"),
            stamp(start, "08:00:00"),
        ),
    )

    expert_ids = _insert_assignment(
        conn, case_id, expert_id, stamp(start, "08:00:00"), expert_items
    )
    _insert_assignment(conn, case_id, parent_id, stamp(start, "08:20:00"), parent_items)

    comment_task_id = expert_ids[-3] if len(expert_ids) >= 3 else expert_ids[-1]
    cur = conn.execute(
        """
        INSERT INTO task_comments (task_id, parent_comment_id, author_id, content, created_at)
        VALUES (?, NULL, ?, ?, ?)
        """,
        (
            comment_task_id,
            expert_id,
            "這次有把情緒寫具體，很好。下次可以再補上當時發生什麼事。",
            stamp(today - timedelta(days=2), "20:05:00"),
        ),
    )
    parent_comment_id = int(cur.lastrowid)
    conn.execute(
        """
        INSERT INTO task_comments (task_id, parent_comment_id, author_id, content, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            comment_task_id,
            parent_comment_id,
            parent_id,
            "我們晚上有一起看他寫的內容，他比較願意講了。",
            stamp(today - timedelta(days=1), "21:40:00"),
        ),
    )


def ensure_admin(conn: sqlite3.Connection) -> None:
    password_hash = _hash_password(SEED_PASSWORD)
    _ensure_user(
        conn,
        "admin001",
        "管理者",
        "Admin",
        "admin001@example.com",
        password_hash,
    )
    conn.commit()


def ensure_demo_data(conn: sqlite3.Connection) -> None:
    """Ensure expanded demo users/cases exist (safe for existing DBs)."""
    password_hash = _hash_password(SEED_PASSWORD)

    admin_id = _ensure_user(
        conn, "admin001", "管理者", "Admin", "admin001@example.com", password_hash
    )
    expert1 = _ensure_user(
        conn, "expert001", "專家 A", "Expert", "expert001@example.com", password_hash
    )
    expert2 = _ensure_user(
        conn, "expert002", "專家 B", "Expert", "expert002@example.com", password_hash
    )
    parent1 = _ensure_user(
        conn, "parent001", "家長 A", "Parent", "parent001@example.com", password_hash
    )
    parent2 = _ensure_user(
        conn, "parent002", "家長 B", "Parent", "parent002@example.com", password_hash
    )
    parent3 = _ensure_user(
        conn, "parent003", "家長 C", "Parent", "parent003@example.com", password_hash
    )
    student1 = _ensure_user(
        conn, "student001", "學生 A", "Student", "student001@example.com", password_hash
    )
    student2 = _ensure_user(
        conn, "student002", "學生 B", "Student", "student002@example.com", password_hash
    )
    student3 = _ensure_user(
        conn, "student003", "學生 C", "Student", "student003@example.com", password_hash
    )
    _ = admin_id

    _ensure_link(conn, student1, parent1, "Mother")
    _ensure_link(conn, student2, parent2, "Father")
    _ensure_link(conn, student3, parent3, "Mother")

    # expert001 has 2 cases; expert002 has 1 case
    _ensure_case(conn, "Case-S001", student1, parent1, expert1)
    _ensure_case(conn, "Case-S002", student2, parent2, expert1)
    _ensure_case(conn, "Case-S003", student3, parent3, expert2)

    _ensure_case_s001_demo_content(conn)
    conn.commit()


def seed_if_empty(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()
    if row is not None and row["cnt"] > 0:
        return
    ensure_demo_data(conn)
