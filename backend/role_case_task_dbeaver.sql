-- =========================================================
-- SQLite / DBeaver 專用版本
-- 特色：
-- 1. 不使用 CREATE TRIGGER，避免 DBeaver 對 BEGIN...END 的解析問題
-- 2. 可直接在 DBeaver 用 Alt+X 執行整份 Script
-- 3. 每個 Case 只對應一位 Expert，因此 expert_id 直接放在 cases
-- 4. 一次派發可包含多個 Task
-- 5. Task 完成狀態由 completed_at 自動推導 is_done
-- 6. 權限規則（只有 Parent/Expert 可派發、只能派自己 Case）
--    建議由後端 API 驗證
-- =========================================================

PRAGMA foreign_keys = ON;

-- =========================================================
-- 1. Users
-- Role: Student / Parent / Expert / Admin
-- =========================================================
CREATE TABLE IF NOT EXISTS users (
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
);

-- =========================================================
-- 2. Student <-> Parent 綁定
-- 支援：
--   一位 Parent 綁多位 Student
--   一位 Student 綁多位 Parent
-- =========================================================
CREATE TABLE IF NOT EXISTS student_parent_links (
    link_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id     INTEGER NOT NULL,
    parent_id      INTEGER NOT NULL,
    relationship   TEXT,
    is_active      INTEGER NOT NULL DEFAULT 1
                   CHECK (is_active IN (0, 1)),
    created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (student_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE,

    FOREIGN KEY (parent_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE,

    UNIQUE (student_id, parent_id)
);

-- =========================================================
-- 3. Cases
--
-- 一個 Case：
--   1 Student
--   1 Parent
--   1 Expert
--
-- 一位 Expert 可以管理很多 Case
-- 但每個 Case 只有一位 Expert
-- =========================================================
CREATE TABLE IF NOT EXISTS cases (
    case_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    case_name      TEXT,

    student_id     INTEGER NOT NULL,
    parent_id      INTEGER NOT NULL,
    expert_id      INTEGER NOT NULL,

    status         TEXT NOT NULL DEFAULT 'active'
                   CHECK (status IN ('active', 'closed')),

    created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (student_id)
        REFERENCES users(user_id)
        ON DELETE RESTRICT,

    FOREIGN KEY (parent_id)
        REFERENCES users(user_id)
        ON DELETE RESTRICT,

    FOREIGN KEY (expert_id)
        REFERENCES users(user_id)
        ON DELETE RESTRICT,

    UNIQUE (student_id, parent_id)
);

-- =========================================================
-- 4. Task Assignment
--
-- 一次「派發任務」建立一筆 assignment。
-- 一個 assignment 可以包含多筆 tasks。
--
-- assigned_by：
--   Parent 或 Expert 的 user_id
--
-- 注意：
-- SQLite 無法只靠 CHECK 跨 users 表驗證 role，
-- 因此「只能 Parent / Expert 派發」由後端 API 驗證。
-- =========================================================
CREATE TABLE IF NOT EXISTS task_assignments (
    assignment_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id        INTEGER NOT NULL,
    assigned_by    INTEGER NOT NULL,
    created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (case_id)
        REFERENCES cases(case_id)
        ON DELETE CASCADE,

    FOREIGN KEY (assigned_by)
        REFERENCES users(user_id)
        ON DELETE RESTRICT
);

-- =========================================================
-- 5. Tasks
--
-- 一個 assignment 可以有很多 task。
--
-- Task 欄位：
--   title
--   content
--   deadline
--   completed_at
--   is_done（自動產生，不可直接修改）
--
-- 狀態：
--   completed_at IS NULL     -> is_done = 0
--   completed_at IS NOT NULL -> is_done = 1
--
-- 完成任務時後端執行：
-- UPDATE tasks
-- SET completed_at = CURRENT_TIMESTAMP
-- WHERE task_id = ?
--   AND completed_at IS NULL;
--
-- 後端不要提供把 completed_at 改回 NULL 的 API，
-- 因此 App 流程只有「未完成 -> 已完成」。
-- =========================================================
CREATE TABLE IF NOT EXISTS tasks (
    task_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id  INTEGER NOT NULL,

    title          TEXT NOT NULL,
    content        TEXT,
    deadline       TEXT,
    is_periodic    INTEGER NOT NULL DEFAULT 0
                   CHECK (is_periodic IN (0, 1)),

    completed_at   TEXT,

    is_done        INTEGER
                   GENERATED ALWAYS AS (
                       CASE
                           WHEN completed_at IS NULL THEN 0
                           ELSE 1
                       END
                   ) VIRTUAL,

    created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (assignment_id)
        REFERENCES task_assignments(assignment_id)
        ON DELETE CASCADE
);

-- =========================================================
-- 5b. Notifications（指派／完成提醒）
-- =========================================================
CREATE TABLE IF NOT EXISTS notifications (
    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    type            TEXT NOT NULL
                    CHECK (type IN ('task_assigned', 'task_completed')),
    task_id         INTEGER NOT NULL,
    case_id         INTEGER NOT NULL,
    actor_id        INTEGER NOT NULL,
    is_read         INTEGER NOT NULL DEFAULT 0
                    CHECK (is_read IN (0, 1)),
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE,

    FOREIGN KEY (task_id)
        REFERENCES tasks(task_id)
        ON DELETE CASCADE,

    FOREIGN KEY (case_id)
        REFERENCES cases(case_id)
        ON DELETE CASCADE,

    FOREIGN KEY (actor_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE
);

-- =========================================================
-- Indexes
-- =========================================================
CREATE INDEX IF NOT EXISTS idx_users_role
ON users(role);

CREATE INDEX IF NOT EXISTS idx_notifications_user
ON notifications(user_id);

CREATE INDEX IF NOT EXISTS idx_notifications_user_unread
ON notifications(user_id, is_read);

-- =========================================================
-- 5c. Mood journals（學生每日心情札記）
-- 每個 Case 同一天只保留一筆，可更新。
-- =========================================================
CREATE TABLE IF NOT EXISTS mood_journals (
    journal_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id        INTEGER NOT NULL,
    student_id     INTEGER NOT NULL,
    entry_date     TEXT NOT NULL,
    mood           TEXT NOT NULL
                   CHECK (mood IN ('happy', 'calm', 'okay', 'sad', 'angry')),
    note           TEXT,
    created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (case_id)
        REFERENCES cases(case_id)
        ON DELETE CASCADE,

    FOREIGN KEY (student_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE,

    UNIQUE (case_id, entry_date)
);

CREATE INDEX IF NOT EXISTS idx_mood_journals_case_date
ON mood_journals(case_id, entry_date);

-- =========================================================
-- 5d. Task comments（任務留言）
-- 所有任務皆可留言。Expert／Parent 可留言與回覆；Student 僅可閱讀。
-- parent_comment_id 為 NULL 表示主留言，回覆只掛在主留言下。
-- =========================================================
CREATE TABLE IF NOT EXISTS task_comments (
    comment_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id            INTEGER NOT NULL,
    parent_comment_id  INTEGER,
    author_id          INTEGER NOT NULL,
    content            TEXT NOT NULL,
    created_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (task_id)
        REFERENCES tasks(task_id)
        ON DELETE CASCADE,

    FOREIGN KEY (parent_comment_id)
        REFERENCES task_comments(comment_id)
        ON DELETE CASCADE,

    FOREIGN KEY (author_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_task_comments_task
ON task_comments(task_id);

CREATE INDEX IF NOT EXISTS idx_task_comments_parent
ON task_comments(parent_comment_id);

CREATE TABLE IF NOT EXISTS task_comment_reads (
    user_id              INTEGER NOT NULL,
    task_id              INTEGER NOT NULL,
    last_read_comment_id INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, task_id),

    FOREIGN KEY (user_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE,

    FOREIGN KEY (task_id)
        REFERENCES tasks(task_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_student_parent_student
ON student_parent_links(student_id);

CREATE INDEX IF NOT EXISTS idx_student_parent_parent
ON student_parent_links(parent_id);

CREATE INDEX IF NOT EXISTS idx_cases_student
ON cases(student_id);

CREATE INDEX IF NOT EXISTS idx_cases_parent
ON cases(parent_id);

CREATE INDEX IF NOT EXISTS idx_cases_expert
ON cases(expert_id);

CREATE INDEX IF NOT EXISTS idx_assignment_case
ON task_assignments(case_id);

CREATE INDEX IF NOT EXISTS idx_assignment_assigned_by
ON task_assignments(assigned_by);

CREATE INDEX IF NOT EXISTS idx_tasks_assignment
ON tasks(assignment_id);

CREATE INDEX IF NOT EXISTS idx_tasks_deadline
ON tasks(deadline);

CREATE INDEX IF NOT EXISTS idx_tasks_completed_at
ON tasks(completed_at);

-- =========================================================
-- 6. View：Case 完整資訊
-- =========================================================
CREATE VIEW IF NOT EXISTS v_case_details AS
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
JOIN users s
    ON s.user_id = c.student_id
JOIN users p
    ON p.user_id = c.parent_id
JOIN users e
    ON e.user_id = c.expert_id;

-- =========================================================
-- 7. View：Task 完整資訊
-- =========================================================
CREATE VIEW IF NOT EXISTS v_task_details AS
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
JOIN task_assignments ta
    ON ta.assignment_id = t.assignment_id
JOIN cases c
    ON c.case_id = ta.case_id
JOIN users s
    ON s.user_id = c.student_id
JOIN users p
    ON p.user_id = c.parent_id
JOIN users e
    ON e.user_id = c.expert_id
JOIN users a
    ON a.user_id = ta.assigned_by;

-- =========================================================
-- 8. 常用 SQL 範例
-- 以下全部是註解，不會在初始化時執行
-- =========================================================

-- ---------------------------------------------------------
-- A. 建立帳號
-- ---------------------------------------------------------
-- INSERT INTO users (username, display_name, role, email)
-- VALUES ('student001', '學生 A', 'Student', 'student001@example.com');
--
-- INSERT INTO users (username, display_name, role, email)
-- VALUES ('parent001', '家長 A', 'Parent', 'parent001@example.com');
--
-- INSERT INTO users (username, display_name, role, email)
-- VALUES ('expert001', '專家 A', 'Expert', 'expert001@example.com');

-- ---------------------------------------------------------
-- B. Student / Parent 綁定
-- ---------------------------------------------------------
-- INSERT INTO student_parent_links (
--     student_id,
--     parent_id,
--     relationship
-- )
-- VALUES (1, 2, 'Mother');

-- ---------------------------------------------------------
-- C. 建立 Case
-- 每個 Case 直接指定唯一 Expert
-- ---------------------------------------------------------
-- INSERT INTO cases (
--     case_name,
--     student_id,
--     parent_id,
--     expert_id
-- )
-- VALUES (
--     'Case-S001',
--     1,
--     2,
--     3
-- );

-- ---------------------------------------------------------
-- D. 一次派發多個任務
--
-- 建議後端用 transaction：
-- 先建立 assignment，再新增多個 task。
-- ---------------------------------------------------------
-- BEGIN TRANSACTION;
--
-- INSERT INTO task_assignments (
--     case_id,
--     assigned_by
-- )
-- VALUES (
--     1,
--     3
-- );
--
-- 假設後端取得剛建立的 assignment_id = 1
--
-- INSERT INTO tasks (
--     assignment_id,
--     title,
--     content,
--     deadline
-- )
-- VALUES
-- (
--     1,
--     '專注力訓練',
--     '完成今日 20 分鐘訓練',
--     '2026-08-20 18:00:00'
-- ),
-- (
--     1,
--     '完成量表',
--     '完成今日指定量表',
--     '2026-08-20 20:00:00'
-- ),
-- (
--     1,
--     '觀看教學影片',
--     '觀看指定教學影片',
--     '2026-08-21 18:00:00'
-- );
--
-- COMMIT;

-- ---------------------------------------------------------
-- E. Student 查自己的全部任務
-- ---------------------------------------------------------
-- SELECT *
-- FROM v_task_details
-- WHERE student_id = 1
-- ORDER BY is_done ASC, deadline ASC;

-- ---------------------------------------------------------
-- F. Expert 查自己的 Case
-- ---------------------------------------------------------
-- SELECT *
-- FROM v_case_details
-- WHERE expert_id = 3
-- ORDER BY case_id DESC;

-- ---------------------------------------------------------
-- G. Parent 查自己的 Case
-- ---------------------------------------------------------
-- SELECT *
-- FROM v_case_details
-- WHERE parent_id = 2
-- ORDER BY case_id DESC;

-- ---------------------------------------------------------
-- H. 查一次派發的全部任務
-- ---------------------------------------------------------
-- SELECT *
-- FROM v_task_details
-- WHERE assignment_id = 1
-- ORDER BY task_id ASC;

-- ---------------------------------------------------------
-- I. 完成 Task
--
-- 加 AND completed_at IS NULL
-- 可以確保同一個 Task 只會第一次完成時寫入時間。
-- ---------------------------------------------------------
-- UPDATE tasks
-- SET completed_at = CURRENT_TIMESTAMP,
--     updated_at = CURRENT_TIMESTAMP
-- WHERE task_id = 1
--   AND completed_at IS NULL;

-- ---------------------------------------------------------
-- J. 查未完成 Task
-- ---------------------------------------------------------
-- SELECT *
-- FROM v_task_details
-- WHERE student_id = 1
--   AND is_done = 0
-- ORDER BY deadline ASC;

-- ---------------------------------------------------------
-- K. 查已完成 Task
-- ---------------------------------------------------------
-- SELECT *
-- FROM v_task_details
-- WHERE student_id = 1
--   AND is_done = 1
-- ORDER BY completed_at DESC;
