"""locales/zh_tw.py — 繁體中文（母表）

改這裡的譯文不影響任何邏輯：程式一律用 key 比對。改錯最壞的情況只是
畫面顯示怪怪的。

⚠ 帶變數的訊息一律用**具名** placeholder（{path} 而不是 {0}）——翻譯時
語序一變，位置參數就錯位。四種語言的 placeholder 集合必須完全一致，
tests/test_i18n.py 會檢查。

⚠ **不在這裡的東西**（是資料不是介面文字，見 i18n.py 的設計約束）：
逐字稿 `_transcript.txt` 的段落標頭與失敗佔位符、`transcriber.PROMPT`、
`classify_error` 的分類鍵、以及所有落進 `logs/app.log` 的字面。
"""

from __future__ import annotations

STRINGS: dict[str, str] = {
    # ---- 區塊標題 ----
    "gui.frame.source":            " 音訊來源 ",
    "gui.frame.range":             " 擷取範圍 ",
    "gui.frame.cut":               " 切割設定 ",
    "gui.frame.progress":          " 處理進度 ",

    # ---- 音訊來源 ----
    "gui.radio.local":             "本地上傳",
    "gui.radio.youtube":           "YouTube 下載",
    "gui.btn.select_file":         "選擇檔案",
    "gui.lbl.yt_url":              "YouTube 網址：",
    "gui.lbl.save_as":             "儲存為：",
    "gui.btn.save_as":             "另存新檔",
    "gui.radio.download_transcribe": "下載後馬上轉錄",
    "gui.radio.download_only":     "只下載音訊（不需 API Key）",

    # ---- 擷取範圍 ----
    "gui.chk.range_enabled":       "只處理音訊的一部分",
    "gui.lbl.range_start":         "起始時間：",
    "gui.lbl.range_end":           "結束時間：",
    "gui.lbl.time_format_hint":    "（HH:MM:SS，例如 00:10:00）",
    "gui.lbl.range_note":          "⚠️ 下方切割點為原始音訊的絕對時間，需落在此範圍內才會生效",

    # ---- 切割設定 ----
    "gui.radio.cut_auto":          "自動（每 {minutes} 分鐘切一段）",
    "gui.lbl.min_seg_prefix":      "└ 尾巴不足",
    "gui.lbl.min_seg_suffix":      "分鐘就併入前一段（填 0 不合併）",
    "gui.radio.cut_custom":        "自訂切割點",
    "gui.lbl.custom_points":       "輸入切割時間點（HH:MM:SS，每行一個）：",

    # ---- API Key ----
    "gui.btn.show":                "顯示",
    "gui.chk.remember":            "記住",
    "gui.lbl.api_notice":          "🔒 API Key 僅儲存於本機 .env 檔，請勿將 Key 提供給他人。",
    "gui.link.api_help":           "如何取得 API Key？",

    # ---- API Key 說明視窗 ----
    "gui.dlg.api_help.title":      "如何取得 Gemini API Key",
    "gui.dlg.api_help.steps":      "申請步驟",
    "gui.dlg.api_help.step1":      "1. 點擊下方連結，前往 Google AI Studio",
    "gui.dlg.api_help.step2":      "2. 使用 Google 帳號登入",
    "gui.dlg.api_help.step3":      "3. 點擊「Create API key」",
    "gui.dlg.api_help.step4":      "4. 選擇「Create API key in new project」",
    "gui.dlg.api_help.step5":      "5. 複製產生的 Key，貼入 SnapTranscript 的 API Key 欄位",
    "gui.dlg.api_help.notice":     "⚠️  注意：申請後請確認 API Key 狀態顯示為「Free tier」，\n"
                                   "若顯示「Set up billing」代表尚未啟用免費方案，\n"
                                   "請勿輸入信用卡，直接使用即可享有免費額度。",
    "gui.btn.close":               "關閉",

    # ---- 開始列 / 進度區 ----
    "gui.btn.start_transcribe":    "▶  開始轉錄",
    "gui.btn.start_download":      "▶  開始下載",
    "gui.chk.auto_retry":          "自動重試",
    "gui.status.idle":             "等待開始...",
    "gui.status.preparing":        "準備中...",
    "gui.status.error":            "發生錯誤，請查看上方記錄",
    "gui.btn.open_folder":         "開啟資料夾",
    "gui.log.intro":               "請選擇音訊來源，設定完成後按「開始」。\n",

    # ---- 關閉視窗確認 ----
    "gui.dlg.closing.title":       "任務進行中",
    "gui.dlg.closing.body":        "轉錄還在進行中，現在關閉會中斷任務。\n\n"
                                   "已完成的段落尚未寫檔，關閉後會遺失，\n"
                                   "需要重新開始轉錄。\n\n"
                                   "確定要關閉嗎？",

    # ---- 補跑 ----
    "gui.btn.retry_failed":        "重試失敗的段落",
    "gui.btn.retry_failed_n":      "重試失敗的 {count} 段",
    "gui.btn.continue_unfinished": "繼續未完成的 {count} 段",
    "gui.msg.unfinished_generic":  "部分段落未完成",
    "gui.msg.n_failed":            "{count} 段失敗",
    "gui.msg.n_pending":           "{count} 段未處理",
    "gui.msg.list_sep":            "、",
    "gui.dlg.audio_missing.title": "找不到音訊檔",
    "gui.dlg.audio_missing.body":  "原始音訊已不存在，無法補跑：\n{path}",
    "gui.log.retry_start":         "\n開始補跑 {count} 個失敗段落...",
    "gui.log.transcript_updated":  "\n逐字稿已更新：{path}",

    # ---- 檔案對話框 ----
    "gui.dlg.save_title":          "選擇儲存位置與檔名",
    "gui.dlg.open_title":          "選擇音訊檔案",
    "gui.filetype.mp3":            "MP3 音訊",
    "gui.filetype.audio":          "音訊檔案",
    "gui.filetype.all":            "所有檔案",

    # ---- 輸入驗證 ----
    "gui.dlg.error.title":         "錯誤",
    "gui.dlg.format_error.title":  "格式錯誤",
    "gui.msg.no_file":             "請先選擇音訊檔案",
    "gui.msg.no_url":              "請輸入 YouTube 網址",
    "gui.msg.no_save_path":        "請點「另存新檔」選擇儲存位置與檔名",
    "gui.msg.no_api_key":          "請輸入 Gemini API Key",

    # ---- 執行過程 ----
    "gui.log.downloading":         "正在下載 YouTube 音訊，請稍候...",
    "gui.log.download_done":       "下載完成：{name}",
    "gui.status.downloading_pct":  "下載中... {percent}%  ({done} / {total} MB{speed})",
    "gui.status.downloading_size": "下載中... {done} MB{speed}",
    "gui.log.reading_audio":       "讀取音訊：{name}",
    "gui.log.total_duration":      "總時長：{duration}",
    "gui.log.range":               "擷取範圍：{start} → {end}",
    "gui.log.segments_planned":    "共 {count} 段，開始處理...",
    "gui.log.transcript_saved":    "\n逐字稿已儲存：{path}",

    # ---- 結果 ----
    "gui.dlg.transcribe_failed.title": "轉錄失敗",
    "gui.lbl.downloaded":          "已下載：{path}",
    "gui.dlg.download_done.title": "下載完成",
    "gui.dlg.download_done.body":  "音訊已儲存至：\n{path}",
    "gui.lbl.output":              "輸出：{path}",
    "gui.lbl.output_partial":      "輸出：{path}（{ok}/{total} 段成功）",
    "gui.lbl.output_aborted":      "輸出（部分完成）：{path}",
    "gui.dlg.partial.title":       "部分完成",
    "gui.dlg.partial.body":        "逐字稿已儲存（{ok}/{total} 段成功，{detail}）：\n"
                                   "{path}\n\n"
                                   "未完成的段落在檔案中標記為佔位符，可按「{button}」補跑。",
    "gui.dlg.done.title":          "完成",
    "gui.dlg.done.body":           "逐字稿已儲存：\n{path}",

    # ---- job.py（進度／錯誤訊息，批次 4）----
    "job.status.segments_done":    "{done} / {total} 段完成",
    "job.log.cutting":             "\n[{index}/{total}] 切割 {start} → {end}...",
    "job.log.uploading":           "[{index}/{total}] 上傳至 Gemini，等待轉錄...",
    "job.log.segment_done":        "[{index}/{total}] 完成",
    "job.log.error":               "[錯誤] {reason}",
    # ⚠ 半形括號是刻意的：與遷移前逐字相同，test_job.py 有斷言比對
    "job.log.auto_retrying":       "[{index}/{total}] 自動重試中... ({count}/{max})",
    "job.log.retrying":            "[{index}/{total}] 重試中...",
    "job.log.marked_failed":       "[{index}/{total}] {reason}，標記後繼續",
    "job.log.merging":             "\n合併逐字稿...",
    "job.status.retry_wait":       "第 {index} 段重試中... {seconds} 秒 ({count}/{max})",
    "job.msg.cut_failed":          "第 {index} 段切割失敗，請確認 ffmpeg 是否正常運作",
    "job.msg.quota_exhausted":     "已達 Gemini API 用量上限（可能是短時間內請求過多，或當日額度用盡）。"
                                   "已完成的段落已存檔，請稍後用「重試失敗的段落」補跑。",
    "job.msg.retry_exhausted":     "{reason}，已自動重試 {max} 次仍失敗",
    "job.msg.retry_cancelled":     "{reason}（使用者取消重試）",
    "job.msg.ask_retry":           "{reason}，是否重試？",

    # ---- 錯誤訊息（audio.py / segments.py / transcriber.py，批次 4）----
    "err.audio.not_found":         "找不到音訊檔案：{path}\n"
                                   "檔案可能已被移動、刪除，或所在的隨身碟／網路磁碟已中斷。",
    "err.audio.no_ffprobe":        "找不到 ffprobe（ffmpeg 的一部分）。請確認 ffmpeg 已安裝並加入系統 PATH，"
                                   "在命令列執行 `ffmpeg -version` 可以驗證。",
    "err.audio.bad_duration":      "無法讀取音訊長度：{name}\n"
                                   "這個檔案可能不是有效的音訊／影片檔，或檔案已損毀。",
    "err.audio.download_missing":  "下載後找不到音訊檔案：{path}",
    "err.seg.bad_time_format":     "格式錯誤：「{value}」，請使用 HH:MM:SS 格式（例如 {example}）",
    "err.seg.range_required":      "請輸入起始與結束時間",
    "err.seg.start_after_end":     "起始時間必須早於結束時間",
    "err.seg.min_required":        "請輸入尾巴合併門檻（分鐘），填 0 代表不合併",
    "err.seg.min_bad_format":      "格式錯誤：「{value}」，請輸入整數分鐘（例如 5），填 0 代表不合併",
    "err.seg.min_negative":        "尾巴合併門檻不能是負數，填 0 代表不合併",
    "err.seg.min_too_large":       "尾巴合併門檻必須小於切割長度（{limit} 分鐘），"
                                   "否則合併後的段落會長到可能超出 Gemini 的輸出上限",
    "err.seg.range_beyond_audio":  "擷取範圍超出音訊總長度，請重新設定",
    "err.gemini.file_failed":      "Gemini 檔案處理失敗（狀態：{state}），請重試",
    # ⚠ 沒有 err.gemini.blank_result 這條，是刻意的：
    # `transcriber.py` 拋出的「Gemini 回傳空白結果（finish_reason: ...）」被
    # 同檔的 `classify_error()` 拿去 `in err_str` 比對，決定這個錯誤要不要重試。
    # 那個字面**同時是例外訊息又是分類鍵＝資料**，一翻就自己把自己查斷：
    # classify_error 回 None → 空白結果不再重試 → 直接中止整個任務，而且不會
    # 有任何錯誤，測試也抓不到。維持寫死繁中，靠 test_i18n 的精確豁免放行。

    # ---- 進階設定視窗 ----
    "gui.dlg.settings.title":      "進階設定",

    # ---- 版本更新（進階設定視窗內） ----
    "gui.frame.update":            " 版本更新 ",
    "gui.btn.check_update":        "檢查更新",
    "gui.btn.install_update":      "一鍵安裝",
    "gui.update.checking":         "檢查中...",
    "gui.update.no_git":           "此版本無法自動更新，請至 GitHub 頁面下載最新版本。",
    "gui.update.offline":          "連不上 GitHub，請確認網路連線後再試一次。",
    "gui.update.dirty":            "偵測到本機程式碼有手動修改，已略過（避免覆蓋你的修改）。",
    "gui.update.ahead":            "本機有尚未同步的變更，已略過（避免覆蓋你的修改）。",
    "gui.update.up_to_date":       "已是最新版本。",
    "gui.update.available":        "發現新版本（{count} 筆變更），點「一鍵安裝」更新。",
    "gui.dlg.update_confirm.title": "確認安裝更新",
    "gui.dlg.update_confirm.body": "即將更新程式碼，需要手動重啟程式才會生效。\n\n本次變更：\n{summary}\n\n是否繼續？",
    "gui.update.installing":       "安裝中...",
    "gui.update.updated":          "已更新到最新版本（{commit}），請關閉程式後重新開啟。",
    "gui.dlg.update_done.title":   "更新完成",
    "gui.dlg.update_done.body":    "已安裝最新版本，請關閉這個視窗後重新雙擊啟動器，讓新版本生效。",
    "gui.update.error":            "檢查更新失敗：{msg}",
}
