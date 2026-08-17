# I18N_RESUME — SnapTranscript 多語言遷移（**已完成**）

分支 `feat/i18n`。**尚未合併回 master，也沒有 push**——由使用者自己看過再合。

遷移日期：2026-08-16。裁決依據：
`C:\Users\CTH\Documents\Code\_i18n_migration\snaptranscript_decisions.md`。

---

## 結果

介面支援 **繁體中文／简体中文／English／日本語**，重開生效。
母表 **115 條 key**，四語 key 集合與 placeholder 完全一致。
測試 **111 → 124**（既有 111 條**一條都沒改**）。

## commit 列表（依序）

| commit | 內容 |
|---|---|
| `897868d` | 先前未提交的 `_position_window` 改動獨立 commit（與 i18n 無關） |
| `e78250b` | 第 0 步：`ui.py` 兩處 `t = threading.Thread(...)` 改名 `worker_thread` |
| `12fe19f` | `scripts/transcript_golden.py` 逐字稿逐 byte 基準 + 本檔 |
| `6771e24` | 批次 1：`i18n.py`、空語言檔、config schema、Language combobox、首次啟動選語言 |
| `a475722` | 批次 3：`ui.py` 74 處字面走 `t()` |
| `ec7f1ed` | 批次 4a：`job.py` 12 條，`_mark_failed` 加 `ui_reason` |
| `6d1ec90` | 批次 4b：`segments.py` 11 條、`audio.py` 5 條、`transcriber.py` 1 條 |
| `a303ab7` | 批次 5：简中／英文／日文譯文 |
| `e61ffbb` | 批次 6：七道防退化測試（unittest + subTest） |

（批次 2「輸出檔顯示文字」整批跳過——逐字稿的段落標頭裁決為資料，不翻。）

## 驗收結果

| 項目 | 結果 |
|---|---|
| 完整測試 | 111 → **124**，全綠 |
| 四語 GUI 建置 | 四語各 39 條 widget 文字，**殘留 key 0 條** |
| 繁中行為不變 | 介面文字對遷移前逐字比對，**唯一差異是新增的 Language 列本身** |
| 輸出檔 | 四語 byte 完全相同（`sha256 7d652917…`）；`r.error` 四語相同 |
| key / placeholder | 四語各 115 條，集合與 placeholder 逐條一致 |
| 首次啟動視窗 | 開得起來、點下去有存檔、第二次不再跳（測試涵蓋） |
| 負向驗證 | 6 項全數會紅（見下） |

負向驗證（做完都已還原，`git status` 乾淨）：
塞寫死中文常數 ✅紅／刪 `ja.py` 一個 key ✅紅／塞 `t` 區域變數 ✅紅／
打錯 placeholder ✅紅／PROMPT 跟著語言走 ✅抓得到／關掉語言切換 ✅紅。

## 之後要記得的事

- **語言檔未經母語者校對**，改 `locales/*.py` 的 value 不影響邏輯，
  但不要動 key、要保留具名 placeholder
- **四種語言的實際畫面還沒有人目視確認**（版面、日文字型）
- 詳細待辦見 `TODO.md`「多語言（i18n）2026-08-16 遷移後留下的」
- 不翻的字串與理由見 `ARCHITECTURE.md`「多語言（i18n）」章節
- 踩到的三個坑見 `PITFALLS.md`（`t` 遮蔽、`classify_error` 比對字面、
  逐字稿檔案裡的文字）
