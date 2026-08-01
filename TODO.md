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

## 可以做但不急

- `ui.py` 的 `_worker` 仍然偏長（下載、分段、建立 job、三個 except 分支都在裡面）。
  分段那塊已經抽走了，剩下的要再拆得先想清楚 UI 狀態怎麼傳，暫時不動。
- ~~`audio.py` 的 `get_audio_duration` 沒有處理 ffprobe 失敗~~ — 2026-08-01 修好了
- 關視窗時 `_poll_queue` 還掛著一個 `root.after(100, ...)`，Tk 可能在關閉瞬間
  印出 `invalid command name ..._poll_queue`。實測只在同一個行程建立多個 Tk root
  時看得到（測試腳本），正常使用是單一 root 且緊接著行程結束，沒有實際影響。
  真要修就是在關閉時記下 after id 並 `after_cancel`。

## 設定步驟（首次使用）

1. 確認 ffmpeg 已安裝：在命令列執行 `ffmpeg -version`
2. 準備 Gemini API Key（從 Google AI Studio 取得）
3. 雙擊 `Run SnapTranscript.bat` → 自動建立 venv → 輸入 API Key → 開始使用
