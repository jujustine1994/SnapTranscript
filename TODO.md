# TODO — SnapTranscript

## 待辦

- [x] 實際執行測試（選音訊 → 轉錄 → 輸出）— 2026-08-01 實測通過
- [x] 確認 Gemini 回應內容符合預期格式 — 中英文都正確，說話者標籤可用
- [x] 擷取範圍功能 end-to-end 實測 — 2026-08-01 用 44 分鐘 m4a 取 00:10:00→00:13:00 通過
- [x] 測試音訊格式 — mp3 / m4a / wav / flac 全部於 2026-08-01 實測通過
- [x] 從 UI 完整走一次 — 2026-08-01 通過（含失敗→跳過續跑→補跑按鈕→補跑完成）
- [ ] 測試超長音訊（>2 小時）的記憶體與穩定性

## 已知小問題（不影響使用，可有空再修）

- `ui.py` 的詢問對話框標題寫死「503 伺服器錯誤」，但空白結果
  （`MALFORMED_RESPONSE`）那種錯誤也會用同一個標題，容易誤判原因。
  只有標題錯，內文是對的。**只有不勾「自動重試」時才會看到**。
- 429 配額用盡中止時，後面「還沒輪到跑」的段落也會被算進 `failed_count`，
  按鈕顯示成「重試失敗的 N 段」。行為是對的（按下去會把那幾段跑完），
  只是字面上會讓人以為錯了 N 次。

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
