"""SnapTranscript 主視窗（tkinter）。"""

import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import ttk, filedialog, messagebox, scrolledtext

from dotenv import load_dotenv, set_key
from google import genai

import i18n
import job
import update_checker
from audio import download_youtube_audio, get_audio_duration
from config import (
    CONFIG_PATH,
    DEFAULT_CHUNK_SECONDS,
    ENV_PATH,
    MIN_SEGMENT_SECONDS,
    MODEL_NAME,
    load_config,
    save_config,
)
from i18n import t
from logger import write_log, write_log_header
from segments import (
    parse_custom_cut_points,
    parse_min_segment_minutes,
    parse_range,
    plan_segments,
    seconds_to_hms,
)


# ---- 主視窗 ----
class SnapTranscriptApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("SnapTranscript")
        self.root.resizable(False, False)

        self.msg_queue: queue.Queue = queue.Queue()
        self.is_running = False
        self._job: job.TranscriptionJob | None = None
        self.source_mode = tk.StringVar(value="local")
        self.yt_url_var = tk.StringVar()
        self.yt_save_path_var = tk.StringVar()
        self.yt_action = tk.StringVar(value="transcribe")
        self._last_output_path = ""
        self.range_enabled = tk.BooleanVar(value=False)
        self.range_start_var = tk.StringVar()
        self.range_end_var = tk.StringVar()
        self.auto_retry_var = tk.BooleanVar(value=True)
        self.log_start_time = 0.0

        self._poll_after_id: str | None = None

        self.cfg = load_config(CONFIG_PATH)
        # 語言必須在建任何 widget 之前設好——t() 是建置時查一次表，設晚了
        # 介面會停在預設語言（見 pattern_i18n.py 地雷「t() 不可在 import 時求值」）
        i18n.set_lang(self.cfg.get("language"))

        self._build_ui()
        self._load_api_key()
        self._position_window()
        self._poll_queue()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- 視窗定位 ----
    def _position_window(self):
        """視窗置中並加寬，同時避免底部超出螢幕（被工作列切到）。"""
        self.root.update_idletasks()
        width = self.root.winfo_reqwidth() + 150
        height = self.root.winfo_reqheight()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2 - 20)

        taskbar_estimate = 48
        if y + height > screen_h - taskbar_estimate:
            y = max(0, screen_h - taskbar_estimate - height)

        self.root.geometry(f"{width}x{height}+{x}+{y}")

    # ---- 關閉視窗 ----
    def _on_close(self):
        """關視窗前確認並清暫存檔。

        背景執行緒是 daemon，行程一結束就被硬砍，`job._process_one` 的 finally
        不會執行——不清的話專案目錄會留下一個 27 MB 左右的 `_temp_seg_*`，
        跑幾次就是好幾百 MB。只清本行程 PID 的檔案，不動其他實例的。
        """
        if self.is_running:
            if not messagebox.askyesno(
                t("gui.dlg.closing.title"),
                t("gui.dlg.closing.body"),
            ):
                return

        if self._poll_after_id is not None:
            # 不取消的話，destroy 後那個 after 回呼會噴
            # 「invalid command name ..._poll_queue」
            try:
                self.root.after_cancel(self._poll_after_id)
            except tk.TclError:
                pass

        job.cleanup_temp_files()
        self.root.destroy()

    # ---- 語言 ----
    def _build_language_row(self):
        """主視窗第一列的語言選單（右對齊）。

        這個工具沒有設定視窗（pattern_i18n.py 第 5 段假設有），所以語言列
        直接放主視窗最上面。標籤固定英文 `Language:`、選項用各語言自稱——
        任何語言下使用者都認得出哪個是哪個。選項由 i18n.LANGUAGES 動態生成，
        日後新增語言這裡一個字都不必改。
        """
        lang_frame = ttk.Frame(self.root)
        lang_frame.grid(row=0, column=0, sticky="e", padx=14, pady=(8, 0))
        ttk.Label(lang_frame, text="Language:").pack(side="left", padx=(0, 6))

        self._lang_choices = i18n.available_languages()
        # ⚠ 讀 config 不讀 i18n.get_lang()：set_lang() 只在 __init__ 跑一次，
        # 使用者選了新語言但按「稍後」不重啟時，runtime 語言還是舊的。用 runtime
        # 值當基準的話，下次改語言會把他的選擇默默寫回去。
        saved = self.cfg.get("language", "")
        self._lang_saved_code = saved if i18n.is_supported(saved) else i18n.DEFAULT_LANG
        names = [name for _, name in self._lang_choices]
        current = next(
            (n for c, n in self._lang_choices if c == self._lang_saved_code), names[0]
        )
        self.lang_var = tk.StringVar(value=current)
        combo = ttk.Combobox(
            lang_frame, textvariable=self.lang_var, values=names,
            width=10, state="readonly",
        )
        combo.pack(side="left")
        combo.bind("<<ComboboxSelected>>", self._on_language_selected)

        # 進階設定入口（目前只有「檢查更新」；日後其他設定項都掛在這個
        # Toplevel 裡，不做即時分頁）。齒輪符號跨語言通用，按鈕本身不需要
        # 翻譯文字。
        ttk.Button(
            lang_frame, text="⚙", width=3, command=self._open_settings,
        ).pack(side="left", padx=(6, 0))

    def _selected_lang_code(self) -> str:
        """把下拉選單顯示的名稱換回代號。取不到就維持原設定，不亂改。"""
        chosen = self.lang_var.get()
        for code, name in self._lang_choices:
            if name == chosen:
                return code
        return self._lang_saved_code

    def _on_language_selected(self, _event=None):
        """選了語言就存檔，真的變更才問要不要重啟。"""
        new_lang = self._selected_lang_code()
        if new_lang == self._lang_saved_code:
            return
        self.cfg["language"] = new_lang
        save_config(self.cfg, CONFIG_PATH)
        self._lang_saved_code = new_lang
        self._prompt_restart_for_language()

    def _prompt_restart_for_language(self):
        """語言變更後問是否重啟。

        **重開才生效，不做即時切換。** 即時切換要建 widget 登記表逐一
        config(text=...)，漏掉任何一個元件就是中英混雜，popup 還要額外處理，
        改動幅度大好幾倍，換來的只是省一次重開。

        視窗全英文：此刻介面還是舊語言、使用者要的是新語言，用任一方都尷尬。
        """
        if messagebox.askyesno(
            "Language Changed",
            "Restart the app to apply the new language.\n\nRestart now?",
        ):
            self._restart_app()

    def _restart_app(self):
        """起一個新行程再關掉自己。

        不用 os.execv：Windows 上它會就地覆寫當前行程，tkinter 還沒釋放的
        視窗 handle 可能殘留，看起來像關不掉的殭屍視窗。
        """
        try:
            subprocess.Popen([sys.executable, *sys.argv], close_fds=True)
        except OSError:
            # 起不了新行程就什麼都不做——使用者下次自己開一樣會生效，
            # 這裡把舊視窗關掉反而讓人以為程式壞了
            return
        job.cleanup_temp_files()
        self.root.destroy()

    # ---- 進階設定（目前只有版本更新，未來的一般設定項都加在這個 Toplevel 裡）----
    def _open_settings(self):
        win = tk.Toplevel(self.root)
        win.title(t("gui.dlg.settings.title"))
        win.resizable(False, False)
        win.grab_set()

        self._build_update_section(win)

        ttk.Button(win, text=t("gui.btn.close"), command=win.destroy).pack(
            pady=(0, 14)
        )

    # ------------------------------------------------------------------
    # 版本更新區塊
    #
    # ⚠ 全程沒有任何一步自動觸發：「檢查更新」只讀不寫；有新版本才會出現
    # 「一鍵安裝」，按下去還要先跳確認框，使用者按確定才真的動檔案。
    # 更新完不自動重啟（跟語言切換不同），只跳訊息框請使用者自己關掉重開，
    # 因為更新可能動到正在執行中的模組，自動重啟的邊界情況不值得為手動
    # 觸發的功能多繞。
    # ------------------------------------------------------------------
    def _build_update_section(self, parent: tk.Widget):
        section = ttk.LabelFrame(parent, text=t("gui.frame.update"), padding=8)
        section.pack(fill="x", padx=14, pady=14)

        row = ttk.Frame(section)
        row.pack(anchor="w", fill="x")

        self._check_update_btn = ttk.Button(
            row, text=t("gui.btn.check_update"), command=self._on_check_update,
        )
        self._check_update_btn.pack(side="left")

        self._install_update_btn = ttk.Button(
            row, text=t("gui.btn.install_update"), command=self._on_install_update,
        )
        # 有新版本才 pack，預設不顯示

        self._update_status_var = tk.StringVar(value="")
        ttk.Label(
            section, textvariable=self._update_status_var,
            foreground="gray", justify="left", anchor="w", wraplength=360,
        ).pack(anchor="w", fill="x", pady=(8, 0))

        self._pending_update_summary = ""

    def _on_check_update(self):
        self._check_update_btn.config(state="disabled")
        self._install_update_btn.pack_forget()
        self._update_status_var.set(t("gui.update.checking"))
        threading.Thread(target=self._check_update_worker, daemon=True).start()

    def _check_update_worker(self):
        """背景執行緒：跑 git fetch，不可卡住主視窗（見 windows-tool-templates.md）。"""
        result = update_checker.check_for_update()
        try:
            self.root.after(0, self._on_check_update_done, result)
        except (RuntimeError, tk.TclError):
            pass  # 視窗已關閉，結果沒人要了

    def _on_check_update_done(self, result: dict):
        self._check_update_btn.config(state="normal")
        status = result.get("status")

        if status == "no_git":
            self._update_status_var.set(t("gui.update.no_git"))
        elif status == "offline":
            self._update_status_var.set(t("gui.update.offline"))
        elif status == "dirty":
            self._update_status_var.set(t("gui.update.dirty"))
        elif status == "ahead":
            self._update_status_var.set(t("gui.update.ahead"))
        elif status == "up_to_date":
            self._update_status_var.set(t("gui.update.up_to_date"))
        elif status == "update_available":
            self._pending_update_summary = result.get("summary", "")
            self._update_status_var.set(
                t("gui.update.available", count=result.get("commits", 0))
            )
            self._install_update_btn.pack(side="left", padx=(8, 0))
        else:
            self._update_status_var.set(
                t("gui.update.error", msg=result.get("message", status or ""))
            )

    def _on_install_update(self):
        if not messagebox.askyesno(
            t("gui.dlg.update_confirm.title"),
            t("gui.dlg.update_confirm.body", summary=self._pending_update_summary),
        ):
            return
        self._check_update_btn.config(state="disabled")
        self._install_update_btn.config(state="disabled")
        self._update_status_var.set(t("gui.update.installing"))
        threading.Thread(target=self._install_update_worker, daemon=True).start()

    def _install_update_worker(self):
        result = update_checker.install_update()
        try:
            self.root.after(0, self._on_install_update_done, result)
        except (RuntimeError, tk.TclError):
            pass

    def _on_install_update_done(self, result: dict):
        self._check_update_btn.config(state="normal")
        status = result.get("status")

        if status == "updated":
            self._install_update_btn.pack_forget()
            self._update_status_var.set(
                t("gui.update.updated", commit=result.get("commit", ""))
            )
            messagebox.showinfo(
                t("gui.dlg.update_done.title"), t("gui.dlg.update_done.body")
            )
        else:
            self._install_update_btn.config(state="normal")
            self._update_status_var.set(
                t("gui.update.error", msg=result.get("message", status or ""))
            )

    # ---- UI 建置 ----
    def _build_ui(self):
        pad = {"padx": 14, "pady": 6}

        self._build_language_row()

        # 音訊來源
        frame_source = ttk.LabelFrame(self.root, text=t("gui.frame.source"), padding=8)
        frame_source.grid(row=1, column=0, sticky="ew", **pad)
        frame_source.columnconfigure(0, weight=1)

        # Radio：本地上傳 / YouTube 下載
        radio_row = ttk.Frame(frame_source)
        radio_row.grid(row=0, column=0, sticky="w", pady=(0, 6))
        ttk.Radiobutton(
            radio_row, text=t("gui.radio.local"),
            variable=self.source_mode, value="local",
            command=self._toggle_source_mode,
        ).pack(side="left", padx=(0, 16))
        ttk.Radiobutton(
            radio_row, text=t("gui.radio.youtube"),
            variable=self.source_mode, value="youtube",
            command=self._toggle_source_mode,
        ).pack(side="left")

        # 本地上傳 UI
        self.frame_local = ttk.Frame(frame_source)
        self.frame_local.grid(row=1, column=0, sticky="ew")
        self.frame_local.columnconfigure(0, weight=1)
        self.file_var = tk.StringVar()
        ttk.Entry(self.frame_local, textvariable=self.file_var, state="readonly").grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        ttk.Button(self.frame_local, text=t("gui.btn.select_file"), command=self._select_file).grid(
            row=0, column=1
        )

        # YouTube 下載 UI
        self.frame_youtube = ttk.Frame(frame_source)
        self.frame_youtube.grid(row=1, column=0, sticky="ew")
        self.frame_youtube.columnconfigure(1, weight=1)
        ttk.Label(self.frame_youtube, text=t("gui.lbl.yt_url")).grid(
            row=0, column=0, sticky="w", padx=(0, 6)
        )
        ttk.Entry(self.frame_youtube, textvariable=self.yt_url_var).grid(
            row=0, column=1, columnspan=2, sticky="ew"
        )
        ttk.Label(self.frame_youtube, text=t("gui.lbl.save_as")).grid(
            row=1, column=0, sticky="w", padx=(0, 6), pady=(6, 0)
        )
        ttk.Entry(self.frame_youtube, textvariable=self.yt_save_path_var, state="readonly").grid(
            row=1, column=1, sticky="ew", padx=(0, 8), pady=(6, 0)
        )
        ttk.Button(self.frame_youtube, text=t("gui.btn.save_as"), command=self._select_save_path).grid(
            row=1, column=2, pady=(6, 0)
        )
        action_frame = ttk.Frame(self.frame_youtube)
        action_frame.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Radiobutton(
            action_frame, text=t("gui.radio.download_transcribe"),
            variable=self.yt_action, value="transcribe",
            command=self._update_btn_label,
        ).pack(side="left", padx=(0, 16))
        ttk.Radiobutton(
            action_frame, text=t("gui.radio.download_only"),
            variable=self.yt_action, value="download_only",
            command=self._update_btn_label,
        ).pack(side="left")
        self.frame_youtube.grid_remove()  # 預設隱藏

        # 擷取範圍
        self.frame_range = ttk.LabelFrame(self.root, text=t("gui.frame.range"), padding=8)
        self.frame_range.grid(row=2, column=0, sticky="ew", **pad)

        ttk.Checkbutton(
            self.frame_range, text=t("gui.chk.range_enabled"),
            variable=self.range_enabled, command=self._toggle_range_mode,
        ).grid(row=0, column=0, sticky="w")

        self.frame_range_inputs = ttk.Frame(self.frame_range)
        self.frame_range_inputs.grid(row=1, column=0, sticky="w", padx=(20, 0), pady=(6, 0))
        ttk.Label(self.frame_range_inputs, text=t("gui.lbl.range_start")).grid(row=0, column=0, sticky="w")
        ttk.Entry(self.frame_range_inputs, textvariable=self.range_start_var, width=10).grid(
            row=0, column=1, padx=(0, 16)
        )
        ttk.Label(self.frame_range_inputs, text=t("gui.lbl.range_end")).grid(row=0, column=2, sticky="w")
        ttk.Entry(self.frame_range_inputs, textvariable=self.range_end_var, width=10).grid(
            row=0, column=3
        )
        ttk.Label(self.frame_range_inputs, text=t("gui.lbl.time_format_hint")).grid(
            row=1, column=0, columnspan=4, sticky="w", pady=(2, 0)
        )
        self.frame_range_inputs.grid_remove()  # 預設隱藏

        tk.Label(
            self.frame_range,
            text=t("gui.lbl.range_note"),
            foreground="gray", font=("", 8),
        ).grid(row=2, column=0, sticky="w", pady=(6, 0))

        # 切割設定
        self.frame_cut = ttk.LabelFrame(self.root, text=t("gui.frame.cut"), padding=8)
        self.frame_cut.grid(row=3, column=0, sticky="ew", **pad)
        frame_cut = self.frame_cut

        self.cut_mode = tk.StringVar(value="auto")
        ttk.Radiobutton(
            frame_cut, text=t("gui.radio.cut_auto", minutes=DEFAULT_CHUNK_SECONDS // 60),
            variable=self.cut_mode, value="auto", command=self._toggle_cut_mode,
        ).grid(row=0, column=0, sticky="w")

        # 尾巴合併門檻：只對自動模式有意義，所以縮排掛在「自動」底下，
        # 切到「自訂切割點」時整列 disable（自訂切點不做合併，見 segments.py）
        self.frame_min_seg = ttk.Frame(frame_cut)
        self.frame_min_seg.grid(row=1, column=0, sticky="w", padx=(20, 0), pady=(2, 0))
        ttk.Label(self.frame_min_seg, text=t("gui.lbl.min_seg_prefix")).pack(side="left")
        self.min_seg_var = tk.StringVar(value=str(MIN_SEGMENT_SECONDS // 60))
        self.entry_min_seg = ttk.Entry(
            self.frame_min_seg, textvariable=self.min_seg_var, width=4, justify="center"
        )
        self.entry_min_seg.pack(side="left", padx=4)
        ttk.Label(self.frame_min_seg, text=t("gui.lbl.min_seg_suffix")).pack(side="left")

        ttk.Radiobutton(
            frame_cut, text=t("gui.radio.cut_custom"),
            variable=self.cut_mode, value="custom", command=self._toggle_cut_mode,
        ).grid(row=2, column=0, sticky="w", pady=(4, 0))

        self.frame_custom = ttk.Frame(frame_cut)
        self.frame_custom.grid(row=3, column=0, sticky="ew", padx=(20, 0), pady=(6, 0))
        ttk.Label(self.frame_custom, text=t("gui.lbl.custom_points")).pack(anchor="w")
        self.cut_text = scrolledtext.ScrolledText(
            self.frame_custom, width=28, height=5, font=("Consolas", 10)
        )
        self.cut_text.pack(fill="x")
        self.cut_text.insert("1.0", "00:30:00\n01:00:00")
        self.frame_custom.grid_remove()  # 預設隱藏

        # API Key
        self.frame_api = ttk.LabelFrame(self.root, text=" Gemini API Key ", padding=8)
        self.frame_api.grid(row=4, column=0, sticky="ew", **pad)

        api_row = tk.Frame(self.frame_api)
        api_row.pack(anchor="w")
        self.api_var = tk.StringVar()
        self.api_entry = ttk.Entry(api_row, textvariable=self.api_var, width=40, show="•")
        self.api_entry.pack(side="left", padx=(0, 8))
        ttk.Button(api_row, text=t("gui.btn.show"), width=5, command=self._toggle_api_show).pack(
            side="left", padx=(0, 8)
        )
        self.save_key_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(api_row, text=t("gui.chk.remember"), variable=self.save_key_var).pack(side="left")

        tk.Label(
            self.frame_api,
            text=t("gui.lbl.api_notice"),
            foreground="gray", font=("", 8),
        ).pack(anchor="w", pady=(4, 0))

        # 開始按鈕列（如何取得？ 左邊，開始轉錄 置中）
        frame_start = tk.Frame(self.root)
        frame_start.grid(row=5, column=0, sticky="ew", padx=14, pady=10)
        frame_start.columnconfigure(0, weight=1)
        frame_start.columnconfigure(1, weight=1)
        frame_start.columnconfigure(2, weight=1)

        link = tk.Label(
            frame_start, text=t("gui.link.api_help"),
            foreground="#0078D4", cursor="hand2", font=("", 9, "underline")
        )
        link.grid(row=0, column=0, sticky="w")
        link.bind("<Button-1>", lambda e: self._show_api_help())

        self.btn_start = ttk.Button(
            frame_start, text=t("gui.btn.start_transcribe"), command=self._start, width=20
        )
        self.btn_start.grid(row=0, column=1, ipady=6)

        ttk.Checkbutton(
            frame_start, text=t("gui.chk.auto_retry"), variable=self.auto_retry_var,
        ).grid(row=0, column=2, sticky="w", padx=(10, 0))


        # 進度區
        frame_progress = ttk.LabelFrame(self.root, text=t("gui.frame.progress"), padding=8)
        frame_progress.grid(row=6, column=0, sticky="ew", padx=14, pady=(6, 14))

        self.progress_label = ttk.Label(frame_progress, text=t("gui.status.idle"))
        self.progress_label.pack(anchor="w")
        self.progress_bar = ttk.Progressbar(frame_progress, mode="determinate")
        self.progress_bar.pack(fill="x", pady=(4, 8))
        self.log_text = scrolledtext.ScrolledText(
            frame_progress, width=56, height=8, state="disabled", font=("Consolas", 9)
        )
        self.log_text.pack(fill="x")

        # 輸出路徑 + 開啟資料夾
        frame_output = tk.Frame(self.root)
        frame_output.grid(row=7, column=0, pady=(0, 12))
        # wraplength 220：兩顆按鈕（開啟資料夾 87 + 重試失敗的 N 段 ~100+）
        # 同時顯示時，長路徑改換行而非把視窗撐寬，見 task-9-report.md Finding 3
        self.output_label = ttk.Label(
            frame_output, text="", foreground="gray", wraplength=220, justify="left"
        )
        self.output_label.pack(side="left", padx=(0, 8))
        self.btn_open_folder = ttk.Button(
            frame_output, text=t("gui.btn.open_folder"), command=self._open_output_folder
        )
        # 預設隱藏，完成後才顯示
        self.btn_retry_failed = ttk.Button(
            frame_output, text=t("gui.btn.retry_failed"), command=self._retry_failed
        )
        # 預設隱藏，有失敗段落時才顯示

        # 初始引導文字
        self.log_text.config(state="normal")
        self.log_text.insert("1.0", t("gui.log.intro"))
        self.log_text.config(state="disabled")

        self.root.columnconfigure(0, weight=1)

    # ---- UI 互動 ----
    def _show_api_help(self):
        win = tk.Toplevel(self.root)
        win.title(t("gui.dlg.api_help.title"))
        win.resizable(False, False)
        win.grab_set()  # 鎖定焦點在此視窗

        pad = {"padx": 20, "pady": 6}

        ttk.Label(win, text=t("gui.dlg.api_help.steps"), font=("", 11, "bold")).pack(anchor="w", padx=20, pady=(16, 4))

        steps = [t(f"gui.dlg.api_help.step{i}") for i in range(1, 6)]
        for step in steps:
            ttk.Label(win, text=step, justify="left").pack(anchor="w", **pad)

        # 注意事項
        notice_frame = tk.Frame(win, background="#FFF3CD", padx=12, pady=10)
        notice_frame.pack(fill="x", padx=20, pady=(8, 4))
        tk.Label(
            notice_frame,
            text=t("gui.dlg.api_help.notice"),
            justify="left", background="#FFF3CD", foreground="#856404"
        ).pack(anchor="w")

        # 可點擊超連結
        url = "https://aistudio.google.com/apikey"
        link = tk.Label(win, text=url, foreground="#0078D4", cursor="hand2",
                        font=("", 9, "underline"))
        link.pack(anchor="w", padx=20, pady=(4, 16))
        link.bind("<Button-1>", lambda e: webbrowser.open(url))

        ttk.Button(win, text=t("gui.btn.close"), command=win.destroy).pack(pady=(0, 16))

    def _toggle_cut_mode(self):
        is_custom = self.cut_mode.get() == "custom"
        if is_custom:
            self.frame_custom.grid()
        else:
            self.frame_custom.grid_remove()
        # 尾巴合併只作用於自動模式，切到自訂就 dim 掉，免得以為有生效
        self._set_widgets_state(self.frame_min_seg, "disabled" if is_custom else "normal")
        self.root.update_idletasks()

    def _toggle_range_mode(self):
        if self.range_enabled.get():
            self.frame_range_inputs.grid()
        else:
            self.frame_range_inputs.grid_remove()
        self.root.update_idletasks()

    def _toggle_api_show(self):
        self.api_entry.config(show="" if self.api_entry.cget("show") else "•")

    def _toggle_source_mode(self):
        if self.source_mode.get() == "youtube":
            self.frame_local.grid_remove()
            self.frame_youtube.grid()
        else:
            self.frame_youtube.grid_remove()
            self.frame_local.grid()
        self._update_btn_label()
        self.root.update_idletasks()

    def _set_widgets_state(self, widget, state):
        """遞迴設定 widget 及其所有子元件的 state"""
        try:
            widget.config(state=state)
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._set_widgets_state(child, state)

    def _update_btn_label(self):
        is_download_only = (
            self.source_mode.get() == "youtube" and self.yt_action.get() == "download_only"
        )
        if is_download_only:
            self.btn_start.config(text=t("gui.btn.start_download"))
            self._set_widgets_state(self.frame_range, "disabled")
            self._set_widgets_state(self.frame_cut, "disabled")
            self._set_widgets_state(self.frame_api, "disabled")
        else:
            self.btn_start.config(text=t("gui.btn.start_transcribe"))
            self._set_widgets_state(self.frame_range, "normal")
            self._set_widgets_state(self.frame_cut, "normal")
            self._set_widgets_state(self.frame_api, "normal")

    def _open_output_folder(self):
        folder = os.path.dirname(self._last_output_path)
        if folder and os.path.exists(folder):
            os.startfile(folder)

    def _retry_button_text(self) -> str:
        """補跑按鈕的文字。

        「失敗」與「未完成」是兩件事：重試耗盡的段落確實失敗過，但任務中途
        中止（例如 429 配額用盡）時，後面的段落根本沒輪到跑。全都寫成
        「重試失敗的 N 段」會讓使用者以為錯了 N 次。
        """
        if self._job is None:
            return t("gui.btn.retry_failed")
        n = self._job.failed_count
        if self._job.pending_count > 0:
            return t("gui.btn.continue_unfinished", count=n)
        return t("gui.btn.retry_failed_n", count=n)

    def _unfinished_wording(self) -> str:
        """「部分完成」對話框裡描述未完成段落的措辭。"""
        if self._job is None:
            return t("gui.msg.unfinished_generic")
        failed, pending = self._job.attempted_failed_count, self._job.pending_count
        parts = []
        if failed:
            parts.append(t("gui.msg.n_failed", count=failed))
        if pending:
            parts.append(t("gui.msg.n_pending", count=pending))
        return t("gui.msg.list_sep").join(parts) or t("gui.msg.unfinished_generic")

    def _retry_failed(self):
        """只補跑失敗的段落（背景執行緒）。"""
        if self._job is None or self._job.failed_count == 0:
            return
        if not os.path.exists(self._job.audio_path):
            messagebox.showerror(
                t("gui.dlg.audio_missing.title"),
                t("gui.dlg.audio_missing.body", path=self._job.audio_path),
            )
            return

        self.is_running = True
        self.btn_start.config(state="disabled")
        self.btn_retry_failed.pack_forget()
        self._log(t("gui.log.retry_start", count=self._job.failed_count))

        worker_thread = threading.Thread(target=self._retry_worker, daemon=True)
        worker_thread.start()

    def _retry_worker(self):
        """背景執行緒：只跑失敗段落，成功後重新合併覆寫輸出檔。"""
        self.log_start_time = time.time()
        try:
            write_log_header(
                f"補跑 {os.path.basename(self._job.audio_path)} | {MODEL_NAME} | "
                f"{self._job.failed_count}段"
            )
            output_path = self._job.retry_failed()
            self._log(t("gui.log.transcript_updated", path=output_path))
            self._finalize_log_file(success=self._job.failed_count == 0)
            self._done(output_path, success=True, failed_count=self._job.failed_count)
        except job.QuotaExhausted as e:
            # 不落檔：job.py 拋出前已經記過一行 429
            self._abort(e, log_label=None)
        except Exception as e:
            self._abort(e, log_label="補跑中止")

    def _select_save_path(self):
        path = filedialog.asksaveasfilename(
            title=t("gui.dlg.save_title"),
            defaultextension=".mp3",
            filetypes=[(t("gui.filetype.mp3"), "*.mp3"), (t("gui.filetype.all"), "*.*")],
        )
        if path:
            self.yt_save_path_var.set(path)

    def _select_file(self):
        path = filedialog.askopenfilename(
            title=t("gui.dlg.open_title"),
            filetypes=[
                (t("gui.filetype.audio"),
                 "*.mp3 *.wav *.m4a *.aac *.flac *.ogg *.wma *.mp4 *.mov *.mkv"),
                (t("gui.filetype.all"), "*.*"),
            ],
        )
        if path:
            self.file_var.set(path)

    def _load_api_key(self):
        load_dotenv(ENV_PATH)
        key = os.getenv("GEMINI_API_KEY", "")
        if key:
            self.api_var.set(key)

    # ---- 執行邏輯 ----
    def _start(self):
        api_key = self.api_var.get().strip()

        # 依來源模式驗證
        if self.source_mode.get() == "local":
            audio_path = self.file_var.get()
            if not audio_path:
                messagebox.showerror(t("gui.dlg.error.title"), t("gui.msg.no_file"))
                return
            source_info = {"mode": "local", "path": audio_path, "action": "transcribe"}
        else:
            url = self.yt_url_var.get().strip()
            save_path = self.yt_save_path_var.get().strip()
            if not url:
                messagebox.showerror(t("gui.dlg.error.title"), t("gui.msg.no_url"))
                return
            if not save_path:
                messagebox.showerror(t("gui.dlg.error.title"), t("gui.msg.no_save_path"))
                return
            source_info = {"mode": "youtube", "url": url, "save_path": save_path,
                           "action": self.yt_action.get()}

        download_only = source_info["action"] == "download_only"

        # 解析自訂切割點（只下載模式不需要）
        cut_points = None
        min_segment_seconds = MIN_SEGMENT_SECONDS
        if not download_only:
            if self.cut_mode.get() == "custom":
                try:
                    cut_points = parse_custom_cut_points(self.cut_text.get("1.0", "end"))
                except ValueError as e:
                    messagebox.showerror(t("gui.dlg.format_error.title"), str(e))
                    return
            else:
                # 尾巴合併門檻只在自動模式讀取，自訂模式不套用
                try:
                    min_segment_seconds = parse_min_segment_minutes(self.min_seg_var.get())
                except ValueError as e:
                    messagebox.showerror(t("gui.dlg.format_error.title"), str(e))
                    return

        # 解析擷取範圍（只下載模式不需要）
        range_bounds = None
        if not download_only and self.range_enabled.get():
            try:
                range_bounds = parse_range(
                    self.range_start_var.get(), self.range_end_var.get()
                )
            except ValueError as e:
                messagebox.showerror(t("gui.dlg.format_error.title"), str(e))
                return

        # 儲存 API Key（只下載模式不需要）
        if not download_only:
            if not api_key:
                messagebox.showerror(t("gui.dlg.error.title"), t("gui.msg.no_api_key"))
                return
            if self.save_key_var.get():
                set_key(ENV_PATH, "GEMINI_API_KEY", api_key)

        client = genai.Client(api_key=api_key) if not download_only else None

        # 重置 UI
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")
        self.output_label.config(text="")
        self.btn_open_folder.pack_forget()
        self.btn_retry_failed.pack_forget()
        self.progress_bar["value"] = 0
        self.progress_label.config(text=t("gui.status.preparing"))
        self.is_running = True
        self.btn_start.config(state="disabled")
        # 新任務開始前清掉上一個 job：若前置檢查（讀取音訊/切段）在
        # self._job 被重新賦值前就失敗，except 分支不能誤用上一個任務的
        # failed_count/audio_path（會導致補跑按鈕指向上一個音訊檔）
        self._job = None

        auto_retry = self.auto_retry_var.get()

        worker_thread = threading.Thread(
            target=self._worker,
            args=(source_info, cut_points, client, range_bounds, auto_retry,
                  min_segment_seconds),
            daemon=True,
        )
        worker_thread.start()

    def _worker(
        self,
        source_info: dict,
        cut_points: list[int] | None,
        client: genai.Client,
        range_bounds: tuple[int, int] | None,
        auto_retry: bool = False,
        min_segment_seconds: int = MIN_SEGMENT_SECONDS,
    ):
        """背景執行緒：（下載）+ 切割 + 上傳 + 轉錄 + 合併。

        只負責串流程與收尾，每個步驟的細節在各自的方法裡。
        """
        self.log_start_time = time.time()
        try:
            audio_path = self._resolve_audio_source(source_info)
            if audio_path is None:
                return   # 「只下載」模式已在 _resolve_audio_source 收尾

            segment_list = self._plan_and_announce(
                audio_path, cut_points, range_bounds, min_segment_seconds, auto_retry
            )

            self._job = job.TranscriptionJob(
                audio_path=audio_path,
                segment_list=segment_list,
                client=client,
                auto_retry=auto_retry,
                callbacks=job.JobCallbacks(
                    log=self._log,
                    progress=self._set_progress,
                    ask=self._ask_user,
                ),
            )
            output_path = self._job.run()

            self._log(t("gui.log.transcript_saved", path=output_path))
            self._finalize_log_file(success=self._job.failed_count == 0)
            self._done(output_path, success=True, failed_count=self._job.failed_count)

        except job.QuotaExhausted as e:
            # 不落檔：job.py 拋出前已經記過一行 429，這裡再記會變成同一件事兩行
            self._abort(e, log_label=None)
        except Exception as e:
            self._abort(e, log_label="轉錄中止")

    # ---- _worker 的步驟 ----
    def _resolve_audio_source(self, source_info: dict) -> str | None:
        """取得要轉錄的音訊路徑（YouTube 模式會先下載）。

        回傳 `None` 代表「只下載音訊」模式已經完成並收尾，呼叫端直接結束即可。
        """
        if source_info["mode"] != "youtube":
            return source_info["path"]

        self._log(t("gui.log.downloading"))
        audio_path, _ = download_youtube_audio(
            source_info["url"], source_info["save_path"],
            progress_callback=self._download_progress,
        )
        self._log(t("gui.log.download_done", name=os.path.basename(audio_path)))

        if source_info["action"] == "download_only":
            # 只下載：任務起始行只記檔名，不記完整 URL
            write_log_header(f"下載 {os.path.basename(audio_path)} | youtube")
            self._finalize_log_file(success=True)
            self._done(audio_path, success=True, download_only=True)
            return None
        return audio_path

    def _download_progress(self, downloaded: int, total: int, speed: str):
        """yt-dlp 的進度 hook（從 yt-dlp 的執行緒呼叫，只推 queue 不碰 widget）。"""
        speed_str = f"  {speed}" if speed else ""
        if total > 0:
            pct = int(downloaded / total * 100)
            mb_done = downloaded / 1024 / 1024
            mb_total = total / 1024 / 1024
            self._set_progress(
                pct, 100,
                t("gui.status.downloading_pct", percent=pct, done=f"{mb_done:.1f}",
                  total=f"{mb_total:.1f}", speed=speed_str),
            )
        else:
            # 沒有 total 的串流：只顯示已下載量，進度條停在 0
            mb = downloaded / 1024 / 1024
            self._set_progress(0, 100, t("gui.status.downloading_size",
                                        done=f"{mb:.1f}", speed=speed_str))

    def _plan_and_announce(
        self,
        audio_path: str,
        cut_points: list[int] | None,
        range_bounds: tuple[int, int] | None,
        min_segment_seconds: int,
        auto_retry: bool,
    ) -> list[tuple[int, int]]:
        """讀時長、算分段、寫任務起始行，回傳分段清單。"""
        self._log(t("gui.log.reading_audio", name=os.path.basename(audio_path)))
        total_duration = get_audio_duration(audio_path)
        self._log(t("gui.log.total_duration", duration=seconds_to_hms(total_duration)))

        # 自動切點與範圍夾擠的邏輯在 segments.plan_segments，放在那裡才測得到
        segment_list, range_start, range_end = plan_segments(
            total_duration, cut_points, range_bounds,
            min_segment_seconds=min_segment_seconds,
        )
        if range_bounds is not None:
            self._log(
                t("gui.log.range", start=seconds_to_hms(range_start),
                  end=seconds_to_hms(range_end))
            )

        # 任務起始行：檔名 + 模型 + 段數 + 重試設定，全塞同一行（不記 URL）
        write_log_header(
            f"轉錄 {os.path.basename(audio_path)} | {MODEL_NAME} | "
            f"{len(segment_list)}段 | 自動重試:{'開' if auto_retry else '關'}"
        )
        self._log(t("gui.log.segments_planned", count=len(segment_list)))
        self._set_progress(0, len(segment_list),
                          t("job.status.segments_done", done=0, total=len(segment_list)))
        return segment_list

    def _abort(self, e: Exception, log_label: str | None):
        """任務中止的共同收尾（轉錄與補跑都走這裡）。

        `log_label=None` 代表這個錯誤已經在別處落檔過，不要再記一次。
        落檔只記例外類型，不帶訊息全文（見 ARCHITECTURE.md 落檔紀律）。

        `self._job` 可能還是 None——前置步驟（下載、讀時長、分段）失敗時
        job 還沒建立，此時沒有輸出檔也沒有失敗段數。
        """
        self._log(f"\n[ERROR] {e}")
        if log_label is not None:
            write_log(f"{log_label} -> {type(e).__name__}", "ERROR")
        self._finalize_log_file(success=False)
        self._done(
            self._job.output_path if self._job else "",
            success=False,
            failed_count=self._job.failed_count if self._job else 0,
        )

    # ---- 執行紀錄（累積寫入 logs/app.log，供除錯查閱） ----
    def _finalize_log_file(self, success: bool):
        """任務結束：寫一行成功/失敗 + 耗時"""
        elapsed = int(time.time() - self.log_start_time)
        write_log(
            f"{'成功' if success else '失敗'}，耗時 {elapsed // 60}分{elapsed % 60}秒",
            "OK" if success else "FAIL",
        )

    # ---- 執行緒安全 UI 更新 ----
    def _ask_user(self, question: str) -> bool:
        """從背景執行緒呼叫，阻塞直到用戶在主執行緒回答 Yes/No"""
        reply_event = threading.Event()
        reply_holder = [False]
        self.msg_queue.put(("ask", (question, reply_event, reply_holder)))
        reply_event.wait()
        return reply_holder[0]

    def _log(self, msg: str):
        """推一行訊息到 UI queue。落檔改由呼叫端直接呼叫 write_log /
        write_log_header（只有任務起始、錯誤行、任務結果三種情況落檔，
        見 ARCHITECTURE.md 落檔紀律），這個方法本身不落檔。
        """
        self.msg_queue.put(("log", msg))

    def _set_progress(self, current: int, total: int, label: str):
        self.msg_queue.put(("progress", (current, total, label)))

    def _done(self, output_path: str, success: bool, download_only: bool = False,
              failed_count: int = 0):
        self.msg_queue.put(("done", (output_path, success, download_only, failed_count)))

    def _poll_queue(self):
        """每 100ms 從 queue 拉訊息更新 UI（主執行緒安全）"""
        try:
            while True:
                msg_type, data = self.msg_queue.get_nowait()
                if msg_type == "log":
                    self.log_text.config(state="normal")
                    self.log_text.insert("end", data + "\n")
                    self.log_text.see("end")
                    self.log_text.config(state="disabled")
                elif msg_type == "progress":
                    current, total, label = data
                    self.progress_bar["maximum"] = total
                    self.progress_bar["value"] = current
                    self.progress_label.config(text=label)
                elif msg_type == "ask":
                    question, reply_event, reply_holder = data
                    # 標題保持中性：這個 dialog 不只用於 503，Gemini 回傳空白結果
                    # 也走同一條路。實際原因寫在 question 裡。
                    reply_holder[0] = messagebox.askyesno(t("gui.dlg.transcribe_failed.title"), question)
                    reply_event.set()
                elif msg_type == "done":
                    output_path, success, download_only, failed_count = data
                    self.is_running = False
                    self.btn_start.config(state="normal")
                    if success:
                        self._last_output_path = output_path
                        self.btn_open_folder.pack(side="left")
                        if download_only:
                            self.output_label.config(
                                text=t("gui.lbl.downloaded", path=output_path),
                                foreground="green"
                            )
                            messagebox.showinfo(t("gui.dlg.download_done.title"),
                                                t("gui.dlg.download_done.body",
                                                  path=output_path))
                        elif failed_count > 0:
                            total = self._job.total
                            ok = total - failed_count
                            self.output_label.config(
                                text=t("gui.lbl.output_partial", path=output_path,
                                       ok=ok, total=total),
                                foreground="#b8860b",
                            )
                            self.btn_retry_failed.config(text=self._retry_button_text())
                            self.btn_retry_failed.pack(side="left", padx=(6, 0))
                            messagebox.showwarning(
                                t("gui.dlg.partial.title"),
                                t("gui.dlg.partial.body", ok=ok, total=total,
                                  detail=self._unfinished_wording(),
                                  path=output_path,
                                  button=self._retry_button_text()),
                            )
                        else:
                            self.btn_retry_failed.pack_forget()
                            self.output_label.config(
                                text=t("gui.lbl.output", path=output_path),
                                foreground="green"
                            )
                            messagebox.showinfo(t("gui.dlg.done.title"),
                                                t("gui.dlg.done.body", path=output_path))
                    else:
                        self.progress_label.config(text=t("gui.status.error"))
                        if output_path:
                            # 中止前已完成的段落仍先存了檔（見 job.py 的中止保護），
                            # 使用者要能找到這份部分逐字稿，不能讓它悄悄躺在磁碟上
                            self._last_output_path = output_path
                            self.btn_open_folder.pack(side="left")
                            self.output_label.config(
                                text=t("gui.lbl.output_aborted", path=output_path),
                                foreground="#b8860b",
                            )
                        if failed_count > 0:
                            self.btn_retry_failed.config(text=self._retry_button_text())
                            self.btn_retry_failed.pack(side="left", padx=(6, 0))
        except queue.Empty:
            pass
        self._poll_after_id = self.root.after(100, self._poll_queue)
