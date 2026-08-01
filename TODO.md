# TODO — SnapTranscript

## 待辦

- [x] 實際執行測試（選音訊 → 轉錄 → 輸出）— 2026-08-01 實測通過
- [x] 確認 Gemini 回應內容符合預期格式 — 中英文都正確，說話者標籤可用
- [x] 擷取範圍功能 end-to-end 實測 — 2026-08-01 用 44 分鐘 m4a 取 00:10:00→00:13:00 通過
- [x] 測試音訊格式 — mp3 / m4a / wav / flac 全部於 2026-08-01 實測通過
- [x] 從 UI 完整走一次 — 2026-08-01 通過（含失敗→跳過續跑→補跑按鈕→補跑完成）
- [x] 測試超長音訊（>2 小時）的記憶體與穩定性 — 2026-08-01 用 2.5 小時 mp3 實測，
      記憶體全程 88 MB 無漂移、暫存檔無殘留，數據記在 `ARCHITECTURE.md`
      「超長音訊實測數據」。轉錄用假函式，未花 API 額度
- [ ] 超長音訊用真實 Gemini 呼叫跑完整份（會花 5+ 次額度，想驗證連續呼叫的穩定性再做）

- [x] 對話框標題不再寫死「503 伺服器錯誤」（2026-08-01 修，改為中性的「轉錄失敗」）
- [x] 補跑按鈕區分「失敗」與「未處理」（2026-08-01 修）

## 開發規矩

- **改完程式一定要同步更新 .md 文件**（ARCHITECTURE / README / CHANGELOG / PITFALLS）。
  2026-07-31 那輪重構事後才抓到三處失準：PITFALLS 指到已搬走的 `main.py`、
  ARCHITECTURE 寫著已更名的 `_write_log`、README 寫的啟動器檔名根本不存在。

## 已完成的程式碼衛生工作（2026-08-01）

- [x] 自動切點計算與擷取範圍夾擠邏輯抽成 `segments.plan_segments()`，補 17 個測試
- [x] `transcriber.transcribe_segment` 補 7 個測試（假 client，不需網路）
- [x] `_write_output` 寫檔失敗時清除殘留的 `.tmp`
- [x] `segments.py` 兩份重複的 HH:MM:SS 正規表示式合併為 `TIME_PATTERN`

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

- `ui.py` 的 `_worker` 仍然偏長（下載、分段、建立 job、三個 except 分支都在裡面）。
  分段那塊已經抽走了，剩下的要再拆得先想清楚 UI 狀態怎麼傳，暫時不動。
- ~~`audio.py` 的 `get_audio_duration` 沒有處理 ffprobe 失敗~~ — 2026-08-01 修好了
- ~~關視窗時 `_poll_queue` 的 `after` 回呼會噴 `invalid command name`~~ —
  2026-08-01 隨關窗處理一起修（`_on_close` 會 `after_cancel`）

## 設定步驟（首次使用）

1. 確認 ffmpeg 已安裝：在命令列執行 `ffmpeg -version`
2. 準備 Gemini API Key（從 Google AI Studio 取得）
3. 雙擊 `Run SnapTranscript.bat` → 自動建立 venv → 輸入 API Key → 開始使用
