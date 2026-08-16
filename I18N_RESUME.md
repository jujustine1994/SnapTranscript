# I18N_RESUME — SnapTranscript 多語言遷移續跑筆記

分支 `feat/i18n`（**不要合併回 master，不要 push**）。
決定點裁決見 `C:\Users\CTH\Documents\Code\_i18n_migration\snaptranscript_decisions.md`。

## 現在停在哪

**批次 0 完成。** 已完成：
- `897868d` 先前未提交的 `_position_window` 改動獨立 commit（與 i18n 無關）
- `e78250b` 第 0 步：`ui.py` 兩處 `t = threading.Thread(...)` 改名 `worker_thread`

## 下一步

批次 0-b：建 `scripts/transcript_golden.py`（假 results 走真 `_write_output`，byte 比對）。

## 批次計畫

- [x] 0-a 髒工作區獨立 commit
- [x] 0   第 0 步 `t` 遮蔽改名
- [ ] 0-b `scripts/transcript_golden.py` 基準
- [ ] 1   i18n.py + 空語言檔 + config.py/config.json + 首次啟動選語言 + 主視窗 Language combobox + 重啟提示
- [ ] 2   **跳過**（輸出 TXT 段落標頭裁決為資料不翻）→ 改做 log 字串（`logtext.py`）
- [ ] 3   GUI 介面文字（**一個檔一個 commit**）
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
