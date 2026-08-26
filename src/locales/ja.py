"""locales/ja.py — 日本語

ここの訳文を変えてもロジックには影響しません（プログラムは常に key で
参照します）。書き間違えても最悪、画面の表示が変になるだけです。

⚠ 変数を含むメッセージは必ず**名前付き** placeholder（{0} ではなく {path}）
を使ってください。翻訳で語順が変わると位置引数はずれます。4 言語の
placeholder の集合は完全に一致する必要があり、tests/test_i18n.py が検査します。

⚠ このファイルは AI が生成したもので、**ネイティブによる校正は未実施**です。
value は直しても key は変更しないでください。
"""

from __future__ import annotations

STRINGS: dict[str, str] = {
    # ---- セクション見出し ----
    "gui.frame.source":            " 音声ソース ",
    "gui.frame.range":             " 抽出範囲 ",
    "gui.frame.cut":               " 分割設定 ",
    "gui.frame.progress":          " 進捗 ",

    # ---- 音声ソース ----
    "gui.radio.local":             "ローカルファイル",
    "gui.radio.youtube":           "YouTube からダウンロード",
    "gui.btn.select_file":         "ファイルを選択",
    "gui.lbl.yt_url":              "YouTube URL：",
    "gui.lbl.save_as":             "保存先：",
    "gui.btn.save_as":             "名前を付けて保存",
    "gui.radio.download_transcribe": "ダウンロード後すぐに文字起こし",
    "gui.radio.download_only":     "音声のダウンロードのみ（API キー不要）",

    # ---- 抽出範囲 ----
    "gui.chk.range_enabled":       "音声の一部だけを処理する",
    "gui.lbl.range_start":         "開始時刻：",
    "gui.lbl.range_end":           "終了時刻：",
    "gui.lbl.time_format_hint":    "（HH:MM:SS、例：00:10:00）",
    "gui.lbl.range_note":          "⚠️ 下の分割ポイントは元音声の絶対時刻です。"
                                   "この範囲内にないと有効になりません",

    # ---- 分割設定 ----
    "gui.radio.cut_auto":          "自動（{minutes} 分ごとに分割）",
    "gui.lbl.min_seg_prefix":      "└ 末尾が",
    "gui.lbl.min_seg_suffix":      "分未満なら前のセグメントに結合（0 で結合しない）",
    "gui.radio.cut_custom":        "分割ポイントを指定",
    "gui.lbl.custom_points":       "分割する時刻を入力（HH:MM:SS、1 行に 1 つ）：",

    # ---- API キー ----
    "gui.btn.show":                "表示",
    "gui.chk.remember":            "記憶",
    "gui.lbl.api_notice":          "🔒 API キーはローカルの .env ファイルにのみ保存されます。"
                                   "他人に渡さないでください。",
    "gui.link.api_help":           "API キーの取得方法",

    # ---- API キー説明ウィンドウ ----
    "gui.dlg.api_help.title":      "Gemini API キーの取得方法",
    "gui.dlg.api_help.steps":      "取得手順",
    "gui.dlg.api_help.step1":      "1. 下のリンクから Google AI Studio を開く",
    "gui.dlg.api_help.step2":      "2. Google アカウントでログインする",
    "gui.dlg.api_help.step3":      "3. 「Create API key」をクリックする",
    "gui.dlg.api_help.step4":      "4. 「Create API key in new project」を選ぶ",
    "gui.dlg.api_help.step5":      "5. 生成されたキーをコピーし、SnapTranscript の API キー欄に貼り付ける",
    "gui.dlg.api_help.notice":     "⚠️  注意：取得後、API キーの状態が「Free tier」になっているか確認してください。\n"
                                   "「Set up billing」と表示される場合は無料プランが有効になっていません。\n"
                                   "クレジットカードを登録しなくても無料枠はそのまま使えます。",
    "gui.btn.close":               "閉じる",

    # ---- 開始行 / 進捗 ----
    "gui.btn.start_transcribe":    "▶  文字起こし開始",
    "gui.btn.start_download":      "▶  ダウンロード開始",
    "gui.chk.auto_retry":          "自動リトライ",
    "gui.status.idle":             "開始待ち...",
    "gui.status.preparing":        "準備中...",
    "gui.status.error":            "エラーが発生しました。上のログを確認してください",
    "gui.btn.open_folder":         "フォルダを開く",
    "gui.log.intro":               "音声ソースを選び、設定が済んだら「開始」を押してください。\n",

    # ---- 終了確認 ----
    "gui.dlg.closing.title":       "処理中",
    "gui.dlg.closing.body":        "文字起こしがまだ実行中です。ここで閉じると中断されます。\n\n"
                                   "完了済みのセグメントはまだ保存されておらず、\n"
                                   "閉じると失われるため最初からやり直しになります。\n\n"
                                   "閉じてもよろしいですか？",

    # ---- リトライ ----
    "gui.btn.retry_failed":        "失敗したセグメントを再実行",
    "gui.btn.retry_failed_n":      "失敗した {count} セグメントを再実行",
    "gui.btn.continue_unfinished": "未完了の {count} セグメントを続行",
    "gui.msg.unfinished_generic":  "一部のセグメントが未完了",
    "gui.msg.n_failed":            "{count} セグメント失敗",
    "gui.msg.n_pending":           "{count} セグメント未処理",
    "gui.msg.list_sep":            "、",
    "gui.dlg.audio_missing.title": "音声ファイルが見つかりません",
    "gui.dlg.audio_missing.body":  "元の音声が存在しないため再実行できません：\n{path}",
    "gui.log.retry_start":         "\n失敗した {count} セグメントの再実行を開始します...",
    "gui.log.transcript_updated":  "\n文字起こしを更新しました：{path}",

    # ---- ファイルダイアログ ----
    "gui.dlg.save_title":          "保存先とファイル名を選択",
    "gui.dlg.open_title":          "音声ファイルを選択",
    "gui.filetype.mp3":            "MP3 音声",
    "gui.filetype.audio":          "音声ファイル",
    "gui.filetype.all":            "すべてのファイル",

    # ---- 入力チェック ----
    "gui.dlg.error.title":         "エラー",
    "gui.dlg.format_error.title":  "形式エラー",
    "gui.msg.no_file":             "先に音声ファイルを選択してください",
    "gui.msg.no_url":              "YouTube の URL を入力してください",
    "gui.msg.no_save_path":        "「名前を付けて保存」で保存先とファイル名を指定してください",
    "gui.msg.no_api_key":          "Gemini API キーを入力してください",

    # ---- 実行 ----
    "gui.log.downloading":         "YouTube の音声をダウンロード中です。しばらくお待ちください...",
    "gui.log.download_done":       "ダウンロード完了：{name}",
    "gui.status.downloading_pct":  "ダウンロード中... {percent}%  ({done} / {total} MB{speed})",
    "gui.status.downloading_size": "ダウンロード中... {done} MB{speed}",
    "gui.log.reading_audio":       "音声を読み込み中：{name}",
    "gui.log.total_duration":      "全体の長さ：{duration}",
    "gui.log.range":               "抽出範囲：{start} → {end}",
    "gui.log.segments_planned":    "全 {count} セグメント、処理を開始します...",
    "gui.log.transcript_saved":    "\n文字起こしを保存しました：{path}",

    # ---- 結果 ----
    "gui.dlg.transcribe_failed.title": "文字起こし失敗",
    "gui.lbl.downloaded":          "ダウンロード済み：{path}",
    "gui.dlg.download_done.title": "ダウンロード完了",
    "gui.dlg.download_done.body":  "音声を保存しました：\n{path}",
    "gui.lbl.output":              "出力：{path}",
    "gui.lbl.output_partial":      "出力：{path}（{ok}/{total} セグメント成功）",
    "gui.lbl.output_aborted":      "出力（一部完了）：{path}",
    "gui.dlg.partial.title":       "一部完了",
    "gui.dlg.partial.body":        "文字起こしを保存しました（{ok}/{total} セグメント成功、{detail}）：\n"
                                   "{path}\n\n"
                                   "未完了のセグメントはファイル内でプレースホルダーになっています。"
                                   "「{button}」で再実行できます。",
    "gui.dlg.done.title":          "完了",
    "gui.dlg.done.body":           "文字起こしを保存しました：\n{path}",

    # ---- job.py ----
    "job.status.segments_done":    "{done} / {total} セグメント完了",
    "job.log.cutting":             "\n[{index}/{total}] 分割中 {start} → {end}...",
    "job.log.uploading":           "[{index}/{total}] Gemini にアップロード中、文字起こし待ち...",
    "job.log.segment_done":        "[{index}/{total}] 完了",
    "job.log.error":               "[エラー] {reason}",
    "job.log.auto_retrying":       "[{index}/{total}] 自動リトライ中... ({count}/{max})",
    "job.log.retrying":            "[{index}/{total}] リトライ中...",
    "job.log.marked_failed":       "[{index}/{total}] {reason} — 記録して次へ進みます",
    "job.log.merging":             "\n文字起こしを結合中...",
    "job.status.retry_wait":       "セグメント {index} をリトライ中... {seconds} 秒 ({count}/{max})",
    "job.msg.cut_failed":          "セグメント {index} の分割に失敗しました。ffmpeg が正常に動作するか確認してください",
    "job.msg.quota_exhausted":     "Gemini API の利用上限に達しました（短時間にリクエストが多すぎるか、"
                                   "当日の枠を使い切っています）。完了済みのセグメントは保存済みです。"
                                   "後ほど「失敗したセグメントを再実行」でお試しください。",
    "job.msg.retry_exhausted":     "{reason} — 自動リトライ {max} 回でも失敗しました",
    "job.msg.retry_cancelled":     "{reason}（ユーザーがリトライをキャンセル）",
    "job.msg.ask_retry":           "{reason}。リトライしますか？",

    # ---- エラー ----
    "err.audio.not_found":         "音声ファイルが見つかりません：{path}\n"
                                   "移動または削除されたか、保存先の USB／ネットワークドライブが"
                                   "切断されている可能性があります。",
    "err.audio.no_ffprobe":        "ffprobe（ffmpeg の一部）が見つかりません。ffmpeg がインストールされ、"
                                   "システムの PATH に登録されているか確認してください。"
                                   "コマンドラインで `ffmpeg -version` を実行すると確認できます。",
    "err.audio.bad_duration":      "音声の長さを読み取れません：{name}\n"
                                   "有効な音声／動画ファイルではないか、ファイルが壊れている可能性があります。",
    "err.audio.download_missing":  "ダウンロード後に音声ファイルが見つかりません：{path}",
    "err.seg.bad_time_format":     "形式エラー：「{value}」。HH:MM:SS 形式で入力してください（例：{example}）",
    "err.seg.range_required":      "開始時刻と終了時刻を入力してください",
    "err.seg.start_after_end":     "開始時刻は終了時刻より前である必要があります",
    "err.seg.min_required":        "末尾結合のしきい値（分）を入力してください。0 で結合しません",
    "err.seg.min_bad_format":      "形式エラー：「{value}」。整数の分で入力してください（例：5）。0 で結合しません",
    "err.seg.min_negative":        "末尾結合のしきい値に負の数は指定できません。0 で結合しません",
    "err.seg.min_too_large":       "末尾結合のしきい値は分割の長さ（{limit} 分）より小さくしてください。"
                                   "そうしないと結合後のセグメントが長くなり、"
                                   "Gemini の出力上限を超える可能性があります",
    "err.seg.range_beyond_audio":  "抽出範囲が音声全体の長さを超えています。設定し直してください",
    "err.gemini.file_failed":      "Gemini のファイル処理に失敗しました（状態：{state}）。再試行してください。",

    # ---- 詳細設定ウィンドウ ----
    "gui.dlg.settings.title":      "詳細設定",

    # ---- アップデート（詳細設定ウィンドウ内） ----
    "gui.frame.update":            " アップデート ",
    "gui.btn.check_update":        "更新を確認",
    "gui.btn.install_update":      "ワンクリックインストール",
    "gui.update.checking":         "確認中...",
    "gui.update.no_git":           "このバージョンは自動更新できません。GitHub ページから最新版をダウンロードしてください。",
    "gui.update.offline":          "GitHub に接続できません。ネットワーク接続を確認して再度お試しください。",
    "gui.update.dirty":            "ローカルのコードに手動変更が検出されたためスキップしました（変更を上書きしないため）。",
    "gui.update.ahead":            "未同期のローカル変更があるためスキップしました（変更を上書きしないため）。",
    "gui.update.up_to_date":       "最新バージョンです。",
    "gui.update.available":        "新しいバージョンがあります（{count} 件の変更）。「ワンクリックインストール」で更新してください。",
    "gui.dlg.update_confirm.title": "更新の確認",
    "gui.dlg.update_confirm.body": "コードを更新します。反映には手動での再起動が必要です。\n\n今回の変更：\n{summary}\n\n続行しますか？",
    "gui.update.installing":       "インストール中...",
    "gui.update.updated":          "最新バージョン（{commit}）に更新しました。プログラムを閉じて再度開いてください。",
    "gui.dlg.update_done.title":   "更新完了",
    "gui.dlg.update_done.body":    "最新バージョンをインストールしました。このウィンドウを閉じてから起動ファイルをダブルクリックし直してください。",
    "gui.update.error":            "更新確認に失敗しました：{msg}",
}
