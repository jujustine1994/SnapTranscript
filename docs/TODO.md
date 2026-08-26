# TODO — SnapTranscript

## 待辦

- [ ] **實測 GitHub Release 發布流程**（2026-08-26 加）。首次用本專案照
      `~/.claude/project-rules/windows-tool/windows-tool-release.md` SOP 跑一次
      完整發布（`git archive` 打包 → 建 tag → `gh release create`），驗證使用者
      體驗「下載 zip → 解壓 → 雙擊啟動器」全程可行。視實測結果回頭更新母資料夾
      SOP 文件（發現遺漏或跟現況不符的步驟）
- [x] 實際執行測試（選音訊 → 轉錄 → 輸出）— 2026-08-01 實測通過
- [x] 確認 Gemini 回應內容符合預期格式 — 中英文都正確，說話者標籤可用
- [x] 擷取範圍功能 end-to-end 實測 — 2026-08-01 用 44 分鐘 m4a 取 00:10:00→00:13:00 通過
- [x] 測試音訊格式 — mp3 / m4a / wav / flac 全部於 2026-08-01 實測通過
- [x] 從 UI 完整走一次 — 2026-08-01 通過（含失敗→跳過續跑→補跑按鈕→補跑完成）
- [x] 測試超長音訊（>2 小時）的記憶體與穩定性 — 2026-08-01 用 2.5 小時 mp3 實測，
      記憶體全程 88 MB 無漂移、暫存檔無殘留，數據記在 `ARCHITECTURE.md`
      「超長音訊實測數據」。轉錄用假函式，未花 API 額度
- [ ] 超長音訊用真實 Gemini 呼叫跑完整份（會花 5+ 次額度，想驗證連續呼叫的穩定性再做）

### 多語言（i18n）2026-08-16 遷移後留下的

- [ ] **四種語言各開一次視窗目視確認版面**。程式面已驗（四語建置成功、
      殘留 key 0 條），但**沒有人看過實際畫面**。兩個具體風險：
      ① `ui.py` 的 `output_label` 寫死 `wraplength=220`（為了讓「開啟資料夾」
      與「重試失敗的 N 段」兩顆按鈕能並排），英文的
      "Retry 3 failed segment(s)" 比中文長約一倍，可能把那一列擠爆。
      擠爆的話直接調大那個數值即可（純版面數值）
      ② 日文假名的字型。目前**刻意不指定字型**（`i18n.ui_font()` 建了但不
      呼叫），因為指定下去會改變繁中的既有外觀。若日文出現豆腐或字形怪異，
      做法是**只對 `ja`** 套 Yu Gothic，繁中維持不動
- [ ] **简中／英文／日文譯文請母語者校對**。三份都是 AI 產出。改
      `locales/*.py` 的 value 不影響任何邏輯（程式一律用 key 比對），但
      **不要動 key**，具名 placeholder（`{path}`、`{count}`…）要原樣保留，
      否則 `tests/test_i18n.py` 會紅。可疑的幾條：
      - `gui.msg.list_sep`：英文用 `", "`、其餘用「、」
      - `gui.btn.retry_failed_n` 英文用 "segment(s)" 迴避單複數
      - `gui.lbl.min_seg_prefix` / `min_seg_suffix` 是一句話被輸入框切成
        前後兩半，英文語序跟中文不同，實際排出來可能不通順
- [ ] **非繁中語言下，有三類訊息仍顯示繁體中文**（刻意的，但使用者會覺得怪）：
      `transcriber.classify_error` 回傳的「Gemini 伺服器回傳 503」與
      「Gemini 回傳空白結果」（是分類鍵＝資料，見 PITFALLS）、
      逐字稿檔案裡的段落標頭與失敗佔位符、以及 `r.error` 的內容。
      要修的話得先把 `classify_error` 改成用機器可讀的代碼分類（例外子類別
      或 sentinel），那是邏輯變更，2026-08-16 明確判定不在 i18n 範圍內

- [x] 對話框標題不再寫死「503 伺服器錯誤」（2026-08-01 修，改為中性的「轉錄失敗」）
- [x] 補跑按鈕區分「失敗」與「未處理」（2026-08-01 修）

## 開發規矩

- **改完程式一定要同步更新 .md 文件**（ARCHITECTURE / README / CHANGELOG / PITFALLS）。
  2026-07-31 那輪重構事後才抓到三處失準：PITFALLS 指到已搬走的 `main.py`、
  ARCHITECTURE 寫著已更名的 `_write_log`、README 寫的啟動器檔名根本不存在。

## 已完成的程式碼衛生工作

**2026-08-01**

- [x] 自動切點計算與擷取範圍夾擠邏輯抽成 `segments.plan_segments()`，補 17 個測試
- [x] `transcriber.transcribe_segment` 補 7 個測試（假 client，不需網路）
- [x] `_write_output` 寫檔失敗時清除殘留的 `.tmp`
- [x] `segments.py` 兩份重複的 HH:MM:SS 正規表示式合併為 `TIME_PATTERN`
- [x] `audio.get_audio_duration` 失敗時給看得懂的錯誤訊息（原本是
      `could not convert string to float`）
- [x] `cut_audio_segment` 兩次都失敗時清掉殘檔

**2026-08-02**

- [x] `ui.py` 的 `_worker`（94 行）拆成 `_resolve_audio_source` /
      `_download_progress` / `_plan_and_announce` / `_abort`，本體降到 45 行
- [x] 關視窗時 `after_cancel` 掉 `_poll_queue` 的待處理回呼
- [x] 重試邏輯稽核：修掉手動模式錯誤行永遠寫「重試 0/5」的缺陷，
      並補上先前沒測到的四塊路徑（空白結果重試、實際嘗試次數、
      每段額度重置、手動模式無上限與重試中 429）

## 目錄結構不符全域規範（2026-08-16 確認，刻意不動）

`windows-tool.md` 要求 `.py` 收進 `src/`、MD 文件收進 `docs/`。本專案的
`.py` 與 `README/ARCHITECTURE/CHANGELOG/PITFALLS/TODO` 全部在根目錄。

搬移本身不難（`logger._find_project_root()` 往上找 `launcher.ps1`，兩種擺法
都正確，日後搬 `src/` 不會壞），但要同步改 `launcher.ps1` 的呼叫路徑、
`tests/*.py` 的 `sys.path.insert`、以及 `tests/test_i18n.py` 的 `SKIP_DIRS`。
i18n 遷移期間刻意不做——混進來會讓那次的 diff 沒法看。

順帶：`tests/` 缺 `__init__.py`（規範有列，目前靠各測試自己
`sys.path.insert` 也能跑）。

## 順手發現、還沒動的

- `ui.py` 的 `_abort()` 用 `self._log(f"
[ERROR] {e}")` 把例外物件整包推進
  UI 記錄框。落檔那條已經正確（只記 `type(e).__name__`），但 UI 這條若是
  google-genai 的例外，畫面上會出現完整 URL 與 response 片段——使用者截圖
  求助時就外流了。規範只管落檔，這條不違規，但值得修
- `docs/next-session-prompt.md` 與 `.superpowers/sdd/` 留了一堆上次 SDD 流程
  的中間檔（review diff、task brief/report），沒清

## 設定介面現況

目前**沒有設定 tab**，視窗是單一頁面（音訊來源／擷取範圍／切割設定／API Key／進度）。
可調參數的分工是：

- 「尾巴合併門檻」有 UI 欄位（切割設定區），`config.MIN_SEGMENT_SECONDS` 只是預設值
- 其餘（`DEFAULT_CHUNK_SECONDS`、`MAX_AUTO_RETRIES`、`RETRY_WAIT_SECONDS`、
  `FILE_UPLOAD_POLL_SECONDS`）仍只能改 `config.py`

之後若想把更多參數搬上 UI，2026-08-01 討論過的做法是加 `ttk.Notebook`「進階設定」
分頁，把設定存進 `.env` 或新的 settings 檔。當時選了「只加單一欄位」的最小做法，
因為只有尾巴門檻這一項使用者會想常態調整。

## requirements.txt 鎖版本 —— 2026-08-02 調查後決定「不做」

原本 08-01 判斷要鎖，理由是「每次啟動都跑 `uv pip install -r`，套件改版會把
程式弄壞」。**這個前提經實測是錯的，所以整件事取消。**

### 實測證據

**1. `uv pip install -r` 不會升級已安裝的套件。**
建乾淨 venv → 裝 `python-dotenv==1.0.0` → 用未鎖版本的 requirements 跑
`uv pip install -r`（跟 `launcher.ps1` 一模一樣，沒有 `--upgrade`）→
版本仍是 1.0.0。所以日常啟動完全不會動到已裝好的版本，「哪天啟動就壞掉」
不會發生。

**2. 唯一會變版本的時機是「從零重建 venv」**，也就是換機器、手動刪掉 `venv/`，
或 PITFALLS 那條 dist-info 損壞的清理路徑。

**3. 真的重建的話，會裝到 `google-genai` 2.16.0（現在裝的是 1.66.0）。**
主版本 2.x 已經發行。針對這點實際驗過相容性：

| 檢查項目 | 結果 |
|----------|------|
| `genai.Client(api_key=)` | 在 |
| `client.files.upload / get / delete` | 在，參數名未變 |
| `client.models.generate_content(model=, contents=)` | 在 |
| `File.state` / `File.name` / `FileState.PROCESSING`/`ACTIVE` | 在 |
| `Response.text` / `Response.candidates` / `Candidate.finish_reason` | 在 |
| 用 2.16.0 跑專案 101 個測試 | 全過 |

**結論：不鎖也不會壞。** 鎖了反而要記得日後手動解鎖。

### 但有一個相反方向的問題要注意

因為 `uv pip install -r` 從不升級，**`yt-dlp` 會永遠停在第一次安裝的版本**。
目前裝的是 2026.3.13，PyPI 上已經到 2026.7.4（差四個月）。YouTube 一改前端，
舊版 yt-dlp 就下載失敗，而啟動器不會自動幫你更新。

**YouTube 下載突然壞掉時，先做這件事：**

```powershell
uv pip install --upgrade yt-dlp --python venv\Scripts\python.exe
```

這比鎖版本重要得多——鎖版本防的是不會發生的事，這條防的是遲早會發生的事。

### 沒有採用的做法

`uv pip compile` 產完整 lockfile：對 3 個直接相依的專案太重，而且會把 `yt-dlp`
也鎖死，跟上面那條衝突。

## 可以做但不急

- `transcriber.PROMPT` 仍放在 `transcriber.py`，沒有搬進 `config.py`。它算是可調參數，
  但搬過去只是換位置、不會讓它更好調（真要調的是內容，那會直接影響逐字稿品質）。
  暫時維持現狀。
- 目前沒有其他已知的程式碼衛生問題。

## 設定步驟（首次使用）

1. 確認 ffmpeg 已安裝：在命令列執行 `ffmpeg -version`
2. 準備 Gemini API Key（從 Google AI Studio 取得）
3. 雙擊 `Run SnapTranscript.bat` → 自動建立 venv → 輸入 API Key → 開始使用
