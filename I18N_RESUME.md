# I18N_RESUME — SnapTranscript 多語言遷移續跑筆記

分支 `feat/i18n`（**不要合併回 master，不要 push**）。
決定點裁決見 `C:\Users\CTH\Documents\Code\_i18n_migration\snaptranscript_decisions.md`。

## 現在停在哪

**批次 3（ui.py）完成。** 已完成：
- `897868d` 先前未提交的 `_position_window` 改動獨立 commit（與 i18n 無關）
- `e78250b` 第 0 步：`ui.py` 兩處 `t = threading.Thread(...)` 改名 `worker_thread`
- `12fe19f` `scripts/transcript_golden.py`（繁中基準 525 bytes / sha256 `67ff5089`）
- `6771e24` 批次 1：i18n.py、空語言檔、config schema、Language combobox、首次啟動選語言
- `a475722` 批次 3：`ui.py` 74 處字面走 t()，14 條 log 字面留原地

## 下一步

批次 4：`job.py` → `segments.py` → `audio.py` → `transcriber.py` 的錯誤訊息，
**一個檔一個 commit**。job.py 的 `_mark_failed` 難題見下方。

## 批次計畫

- [x] 0-a 髒工作區獨立 commit
- [x] 0   第 0 步 `t` 遮蔽改名
- [x] 0-b `scripts/transcript_golden.py` 基準
- [x] 1   i18n.py + 空語言檔 + config.py/config.json + 首次啟動選語言 + 主視窗 Language combobox + 重啟提示
- [x] 2   **跳過**（輸出 TXT 段落標頭裁決為資料不翻；log 字串留原地靠精確豁免集合放行，禁止抽 logtext.py）
- [x] 3   GUI 介面文字（ui.py 完成；job/segments/audio 的字串併入批次 4）
- [ ] 4   錯誤訊息（segments / audio / job）
- [ ] 5   简中／英／日譯文
- [ ] 6   三道防退化測試（unittest + subTest）+ 文件

## 硬性約束備忘

- 測試基準 **111 條**，指令 `./venv/Scripts/python.exe -m unittest discover -s tests -v`
- 繁中行為必須與改前完全一樣
- 輸出 `_transcript.txt` 的 `=== 第 N 段（...）===` 與 `[此段轉錄失敗：...]` **不翻**（資料）
- `transcriber.PROMPT`、`classify_error` 的 `"Gemini 回傳空白結果"` **不翻、不改邏輯**
- log 內容固定繁中
- ALLOWLIST 用**精確字串豁免集合**，不整檔豁免 `ui.py` / `job.py`
- 逐檔 `git add`，不要 `git add -A`
- GUI smoke test 可用「共用隱藏 root + 每語言一個 Toplevel」（`SnapTranscriptApp`
  收 `root` 參數、不是 `class App(tk.Tk)`，所以 lessons 6-b 的子行程解法用不上）

## 批次 4 的已知難題（`job._mark_failed`）

`reason` 這條字串**同時**推 UI（要翻）與存進 `r.error`，而 `r.error` 會被
`_write_output` 寫進 `_transcript.txt` 的失敗佔位符（**是資料，不翻**）。
做法：`_mark_failed(r, status, ui_reason, log_reason)` 一次拆兩路——UI 走 `t()`，
存進 `r.error` 的固定繁中。這是 lessons 第 13 條的形狀，簽名改動要**同一個
commit** 改完呼叫端（lessons 第 15 條）。
