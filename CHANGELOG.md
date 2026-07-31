# CHANGELOG — SnapTranscript

## 現狀總覽

**已完成功能：**
- tkinter 視窗介面（選檔、切割設定、API Key、進度顯示）
- 自動切割模式（每 30 分鐘）
- 自訂切割點（HH:MM:SS，每行一個）
- ffmpeg 音訊切割（優先 copy codec，失敗自動重新編碼）
- Gemini gemini-flash-latest 逐字稿
- 合併輸出含段落標記的 TXT 檔案
- API Key 自動儲存 / 讀取（.env）
- 背景執行緒處理，UI 不凍結
- YouTube 音訊下載（yt-dlp，原始最佳音質轉 mp3）
- YouTube 下載進度顯示（% + MB + 速度）
- YouTube 模式可選「下載後轉錄」或「只下載音訊（不需 API Key）」
- 擷取範圍功能（只轉錄音訊的一部分）
- 「自動重試」勾選框（503 / 空白結果自動重試，上限 5 次）
- 每次執行自動寫入 `logs/` 目錄的記錄檔（供事後除錯查閱）

**未完成 / 待優化：**
- 尚未測試實際 Gemini API 回應格式
- 尚未測試各種音訊格式（mp3 / m4a / wav）
- 擷取範圍功能未 end-to-end 實測過

---

## 更新記錄

### 2026-07-31（五）— 模組拆分 + 段落級容錯

**重構**
- `main.py`（973 行）拆分為 `config.py`、`logger.py`、`segments.py`、`audio.py`、`transcriber.py`、`job.py`、`ui.py`，`main.py` 只剩程式入口
- 轉錄流程抽為 `job.TranscriptionJob`，不 import tkinter，透過 callback 與 UI 溝通，可在無 GUI / 無 ffmpeg / 無網路的環境下測試
- 測試從 9 個增加到 40 個，新增 `tests/test_transcriber.py`、`tests/test_job.py`
- `_log()` 移除 `to_file` 參數，落檔與推 UI 在型別上分開

**修正**
- 自動重試原本失敗後立刻重打，等於沒有重試效果；改為每次等待 20 秒（`RETRY_WAIT_SECONDS`），進度標籤顯示倒數
- 單段轉錄失敗原本會中止整個任務，且已完成段落的逐字稿隨之丟失；改為標記該段、繼續下一段，輸出檔一律產生
- 429 配額用盡仍會中止，但中止前先把已完成段落寫檔

**新增**
- 「重試失敗的 N 段」按鈕：轉錄結束後若有失敗段落，可只補跑那幾段，成功後原地覆寫輸出檔
- 逐字稿中失敗段落以佔位符呈現，段落編號與時間範圍不變

### 2026-06-25（四）
- 新增：「擷取範圍」UI 區塊 — 勾選「只處理音訊的一部分」後可輸入起始/結束時間（HH:MM:SS），只轉錄該段範圍
- 修改：`build_segments` 改為接受範圍邊界，超出範圍的切割點自動忽略
- 新增：`parse_range` 解析起始/結束時間，格式錯誤或起始 ≥ 結束時擋下並提示
- 注意：此功能已合併但**未完整 end-to-end 實測過**（含實際呼叫 Gemini 轉錄該範圍音訊）

### 2026-07-16（四）
- 新增：「自動重試」勾選框（位於「開始轉錄」按鈕右側），勾選後 503 / Gemini 回傳空白結果（`MALFORMED_RESPONSE` 等）時自動重試，不再跳出詢問 dialog；單段最多自動重試 `MAX_AUTO_RETRIES`（5）次，超過仍失敗才中止該段，避免無限重試耗用 API 配額
- 不勾選時維持原本互動式 dialog 行為（見 2026-04-17 記錄）
- 新增：每次按「開始」在 `logs/` 目錄建立一份記錄檔（`snaptranscript_<時間戳>.log`），內容與視窗內 log 同步，每行加時間戳、檔尾加「結果：成功／失敗＋耗時」總結行，供事後除錯查閱；刻意不記錄逐字稿全文與 API 完整 payload；`logs/` 已加入 `.gitignore`

### 2026-06-10（三）
- 修正：`winget install Python` 加入 `PrependPath=1 Include_pip=1`，確保 Python 安裝後自動加進 PATH（原本 `--silent` 模式預設不加）
- 修正：Python 安裝完但 PATH 尚未生效時，誤顯示 `[OK]` 訊息 → 改為 `[INFO]` 並說明需重開視窗
- 修正：`launcher.ps1` 加入全域 `trap`，攔截未處理例外，防止執行失敗時視窗直接閃退

### 2026-05-20（三）
- 修正：Gemini 回傳 `response.text = None` 時，程式崩潰（`'NoneType' object has no attribute 'strip'`）→ 改為拋出明確錯誤訊息，包含 `finish_reason`
- 新增：`response.text = None` 錯誤同樣觸發互動式 retry dialog（與 503 行為一致）

### 2026-04-17（五）
- 修改：Gemini API 503 改為互動式 retry — log 顯示 `[ERROR] 503 UNAVAILABLE`，跳出 dialog 詢問是否重試，可無限重試直到成功或使用者取消

### 2026-03-17（一）— UI 改進
- 修改：API Key 安全提示改為獨立換行顯示，不再與「記住」勾選框擠同一行
- 新增：YouTube 只下載模式時，切割設定與 API Key 區塊自動 dim（disabled），減少視覺雜訊
- 新增：完成後顯示「開啟資料夾」按鈕，點擊直接開啟 Explorer 至輸出位置
- 新增：Log 區域初始顯示引導文字
- 修改：視窗寬度縮小（API Key 欄位 50→40、Log 區域 66→56 字元）

### 2026-03-17（一）
- 新增：YouTube 音訊下載功能（yt-dlp，原始最佳音質轉 mp3）
- 新增：音訊來源切換 — 本地上傳 / YouTube 下載（radio button）
- 新增：YouTube 模式可選「下載後馬上轉錄」或「只下載音訊（不需 API Key）」
- 新增：YouTube 下載使用「另存新檔」對話框，可自訂儲存位置與檔名
- 新增：下載進度即時顯示（進度條 + 百分比 + 已下載 MB / 總 MB + 速度）
- 新增：啟動按鈕依模式動態改名（「開始轉錄」/ 「開始下載」）
- 修改：launcher.ps1 加入 yt-dlp 安裝說明
- 修改：launcher.ps1 每次啟動自動補裝缺少套件，並清理損壞的 dist-info

### 2026-03-16（一）
- 新增：launcher.ps1 加入系統架構偵測（`$isArm64`）
- 新增：ARM64 電腦找不到 Python 時，顯示警告訊息引導移除舊版 x64 再重裝
- 新增：ffmpeg 在 ARM64 安裝完成後提示「x64 版透過模擬執行，功能正常但速度略慢」

### 2026-03-12（三）
- 新增：launcher.ps1 自動安裝 ffmpeg（winget `Gyan.FFmpeg`），步驟從 3 步擴充為 4 步
- 修改：每個缺少的元件加上說明文字，告知用途與影響
- 修改：每次成功安裝後加 pause，讓使用者確認後再繼續
- 修改：Python / ffmpeg 需重開視窗時，補充說明 Windows PATH 更新機制

### 2026-03-12（二）
- 修改：預設切割間隔從 20 分鐘改為 30 分鐘
- 文件：ARCHITECTURE.md 補充 token 限制設計決策（輸出 token 才是切割關鍵原因）

### 2026-03-12（一）
- 新增：「如何取得 API Key？」說明彈窗（含申請步驟、Google AI Studio 連結、Free tier 注意事項）
- 新增：README 補充 API Key 申請教學段落
- 修改：「如何取得 API Key？」改為文字連結樣式，與「開始轉錄」主按鈕區隔視覺層級
- 修改：「開始轉錄」按鈕加大高度
- 修改：音訊檔案 Entry 改為自動撐滿寬度（grid layout）
- 修改：處理進度區塊底部補充間距，避免框線被截斷

### 2026-03-11
- 新增：專案初始建置，完成所有基礎功能
- 修改：Gemini prompt 改為原文轉錄，不再強制翻譯成繁體中文
