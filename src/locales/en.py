"""locales/en.py — English

Editing these strings affects no logic: the program always looks up by key.
The worst case for a bad edit is odd-looking text on screen.

⚠ Messages with variables must use **named** placeholders ({path}, not {0}) —
word order changes between languages and positional args end up in the wrong
slot. The placeholder sets must match across all four languages;
tests/test_i18n.py enforces this.

⚠ Machine-translated, **not proofread by a native speaker**. Change values,
never keys.
"""

from __future__ import annotations

STRINGS: dict[str, str] = {
    # ---- Section headings ----
    "gui.frame.source":            " Audio Source ",
    "gui.frame.range":             " Time Range ",
    "gui.frame.cut":               " Split Settings ",
    "gui.frame.progress":          " Progress ",

    # ---- Audio source ----
    "gui.radio.local":             "Local file",
    "gui.radio.youtube":           "YouTube download",
    "gui.btn.select_file":         "Browse",
    "gui.lbl.yt_url":              "YouTube URL:",
    "gui.lbl.save_as":             "Save as:",
    "gui.btn.save_as":             "Save As",
    "gui.radio.download_transcribe": "Transcribe after download",
    "gui.radio.download_only":     "Download audio only (no API key needed)",

    # ---- Time range ----
    "gui.chk.range_enabled":       "Only process part of the audio",
    "gui.lbl.range_start":         "Start:",
    "gui.lbl.range_end":           "End:",
    "gui.lbl.time_format_hint":    "(HH:MM:SS, e.g. 00:10:00)",
    "gui.lbl.range_note":          "⚠️ Split points below are absolute times in the original audio "
                                   "and only take effect inside this range",

    # ---- Split settings ----
    "gui.radio.cut_auto":          "Automatic (one segment every {minutes} minutes)",
    "gui.lbl.min_seg_prefix":      "└ Merge a trailing segment shorter than",
    "gui.lbl.min_seg_suffix":      "minutes into the previous one (0 = never merge)",
    "gui.radio.cut_custom":        "Custom split points",
    "gui.lbl.custom_points":       "Enter split times (HH:MM:SS, one per line):",

    # ---- API key ----
    "gui.btn.show":                "Show",
    "gui.chk.remember":            "Remember",
    "gui.lbl.api_notice":          "🔒 Your API key is stored only in the local .env file. "
                                   "Never share it with anyone.",
    "gui.link.api_help":           "How do I get an API key?",

    # ---- API key help window ----
    "gui.dlg.api_help.title":      "How to get a Gemini API key",
    "gui.dlg.api_help.steps":      "Steps",
    "gui.dlg.api_help.step1":      "1. Click the link below to open Google AI Studio",
    "gui.dlg.api_help.step2":      "2. Sign in with your Google account",
    "gui.dlg.api_help.step3":      "3. Click \"Create API key\"",
    "gui.dlg.api_help.step4":      "4. Choose \"Create API key in new project\"",
    "gui.dlg.api_help.step5":      "5. Copy the key and paste it into SnapTranscript's API Key field",
    "gui.dlg.api_help.notice":     "⚠️  Note: after creating the key, check that its status reads "
                                   "\"Free tier\".\n"
                                   "If it says \"Set up billing\", the free plan is not active yet.\n"
                                   "Do not enter a credit card — the free quota works as is.",
    "gui.btn.close":               "Close",

    # ---- Start row / progress ----
    "gui.btn.start_transcribe":    "▶  Start Transcribing",
    "gui.btn.start_download":      "▶  Start Download",
    "gui.chk.auto_retry":          "Auto retry",
    "gui.status.idle":             "Waiting to start...",
    "gui.status.preparing":        "Preparing...",
    "gui.status.error":            "Something went wrong — see the log above",
    "gui.btn.open_folder":         "Open Folder",
    "gui.log.intro":               "Choose an audio source, then press Start.\n",

    # ---- Close confirmation ----
    "gui.dlg.closing.title":       "Task in progress",
    "gui.dlg.closing.body":        "Transcription is still running. Closing now will abort it.\n\n"
                                   "Finished segments have not been written to disk yet and\n"
                                   "will be lost — you would have to start over.\n\n"
                                   "Close anyway?",

    # ---- Retry ----
    "gui.btn.retry_failed":        "Retry failed segments",
    "gui.btn.retry_failed_n":      "Retry {count} failed segment(s)",
    "gui.btn.continue_unfinished": "Continue {count} unfinished segment(s)",
    "gui.msg.unfinished_generic":  "some segments are unfinished",
    "gui.msg.n_failed":            "{count} failed",
    "gui.msg.n_pending":           "{count} not processed",
    "gui.msg.list_sep":            ", ",
    "gui.dlg.audio_missing.title": "Audio file not found",
    "gui.dlg.audio_missing.body":  "The original audio no longer exists, so it cannot be retried:\n{path}",
    "gui.log.retry_start":         "\nRetrying {count} failed segment(s)...",
    "gui.log.transcript_updated":  "\nTranscript updated: {path}",

    # ---- File dialogs ----
    "gui.dlg.save_title":          "Choose where to save and a file name",
    "gui.dlg.open_title":          "Choose an audio file",
    "gui.filetype.mp3":            "MP3 audio",
    "gui.filetype.audio":          "Audio files",
    "gui.filetype.all":            "All files",

    # ---- Input validation ----
    "gui.dlg.error.title":         "Error",
    "gui.dlg.format_error.title":  "Invalid format",
    "gui.msg.no_file":             "Please choose an audio file first",
    "gui.msg.no_url":              "Please enter a YouTube URL",
    "gui.msg.no_save_path":        "Please click \"Save As\" to choose a location and file name",
    "gui.msg.no_api_key":          "Please enter your Gemini API key",

    # ---- Run ----
    "gui.log.downloading":         "Downloading YouTube audio, please wait...",
    "gui.log.download_done":       "Download complete: {name}",
    "gui.status.downloading_pct":  "Downloading... {percent}%  ({done} / {total} MB{speed})",
    "gui.status.downloading_size": "Downloading... {done} MB{speed}",
    "gui.log.reading_audio":       "Reading audio: {name}",
    "gui.log.total_duration":      "Total length: {duration}",
    "gui.log.range":               "Time range: {start} → {end}",
    "gui.log.segments_planned":    "{count} segment(s) total, starting...",
    "gui.log.transcript_saved":    "\nTranscript saved: {path}",

    # ---- Results ----
    "gui.dlg.transcribe_failed.title": "Transcription failed",
    "gui.lbl.downloaded":          "Downloaded: {path}",
    "gui.dlg.download_done.title": "Download complete",
    "gui.dlg.download_done.body":  "Audio saved to:\n{path}",
    "gui.lbl.output":              "Output: {path}",
    "gui.lbl.output_partial":      "Output: {path} ({ok}/{total} segments OK)",
    "gui.lbl.output_aborted":      "Output (partial): {path}",
    "gui.dlg.partial.title":       "Partially complete",
    "gui.dlg.partial.body":        "Transcript saved ({ok}/{total} segments OK, {detail}):\n"
                                   "{path}\n\n"
                                   "Unfinished segments are marked with placeholders in the file. "
                                   "Press \"{button}\" to retry them.",
    "gui.dlg.done.title":          "Done",
    "gui.dlg.done.body":           "Transcript saved:\n{path}",

    # ---- job.py ----
    "job.status.segments_done":    "{done} / {total} segments done",
    "job.log.cutting":             "\n[{index}/{total}] Splitting {start} → {end}...",
    "job.log.uploading":           "[{index}/{total}] Uploading to Gemini, waiting for transcription...",
    "job.log.segment_done":        "[{index}/{total}] Done",
    "job.log.error":               "[ERROR] {reason}",
    "job.log.auto_retrying":       "[{index}/{total}] Auto-retrying... ({count}/{max})",
    "job.log.retrying":            "[{index}/{total}] Retrying...",
    "job.log.marked_failed":       "[{index}/{total}] {reason} — marked and moving on",
    "job.log.merging":             "\nMerging transcript...",
    "job.status.retry_wait":       "Retrying segment {index}... {seconds}s ({count}/{max})",
    "job.msg.cut_failed":          "Segment {index} could not be split — check that ffmpeg works",
    "job.msg.quota_exhausted":     "Gemini API quota reached (too many requests in a short time, "
                                   "or the daily quota is used up). Finished segments have been "
                                   "saved — use \"Retry failed segments\" later.",
    "job.msg.retry_exhausted":     "{reason} — still failing after {max} automatic retries",
    "job.msg.retry_cancelled":     "{reason} (retry cancelled by user)",
    "job.msg.ask_retry":           "{reason}. Retry?",

    # ---- Errors ----
    "err.audio.not_found":         "Audio file not found: {path}\n"
                                   "It may have been moved or deleted, or the USB / network drive "
                                   "it lives on was disconnected.",
    "err.audio.no_ffprobe":        "ffprobe (part of ffmpeg) not found. Make sure ffmpeg is installed "
                                   "and on your system PATH — running `ffmpeg -version` in a terminal "
                                   "verifies this.",
    "err.audio.bad_duration":      "Could not read the audio length: {name}\n"
                                   "This file may not be a valid audio/video file, or it is corrupted.",
    "err.audio.download_missing":  "Audio file not found after download: {path}",
    "err.seg.bad_time_format":     "Invalid format: \"{value}\" — use HH:MM:SS (e.g. {example})",
    "err.seg.range_required":      "Please enter both a start and an end time",
    "err.seg.start_after_end":     "The start time must be earlier than the end time",
    "err.seg.min_required":        "Enter the trailing-segment merge threshold in minutes (0 = never merge)",
    "err.seg.min_bad_format":      "Invalid format: \"{value}\" — enter whole minutes (e.g. 5), "
                                   "or 0 for no merging",
    "err.seg.min_negative":        "The merge threshold cannot be negative; use 0 for no merging",
    "err.seg.min_too_large":       "The merge threshold must be smaller than the segment length "
                                   "({limit} minutes), otherwise a merged segment could grow long "
                                   "enough to exceed Gemini's output limit",
    "err.seg.range_beyond_audio":  "The selected range is beyond the total audio length — please adjust it",
    "err.gemini.file_failed":      "Gemini failed to process the file (state: {state}). Please retry.",

    # ---- Advanced settings dialog ----
    "gui.dlg.settings.title":      "Advanced Settings",

    # ---- Updates (inside the advanced settings dialog) ----
    "gui.frame.update":            " Updates ",
    "gui.btn.check_update":        "Check for Updates",
    "gui.btn.install_update":      "Install Update",
    "gui.update.checking":         "Checking...",
    "gui.update.no_git":           "This copy can't auto-update. Please download the latest version from GitHub.",
    "gui.update.offline":          "Could not reach GitHub. Check your network connection and try again.",
    "gui.update.dirty":            "Local code changes detected, skipped (to avoid overwriting your changes).",
    "gui.update.ahead":            "Local commits not yet synced, skipped (to avoid overwriting your changes).",
    "gui.update.up_to_date":       "You are on the latest version.",
    "gui.update.available":        "New version available ({count} changes). Click \"Install Update\" to update.",
    "gui.dlg.update_confirm.title": "Confirm Update",
    "gui.dlg.update_confirm.body": "This will update the app code. You will need to restart the app "
                                   "manually afterwards.\n\nChanges:\n{summary}\n\nContinue?",
    "gui.update.installing":       "Installing...",
    "gui.update.updated":          "Updated to the latest version ({commit}). Please close and reopen the app.",
    "gui.dlg.update_done.title":   "Update Complete",
    "gui.dlg.update_done.body":    "The latest version has been installed. Close this window and "
                                   "double-click the launcher again to apply it.",
    "gui.update.error":            "Update check failed: {msg}",
}
