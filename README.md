# Perfect Co-parenting API

Expert／Parent／Student 任務指派後端（MVP）。

## 流程

```
Login (JWT)
  ├─ Expert → Cases → Assign（派發）
  ├─ Parent → Cases → Contract（= Assign）
  └─ Student → Cases → Execute（完成任務）
                         ↓
              Expert／Parent 查看任務進度
```

## Zeabur

- 根目錄留空（部署整個 `Perfect-Co-Parenting`，含 `frontend/`）
- 建置由根目錄 `zbpack.json` 指定為 Python + uvicorn
- 環境變數：`DATABASE_PATH=/data/app.db`（並掛載 Volume 到 `/data`）

## 啟動

在 `backend` 目錄使用專案虛擬環境（不污染本機 Python）：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\uvicorn app.main:app --reload --app-dir .
```

開啟前端：http://127.0.0.1:8000/（同一網址：CosmoMate 開場 → 登入 → 儀表板）  
API 文件：http://127.0.0.1:8000/docs

資料庫預設：`data/app.db`（與 `backend/` 同層；啟動時套用 `role_case_task_dbeaver.sql` 並 seed）。可用環境變數 `DATABASE_PATH` 覆寫（Zeabur 建議 `/data/app.db` + Volume）。

## 前端

`frontend/` 為純 HTML／CSS／JS，由 FastAPI 同源提供：
- `/`：單一 SPA（無 token 先 CosmoMate 開場，按登入進表單；有 token 進儀表板）
- `frontend/landing/`：開場畫面資源（由 `app.js` 在同頁切換，不換網址）
- `/app`：重新導向至 `/`

登入後為儀表板：左側篩選（未完成／已完成／Expert 指派／Parent 指派）、完成度與月曆、任務列表、通知鈴鐺紅點。Expert 左側 `+` 可新增 Case（綁定 Student + Parent）；Expert／Parent 可 Assign／Contract 任務。

## Seed 帳號

| username | role | password |
|----------|------|----------|
| admin001 | Admin | password123 |
| expert001 | Expert | password123（2 cases：Case-S001、Case-S002） |
| expert002 | Expert | password123（1 case：Case-S003） |
| parent001 / parent002 / parent003 | Parent | password123 |
| student001 / student002 / student003 | Student | password123 |

## 主要 API

| Method | Path | 說明 |
|--------|------|------|
| POST | `/auth/login` | 登入取得 JWT |
| GET | `/me` | 目前使用者 |
| GET | `/admin/users` | **Admin** 列出全部使用者（可選 `?role=`） |
| GET | `/admin/cases` | **Admin** 列出全部 cases（expert → student + parent） |
| GET | `/cases` | 自己的 cases |
| POST | `/cases` | **Expert** 新增 case（綁定 `student_id` + `parent_id`） |
| GET | `/users?role=Student\|Parent` | **Expert／Admin** 列出可綁定的使用者 |
| GET | `/cases/{id}/moods` | Case 心情札記列表（Student／Parent／Expert） |
| PUT | `/cases/{id}/moods` | **僅本案 Student** 寫入／更新當天心情（emoji + 短話） |
| POST | `/cases/{id}/assignments` | Parent／Expert 派發（Contract = Assign）；會通知 Student 與對方成人 |
| PATCH | `/tasks/{id}` | **僅當初指派人**更新未完成任務 |
| DELETE | `/tasks/{id}` | **僅當初指派人**刪除任務 |
| POST | `/tasks/{id}/complete` | Student 標記完成；會通知 Expert 與 Parent |
| GET | `/notifications` | 目前使用者通知（可 `?unread_only=true`） |
| GET | `/notifications/unread-count` | 未讀數量（紅點） |
| POST | `/notifications/read` | 標記已讀（`{ "ids": [...] }` 或 `{}` 全部） |

請求範例需帶：`Authorization: Bearer <token>`

## 測試

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests -v
```

只跑目前版本回歸（心情札記、自訂 emoji 圖、日曆不可點、前端殼）：

```powershell
.\.venv\Scripts\python -m pytest tests/test_current_version.py tests/test_moods.py -v
```
