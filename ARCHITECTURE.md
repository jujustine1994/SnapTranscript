# SnapTranscript — 架構說明

## 工具總覽

會議音訊逐字稿工具。支援本地音訊上傳或 YouTube 音訊下載，分段切割後透過 Gemini 轉錄，合併輸出 TXT。

## 檔案清單

| 檔案 | 用途 |
|------|------|
| `Run SnapTranscript.bat` | 薄殼啟動器：只呼叫 launcher.ps1 |
| `launcher.ps1` | 環境檢查、首次安裝說明、建立 venv、啟動主程式 |
| `main.py` | 程式入口：banner + Tk root |
| `config.py` | 全域常數（模型、切割長度、重試設定） |
| `logger.py` | `logs/app.log` 落檔 |
| `segments.py` | 時間字串解析 + 分段計算（純函式） |
| `audio.py` | ffprobe 取時長 / ffmpeg 切割 / yt-dlp 下載 |
| `transcriber.py` | Gemini 呼叫、prompt、錯誤分類 |
| `job.py` | 轉錄流程編排（不 import tkinter，可獨立測試） |
| `ui.py` | `SnapTranscriptApp` 主視窗 |
| `tests/` | unittest 測試（`python -m unittest discover -s tests`） |
| `requirements.txt` | Python 套件清單（google-genai、python-dotenv、yt-dlp） |
| `.env` | API Key 儲存（不進版控） |
| `.gitignore` | 排除 venv、.env、暫存檔 |

## 執行流程

```
Run SnapTranscript.bat
  └─ launcher.ps1
        └─ 環境檢查（Python / uv / ffmpeg / venv）
        └─ tkinter 視窗啟動
              ├─ 選音訊來源
              │     ├─ 【本地上傳】選取音訊檔
              │     └─ 【YouTube 下載】輸入網址 + 另存新檔對話框
              │           ├─ 下載後馬上轉錄
              │           └─ 只下載音訊（不需 API Key）→ 下載完結束
              ├─ 選切割模式（自動 30 分 / 自訂 HH:MM:SS）
              ├─ 擷取範圍（可選）：只處理音訊的一部分（起始/結束 HH:MM:SS）
              ├─ 輸入 / 確認 API Key
              ├─ 自動重試（可選）：勾選後 503 / 空白結果自動重試，不再跳詢問 dialog
              └─ 按「開始」→ 背景執行緒
                    ├─ [YouTube 模式] yt-dlp 下載音訊（原始最佳音質轉 mp3）
                    ├─ ffprobe 取得音訊總時長
                    ├─ 建立分段清單 [(start, end), ...]（限制在擷取範圍內）
                    └─ 逐段處理（job.TranscriptionJob）：
                          ├─ ffmpeg 切割暫存檔
                          ├─ genai.upload_file 上傳
                          ├─ gemini-flash-latest 轉錄
                          │     └─ 失敗（503 / 空白結果）→ 依「自動重試」設定：
                          │           勾選＝等 RETRY_WAIT_SECONDS 秒後重試，
                          │                 至多 MAX_AUTO_RETRIES 次
                          │           未勾選＝跳 dialog 詢問使用者
                          │     └─ 重試耗盡 / 使用者放棄 → 標記該段失敗，繼續下一段
                          │     └─ 429 配額用盡 → 中止，但已完成段落先寫檔
                          └─ 刪除暫存檔
                    └─ 合併所有段落 → 輸出 _transcript.txt
                          （失敗段落寫佔位符，不因此少一段）
                    └─ 有失敗段落 → UI 顯示「重試失敗的 N 段」按鈕
                          └─ 按下只補跑失敗段落，成功後原地覆寫輸出檔
```

## Log / 錯誤紀錄

單一累積檔 `logs/app.log`（`_find_project_root()` 往上找 `launcher.ps1` 所在目錄定位專案根目錄，主程式在根目錄或 `src/` 都對），不分次建立新檔，執行期間持續累加、不自動清除。`LOG_DIR`/`LOG_FILE` 為模組層級常數，`_write_log(msg, level="INFO")` 每次開檔→寫→關檔、不持有 handle。

落檔只有三種情況，由呼叫端顯式傳 `to_file=True` 觸發（`_log()` 預設 `to_file=False`，是刻意的 fail-closed 設計：漏帶旗標的後果是少記一行，不是把不該落檔的東西寫上磁碟）：
1. **任務起始**（`_init_log_file` → `_write_log_header`）：唯一有完整日期的行，格式 `=== YYYY-MM-DD HH:MM:SS <task_desc> ===`
2. **錯誤行**（`_write_log(msg, "ERROR")`）：例如轉錄中止時記 `type(e).__name__` 與 HTTP 狀態，不寫完整例外堆疊
3. **任務結果**（`_finalize_log_file` → `_write_log`）：成功/失敗 + 耗時，level 為 `OK`/`FAIL`

一般行格式：`[HH:MM:SS] [LEVEL] msg`（level 靠左對齊 5 字元寬）。其餘進度／中間步驟（讀取音訊、上傳、分段完成等）一律不落檔，只推 UI queue 顯示。

範例：
```
=== 2026-07-16 14:18:14 逐字稿 6640.m4a | 共 3 段 ===
[14:18:15] [ERROR ] 轉錄中止 -> ClientError | HTTP 429 配額用盡
[14:18:15] [FAIL  ] 失敗，耗時 0分1秒
```

刻意**不記錄**：逐字稿全文（內容可能機密、對除錯無幫助）、API 完整 request/response payload（太細，判斷不出根因）、音訊檔案大小等原始資料（目前沒有觀察到相關規律）。

> **AI 注意（除錯用，平常不用管）：** 使用者回報「轉錄失敗」「常常出錯」等問題時，先去 `logs/app.log` 翻閱**檔尾附近**的內容（累積檔，最新記錄在最後），比只看使用者截圖更完整。平常維護、開發新功能時不需要主動查閱或提及這個目錄。

拆分為模組後，「推 UI」與「落檔」在型別上就是分開的兩件事：`job.py` 用
`JobCallbacks.log()` 推 UI、用 `logger.write_log()` 落檔，不再需要靠
`to_file=False` 預設值防呆。`ui.py` 的 `_log()` 退化為單純的 UI 推送包裝。

段落級失敗新增一種錯誤行：`第N段 最終失敗 -> <status>`，在單段重試耗盡或
使用者放棄重試時寫入。

## 關鍵設定變數（config.py）

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `DEFAULT_CHUNK_SECONDS` | 1800（30分） | 自動切割間隔 |
| `MODEL_NAME` | `gemini-flash-latest` | Gemini 模型 |
| `ENV_PATH` | `<專案根目錄>/.env` | API Key 儲存位置 |
| `MAX_AUTO_RETRIES` | 5 | 勾選「自動重試」時，單段最多自動重試次數 |
| `RETRY_WAIT_SECONDS` | 20 | 自動重試前的固定等待秒數 |

## 輸出格式

### 逐字稿（本地上傳 / YouTube 下載後轉錄）

```
=== 第 1 段（00:00:00 - 00:30:00）===

[逐字稿內容...]

=== 第 2 段（00:30:00 - 01:00:00）===

[逐字稿內容...]
```

轉錄失敗的段落不會消失，改寫佔位符，段落編號與時間範圍照常：

```
=== 第 2 段（00:30:00 - 01:00:00）===

[此段轉錄失敗：Gemini 伺服器回傳 503，已自動重試 5 次仍失敗，可於程式內重試]
```

按 UI 的「重試失敗的 N 段」補跑成功後，佔位符會被真實逐字稿取代，原地覆寫同一個檔案。

輸出路徑：
- **本地上傳**：與音訊檔同目錄，檔名加上 `_transcript.txt` 後綴
- **YouTube 下載後轉錄**：與下載音訊同目錄，檔名加上 `_transcript.txt` 後綴
- **YouTube 只下載**：只輸出 mp3，無逐字稿

## YouTube 下載設計

- 使用 `yt-dlp`，格式選擇 `bestaudio/best`，postprocessor 轉 mp3
- 存檔路徑由「另存新檔」對話框決定，使用者可自訂位置與檔名
- 下載進度透過 progress hook 回傳至 UI（%、MB、速度）
- Token 計算以音訊時長為準，與 mp3 bitrate 無關（32 tokens/秒）

## 切割設計決策：為何切 30 分鐘

### 模型規格（`gemini-flash-latest`）

本專案一律使用 `gemini-flash-latest`：指向 Gemini Flash 系列最新版本的別名，自動熱切換（可能是穩定版、預覽版或實驗版），無需手動更新模型 ID。

下表以目前別名指向版本的規格為參考基準，實際限制以 Google 官方文件為準：

| 限制 | 數值 |
|------|------|
| 最大輸入 tokens | 1,048,576（約 11 小時音訊） |
| 最大輸出 tokens | 65,536 |

### 為何需要切割（輸出 token 是關鍵）

輸入限制幾乎不是問題（11 小時容量遠超一般會議），但**輸出 token 上限才是真正的瓶頸**。

快速中文語速約 300~400 字/分鐘，換算 token：

| 會議長度 | 估計輸出 tokens | 是否安全 |
|----------|----------------|----------|
| 30 分鐘  | ~18,000        | ✅ 安全（上限 27%）|
| 60 分鐘  | ~36,000        | ✅ 安全（上限 55%）|
| 90 分鐘  | ~54,000        | ⚠️ 接近邊緣 |
| 120 分鐘 | ~72,000        | ❌ 超出上限 |

### 為何選 30 分鐘而非整份送出

- 每段輸出約 18,000 tokens，僅用上限的 27%，有充裕緩衝
- 若某段 API 呼叫失敗，只需重跑該段，不需重跑整份
- 缺點：段落接縫處可能有少量遺漏，說話者標籤在不同段落間可能不一致

### 暫存檔

- 格式：`_temp_seg_0.mp3`（與音訊同副檔名）
- 位置：專案根目錄
- 處理完畢自動刪除，異常退出也會在 finally 清除
