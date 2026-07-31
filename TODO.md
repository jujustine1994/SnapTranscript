# TODO — SnapTranscript

## 待辦

- [x] 實際執行測試（選音訊 → 轉錄 → 輸出）— 2026-08-01 實測通過
- [x] 確認 Gemini 回應內容符合預期格式 — 中英文都正確，說話者標籤可用
- [x] 擷取範圍功能 end-to-end 實測 — 2026-08-01 用 44 分鐘 m4a 取 00:10:00→00:13:00 通過
- [ ] 測試音訊格式 wav / flac（mp3 與 m4a 已於 2026-08-01 實測通過）
- [ ] 測試超長音訊（>2 小時）的記憶體與穩定性
- [ ] 從 UI 完整點一次（目前的實測是直接呼叫 job 層，沒有真的按按鈕）

## 開發規矩

- **改完程式一定要同步更新 .md 文件**（ARCHITECTURE / README / CHANGELOG / PITFALLS）。
  2026-07-31 那輪重構事後才抓到三處失準：PITFALLS 指到已搬走的 `main.py`、
  ARCHITECTURE 寫著已更名的 `_write_log`、README 寫的啟動器檔名根本不存在。

## 可以做但不急

- `ui.py` 的自動切點計算與擷取範圍夾擠邏輯還卡在 UI 執行緒函式裡，沒有測試。
  可抽成 `segments.plan_segments(...)` 再補測試。
- `transcriber.transcribe_segment` 沒有測試。它的 `client` 是參數傳進去的，
  用假的 client 就能測「PROCESSING 輪詢」「非 ACTIVE 拋錯」「失敗仍刪檔」
  「空白結果」四條路徑，不需要網路或 API Key。
- `_write_output` 寫檔失敗時（例如磁碟滿）`.tmp` 檔會留在磁碟上不會自動清除。

## 設定步驟（首次使用）

1. 確認 ffmpeg 已安裝：在命令列執行 `ffmpeg -version`
2. 準備 Gemini API Key（從 Google AI Studio 取得）
3. 雙擊 `Run SnapTranscript.bat` → 自動建立 venv → 輸入 API Key → 開始使用
