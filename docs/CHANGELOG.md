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
- 單段失敗不中止整個任務，結束後可用「重試失敗的 N 段」按鈕補跑
- 自動切割的短尾巴段落併回前一段（門檻可在 UI 調整，填 0 關閉）
- 轉錄途中關視窗會跳確認框，並清掉自己的暫存檔
- 每次執行自動寫入 `logs/` 目錄的記錄檔（供事後除錯查閱，內容固定繁中）
- 介面多語言：繁體中文／简体中文／English／日本語（重開生效）

**未完成 / 待優化：**
- 超長音訊已用 2.5 小時素材測過切割與記憶體，但尚未用真實 Gemini 呼叫跑完整份
- 简中／英文／日文譯文由 AI 產出，**未經母語者校對**
- 四種語言的實際畫面尚未目視確認（版面是否被較長的英文字串擠爆、日文假名字型）
- 幾項程式碼衛生工作見 `TODO.md`「可以做但不急」

---

## 更新記錄

### 2026-08-26 — 依 windows-tool 規則整理專案目錄結構

根目錄原本堆了 9 個 `.py`、`config.json`、`locales/` 和 5 份 MD 文件，不符合
`windows-tool.md` 規定的「根目錄只留啟動器 / README / requirements」。分兩階段搬移：

- **MD 文件**搬進 `docs/`（`ARCHITECTURE.md`／`CHANGELOG.md`／`PITFALLS.md`／
  `TODO.md`），`README.md` 留根目錄。順手刪掉兩份已經沒用的舊工作檔：
  `next-session-prompt.md`（過時的交接提示詞，功能已被記憶系統取代）與
  `I18N_RESUME.md`（i18n 遷移完成紀錄，內容與本檔重疊）。
- **原始碼**（全部 `.py`、`config.json`、`locales/`）搬進 `src/`。連動修正：
  - `config.py`：`SCRIPT_DIR`（`.env` 與暫存音訊段落的存放位置）改用
    `_find_project_root()` 往上找 `launcher.ps1` 定位專案根目錄，不再等於
    `src/`；`CONFIG_PATH` 隨 `config.json` 留在 `src/`。
  - `update_checker.py`：`_SCRIPT_PATH` 同樣改成往上找專案根目錄，才找得到
    根目錄的 `scripts/check_update.ps1`。
  - `scripts/check_update.ps1`：`$CodePaths` 原本寫死根目錄的檔名清單
    （`main.py`／`ui.py`／`locales` 等），搬移後這些路徑已不存在，比對會
    靜默抓不到任何差異——改成單一 `"src"` 涵蓋全部。
  - `launcher.ps1`：`python main.py` 改成 `python src\main.py`，`__pycache__`
    清理路徑同步改成 `src\__pycache__`。
  - `tests/*.py`、`scripts/transcript_golden.py`：`sys.path` 插入點從專案根
    目錄改成 `<root>/src`。

124 個測試全過，並實際啟動 `src/main.py` 確認 GUI 正常開啟無 crash。

### 2026-08-23 — 新增「進階設定」視窗與手動檢查更新

主視窗語言列右側加一顆 ⚙ 按鈕，開啟新的「進階設定」Toplevel（目前只放版本
更新，日後其他設定項會陸續加進來，不影響現有的語言下拉選單）。視窗內含
「檢查更新」／「一鍵安裝」按鈕：`scripts/check_update.ps1` 比對本機與 GitHub
上游的差異，只碰程式碼路徑（`ui.py`／`main.py`／`i18n.py`／`locales/`／
`requirements.txt`／`launcher.ps1` 等），偵測到本機手動改過或有未 push 的
commit 會自動略過，避免覆蓋使用者的修改。全程沒有自動觸發：檢查只讀不寫，
有新版本才顯示「一鍵安裝」，按下去還要先跳確認框列出本次變更。安裝完不會
自動重啟，跳訊息框請使用者自己關閉重開。`git fetch` 一律丟到背景執行緒跑，
不卡住主視窗。四語（繁中／简中／英文／日文）介面文字同步補齊。

### 2026-08-17 — launcher.ps1 拿掉失效的 winget Python 安裝步驟

`winget install --id Python.Python.3`（不帶次版號）已被上游下架，靜默失效。改成
只檢查 uv，`uv venv venv --python 3.13` 讓 uv 自己下載 Python。步驟從 [1/4]~[4/4]
改成 [1/3]~[3/3]。ffmpeg 的 ARM64 模擬執行提醒維持不動。

### 2026-08-16（六）— 介面多語言（i18n）

介面支援 繁體中文／简体中文／English／日本語，重開生效。

- 新增 `i18n.py`（查表核心，`t()` 查不到回 key 本身不回空字串）
- 新增 `locales/{zh_tw,zh_cn,en,ja}.py`，各 **115 條** key
- `config.py` 補 `config.json` 的讀寫（`language` 預設空字串＝沒選過）
- `main.py` 首次啟動跳一次語言視窗（**刻意不翻譯**）
- `ui.py` 主視窗右上角加 `Language:` 下拉選單，改完問要不要重啟；
  原本的 grid row 0-6 整批下移為 1-7
- 搬走的字串：`ui.py` 74 條、`job.py` 12 條、`segments.py` 11 條、
  `audio.py` 5 條、`transcriber.py` 1 條
- **刻意不翻**：逐字稿段落標頭與失敗佔位符、`transcriber.PROMPT`、
  `classify_error` 的分類鍵、`logs/app.log` 全部內容（理由見 ARCHITECTURE.md
  「哪些字串不翻」）
- `job._mark_failed()` 新增 `ui_reason` 參數，把「存進 `r.error` 會寫進逐字稿
  的那條（資料，繁中）」與「推 UI 的那條（介面文字，走 t()）」拆開
- 前置修正：`ui.py` 兩處 `t = threading.Thread(...)` 改名 `worker_thread`
  ——`from i18n import t` 之後那會**靜默**遮蔽翻譯函式
- 新增 `scripts/transcript_golden.py`：逐字稿輸出的逐 byte 回歸基準
- 測試 **111 → 124**（既有 111 條一條沒改），新增 `tests/test_i18n.py` 13 條
- 驗收：繁中介面文字對遷移前逐字比對，唯一差異是新增的 Language 列本身；
  四語輸出檔 byte 完全相同；四語 GUI 殘留 key 0 條；負向驗證 6 項全數會紅

### 2026-08-10（一）— 視窗開啟位置修正 + 加寬

- 修正：視窗開啟時可能被螢幕下緣（工作列）切到，新增 `_position_window()` 於 `_build_ui()` 之後執行，置中顯示並確保底部不超出螢幕
- 調整：視窗寬度在原本自動計算的寬度上加 150px，畫面不再過窄

### 2026-08-02（日）— `_worker` 拆分 + 重試邏輯稽核

- 重構：`ui.py` 的 `_worker`（94 行）拆成四個方法，本體降到 45 行
  - `_resolve_audio_source()`：取得音訊路徑，YouTube 模式先下載；回傳 `None` 代表「只下載」模式已完成收尾
  - `_download_progress()`：yt-dlp 的進度 hook，從內嵌閉包提為方法
  - `_plan_and_announce()`：讀時長、算分段、寫任務起始行
  - `_abort()`：轉錄與補跑共用的中止收尾，把原本四段幾乎一樣的 except 分支收成一處
- 重構：`_abort(log_label=None)` 明確表達「這個錯誤已在別處落檔過」。429 由 `job.py` 在拋出前記一行，UI 端不能再記第二行——原本靠兩個 except 分支的差異隱含表達，現在是具名參數
- 實測：四條路徑逐一驗過（一般轉錄、只下載音訊、前置步驟失敗時 `_job` 仍為 `None`、轉錄中 429 中止），行為與拆分前一致，落檔內容也相同（429 仍只有一行錯誤）
- **修正：手動重試模式的錯誤行永遠寫 `重試 0/5`**。計數器只在自動分支遞增，所以未勾「自動重試」時，使用者按 1 次還是 20 次「是」，log 完全一樣，事後查不出重試過幾次；`/5` 還暗示了一個手動模式根本沒有的上限。改為自動模式維持 `重試 3/5`、手動模式寫 `手動重試 3`
- 測試：重試邏輯稽核後補 10 個測試（50 → 111 個），補齊四塊先前完全沒守著的路徑
  - 「Gemini 回傳空白結果」在 job 層的重試流程（先前所有重試測試清一色用 503，這條與 503 並列的暫時性錯誤等於裸奔）
  - 實際嘗試次數 = `MAX_AUTO_RETRIES + 1`（先前只用累計 sleep 秒數間接推斷）
  - 重試額度每段重置，前一段用掉的不會拖垮下一段
  - 手動模式無重試上限（PITFALLS 明文，先前無測試守著）、重試途中冒出 429 要立刻中止
- 調查：`requirements.txt` 鎖版本經實測認定不必要，結論與證據見 `TODO.md`；反而發現 `yt-dlp` 會永遠停在初次安裝版本，已寫成 `PITFALLS.md` 條目

### 2026-08-01（六）— 測試補強 + 短尾巴段落合併

- 新增：`segments.plan_segments()` — 自動切點計算與擷取範圍夾擠的邏輯從 `ui.py._worker` 抽出來。原本卡在 UI 執行緒函式裡，要測就得起 tkinter，所以一直沒有測試守著；現在是純函式，17 個測試涵蓋自動／自訂／範圍夾擠三類路徑
- 新增：自動切割時不足 `MIN_SEGMENT_SECONDS`（**5 分鐘**）的尾巴段落併回前一段。2 小時 33 分的音訊原本會多切出一個 3 分鐘的段落，白花一次 API 呼叫換來幾乎沒內容的逐字稿。**只作用於自動模式**——自訂切割點是使用者明確指定的位置，不該被程式合併掉
- 新增：門檻可在「切割設定」區直接調整（`└ 尾巴不足 [5] 分鐘就併入前一段`），填 0 關閉合併；選「自訂切割點」時該欄位 disable。輸入 >= 切割長度（30 分）會擋下並說明原因——合併只撤一刀，門檻過大會讓該段變成兩倍長，輸出可能超出 Gemini 的 65,536 token 上限被靜默截斷
- 新增：`segments.parse_min_segment_minutes()` 負責欄位驗證（10 個測試），以及一條掃過整個 chunk 各種尾巴長度的不變式測試，確保最長段落永遠 < 切割長度 + 門檻
- 新增：`transcribe_segment` 的 7 個測試（用假 client，不需網路或 API Key），涵蓋 PROCESSING 輪詢、非 ACTIVE 拋錯、呼叫失敗仍刪雲端檔、回傳空白結果四條路徑
- 修正：`_write_output` 寫檔失敗（磁碟滿、權限、路徑消失）時 `.tmp` 檔會留在使用者的音訊資料夾裡；改為失敗時清除後再拋出原始錯誤
- 重構：`segments.py` 兩份重複的 HH:MM:SS 正規表示式合併為模組常數 `TIME_PATTERN`
- 重構：Gemini 檔案輪詢間隔（原本寫死 2 秒）拉成 `config.FILE_UPLOAD_POLL_SECONDS`；`transcribe_segment` 新增 `sleep_fn` 測試注入點
- 修正：`get_audio_duration` 失敗時的錯誤訊息完全看不懂。音訊檔被刪除／隨身碟拔掉／選到壞檔時，使用者看到的是 `could not convert string to float: b'xxx.mp3: No such file or directory'`；改為分三種情況給明確訊息（找不到檔案／不是有效音訊／找不到 ffprobe）。同時 `stderr` 不再併進 `stdout`——原本 ffprobe 的錯誤訊息會混進要解析的數字裡
- 修正：`cut_audio_segment` 兩次嘗試都失敗時清掉殘檔。ffmpeg 失敗仍可能留下 0 byte 或半截的檔案，留著會讓 `job` 的存在性檢查誤判切割成功，接著把壞掉的音訊上傳給 Gemini
- 新增：`tests/test_audio.py`（9 個測試，用 mock 取代 `subprocess.run`，仍不需要 ffmpeg）
- 新增：轉錄進行中關閉視窗會跳確認對話框；確定關閉時清掉本行程 PID 的暫存檔。背景執行緒是 daemon，行程結束時 `_process_one` 的 finally 不會執行，原本會在專案目錄留下 27 MB 左右的殘檔，跑幾次就是好幾百 MB。清理只掃自己 PID 的前綴，不動其他實例的檔案
- 重構：暫存檔命名集中到 `job.temp_prefix_for_process()`，清理與命名不再各拼各的字串
- 修正：關閉視窗時取消 `_poll_queue` 的待處理 `after` 回呼，不再噴 `invalid command name ..._poll_queue`
- 維護：清掉 `logs/app.log` 的測試殘留（2,103 行 → 121 行）。其中 1,972 行是 2026-07-31 以前的測試沒 patch `write_log` 寫進去的假錯誤，10 行是 08-01 UI 驗證腳本的紀錄。真實使用紀錄全部保留，清理前備份於 `logs/app.log.before-clean.bak`
- 測試：從 50 個增加到 101 個
- 實測：2.5 小時 mp3（137 MB）跑完 5 段真實 ffmpeg 切割，記憶體全程穩定在 88 MB 無漂移，暫存檔每段 27.5 MB 且用完即刪、無殘留，切割總耗時 1.5 秒。轉錄用假函式，未花 API 額度
- 實測：UI 層在重構後仍走得通 — 2 小時 45 分自動切 6 段、擷取範圍 00:20:00→01:35:00 切 3 段，兩條路徑輸出檔內容與段落標題皆正確
- 實測：尾巴合併欄位四個情境（2:33:00 音訊）— 填 5 切 5 段（末段 33 分）、填 0 切 6 段（末段 3 分）、填 30 擋下並跳格式錯誤、切到自訂切割點時欄位變灰且不做合併。視窗寬度未因新欄位變寬（461px 不變）

### 2026-07-31（五）— 模組拆分 + 段落級容錯

- 重構：`main.py`（973 行）拆分為 `config.py`、`logger.py`、`segments.py`、`audio.py`、`transcriber.py`、`job.py`、`ui.py`，`main.py` 只剩程式入口
- 重構：轉錄流程抽為 `job.TranscriptionJob`，不 import tkinter，透過 callback 與 UI 溝通，可在無 GUI / 無 ffmpeg / 無網路的環境下測試
- 重構：測試從 9 個增加到 47 個，新增 `tests/test_transcriber.py`、`tests/test_job.py`
- 重構：`_log()` 移除 `to_file` 參數，落檔與推 UI 在型別上分開
- 修正：自動重試原本失敗後立刻重打，等於沒有重試效果；改為每次等待 20 秒（`RETRY_WAIT_SECONDS`），進度標籤顯示倒數
- 修正：單段轉錄失敗原本會中止整個任務，且已完成段落的逐字稿隨之丟失；改為標記該段、繼續下一段，輸出檔一律產生
- 修正：429 配額用盡仍會中止，但中止前先把已完成段落寫檔
- 新增：「重試失敗的 N 段」按鈕：轉錄結束後若有失敗段落，可只補跑那幾段，成功後原地覆寫輸出檔
- 新增：逐字稿中失敗段落以佔位符呈現，段落編號與時間範圍不變

### 2026-08-01（六）— 實測驗證

- 修正：暫存檔名加上 PID（`_temp_seg_<PID>_<段號>`）。實測時真實重現：兩支 SnapTranscript 同時跑，檔名只有段號會撞在一起，先結束的程序在 finally 清檔時把另一個程序剛切好的暫存檔刪掉，記了一行假的「切割失敗」，段落內容錯置的風險也存在
- 修正：詢問是否重試的對話框標題原本寫死「503 伺服器錯誤」，但 Gemini 回傳空白結果也走同一條路，標題會誤導；改為中性的「轉錄失敗」，實際原因寫在內文
- 修正：補跑按鈕區分「失敗」與「未處理」。429 中止時後面的段落根本沒輪到跑，原本全算成「重試失敗的 N 段」會讓人以為錯了 N 次；現在有未處理段落時顯示「繼續未完成的 N 段」，對話框也會分開列出「N 段失敗、M 段未處理」
- 測試：從 40 個增加到 50 個
- 實測：真實 Gemini 轉錄通過（英文、中文皆正確，說話者標籤可用）
- 實測：音訊格式 mp3 / m4a / wav / flac 全部通過（暫存檔副檔名正確，Gemini 皆接受）
- 實測：從 UI 層完整走過一次 — 第 2 段強制失敗後第 3 段照跑、「重試失敗的 1 段」按鈕出現、按下後只補跑該段、佔位符換成真實內容且第 1／3 段內容未變、按鈕消失
- 實測：換檔案後補跑按鈕不再殘留（原本會指向上一個音訊檔並覆寫它的逐字稿）
- 實測：擷取範圍通過（取 00:10:00→00:13:00，時間戳為原始音訊的絕對時間）
- 實測：單段失敗 → 20 秒退避重試 5 次 → 標記失敗後繼續下一段 → 佔位符 → 補跑覆寫，整條路徑通過
- 實測：落檔紀律正確（成功的任務只寫 2 行，不含逐字稿全文與 API payload）

### 2026-06-25（四）
- 新增：「擷取範圍」UI 區塊 — 勾選「只處理音訊的一部分」後可輸入起始/結束時間（HH:MM:SS），只轉錄該段範圍
- 修改：`build_segments` 改為接受範圍邊界，超出範圍的切割點自動忽略
- 新增：`parse_range` 解析起始/結束時間，格式錯誤或起始 ≥ 結束時擋下並提示
- 注意：2026-08-01 已補上 end-to-end 實測，通過

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
