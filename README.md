# Perfect Co-parenting API

Expert／Parent／Student 任務指派後端（MVP）。

[開啟 CosmoMate 共育星球](https://cosmomate-production.up.railway.app/) · [線上 API 文件](https://cosmomate-production.up.railway.app/docs)

## 流程

```
Login (JWT)
  ├─ Expert → Cases → Assign（派發）
  ├─ Parent → Cases → Contract（= Assign）
  └─ Student → Cases → Execute（完成任務）
                         ↓
              Expert／Parent 查看任務進度
```

## Railway 部署

- 使用專案根目錄 `Dockerfile`（監聽 `$PORT`，預設 8080；並打包 frontend／schema）
- 正式服務從 GitHub 的 `main` 分支自動部署。
- SQLite 使用 `DATABASE_PATH=/data/app.db`，持久化磁碟掛載於 `/data`。

正式服務每日台灣時間 03:00 以 SQLite 線上備份功能建立一致性副本，存放在獨立的私有 Bucket `cosmomate-sqlite-backups`。物件路徑為 `sqlite/YYYY-MM-DD.db`。服務啟動時會檢查最近一次應執行的備份，失敗時每五分鐘重試。排程需保持服務運行。

每次備份均從 Bucket 下載到暫存目錄還原，核對 SHA-256、SQLite 完整性與外鍵。可在 Railway 服務日誌搜尋 `SQLite backup restored and verified` 查看日期與驗證結果。每日副本持續保留。若需自行檢查歷史備份，可下載對應日期的物件，以 SQLite 唯讀開啟該副本。

## 本機啟動

在 `backend` 目錄使用專案虛擬環境（不污染本機 Python）：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\uvicorn app.main:app --reload --app-dir .
```

開啟前端：http://127.0.0.1:8000/（同一網址：CosmoMate 開場 → 登入 → 儀表板）  
API 文件：http://127.0.0.1:8000/docs

本機預設使用 `backend/data/app.db`。啟動時會套用 `role_case_task_dbeaver.sql` 並初始化示範資料。可用環境變數 `DATABASE_PATH` 指定資料庫路徑。

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
