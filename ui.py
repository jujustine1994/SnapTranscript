"""SnapTranscript 主視窗（tkinter）。"""

import os
import queue
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import ttk, filedialog, messagebox, scrolledtext

from dotenv import load_dotenv, set_key
from google import genai

import job
from audio import download_youtube_audio, get_audio_duration
from config import ENV_PATH, MODEL_NAME
from logger import write_log, write_log_header
from segments import (
    parse_custom_cut_points,
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

        self._build_ui()
        self._load_api_key()
        self._poll_queue()

    # ---- UI 建置 ----
    def _build_ui(self):
        pad = {"padx": 14, "pady": 6}

        # 音訊來源
        frame_source = ttk.LabelFrame(self.root, text=" 音訊來源 ", padding=8)
        frame_source.grid(row=0, column=0, sticky="ew", **pad)
        frame_source.columnconfigure(0, weight=1)

        # Radio：本地上傳 / YouTube 下載
        radio_row = ttk.Frame(frame_source)
        radio_row.grid(row=0, column=0, sticky="w", pady=(0, 6))
        ttk.Radiobutton(
            radio_row, text="本地上傳",
            variable=self.source_mode, value="local",
            command=self._toggle_source_mode,
        ).pack(side="left", padx=(0, 16))
        ttk.Radiobutton(
            radio_row, text="YouTube 下載",
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
        ttk.Button(self.frame_local, text="選擇檔案", command=self._select_file).grid(
            row=0, column=1
        )

        # YouTube 下載 UI
        self.frame_youtube = ttk.Frame(frame_source)
        self.frame_youtube.grid(row=1, column=0, sticky="ew")
        self.frame_youtube.columnconfigure(1, weight=1)
        ttk.Label(self.frame_youtube, text="YouTube 網址：").grid(
            row=0, column=0, sticky="w", padx=(0, 6)
        )
        ttk.Entry(self.frame_youtube, textvariable=self.yt_url_var).grid(
            row=0, column=1, columnspan=2, sticky="ew"
        )
        ttk.Label(self.frame_youtube, text="儲存為：").grid(
            row=1, column=0, sticky="w", padx=(0, 6), pady=(6, 0)
        )
        ttk.Entry(self.frame_youtube, textvariable=self.yt_save_path_var, state="readonly").grid(
            row=1, column=1, sticky="ew", padx=(0, 8), pady=(6, 0)
        )
        ttk.Button(self.frame_youtube, text="另存新檔", command=self._select_save_path).grid(
            row=1, column=2, pady=(6, 0)
        )
        action_frame = ttk.Frame(self.frame_youtube)
        action_frame.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Radiobutton(
            action_frame, text="下載後馬上轉錄",
            variable=self.yt_action, value="transcribe",
            command=self._update_btn_label,
        ).pack(side="left", padx=(0, 16))
        ttk.Radiobutton(
            action_frame, text="只下載音訊（不需 API Key）",
            variable=self.yt_action, value="download_only",
            command=self._update_btn_label,
        ).pack(side="left")
        self.frame_youtube.grid_remove()  # 預設隱藏

        # 擷取範圍
        self.frame_range = ttk.LabelFrame(self.root, text=" 擷取範圍 ", padding=8)
        self.frame_range.grid(row=1, column=0, sticky="ew", **pad)

        ttk.Checkbutton(
            self.frame_range, text="只處理音訊的一部分",
            variable=self.range_enabled, command=self._toggle_range_mode,
        ).grid(row=0, column=0, sticky="w")

        self.frame_range_inputs = ttk.Frame(self.frame_range)
        self.frame_range_inputs.grid(row=1, column=0, sticky="w", padx=(20, 0), pady=(6, 0))
        ttk.Label(self.frame_range_inputs, text="起始時間：").grid(row=0, column=0, sticky="w")
        ttk.Entry(self.frame_range_inputs, textvariable=self.range_start_var, width=10).grid(
            row=0, column=1, padx=(0, 16)
        )
        ttk.Label(self.frame_range_inputs, text="結束時間：").grid(row=0, column=2, sticky="w")
        ttk.Entry(self.frame_range_inputs, textvariable=self.range_end_var, width=10).grid(
            row=0, column=3
        )
        ttk.Label(self.frame_range_inputs, text="（HH:MM:SS，例如 00:10:00）").grid(
            row=1, column=0, columnspan=4, sticky="w", pady=(2, 0)
        )
        self.frame_range_inputs.grid_remove()  # 預設隱藏

        tk.Label(
            self.frame_range,
            text="⚠️ 下方切割點為原始音訊的絕對時間，需落在此範圍內才會生效",
            foreground="gray", font=("", 8),
        ).grid(row=2, column=0, sticky="w", pady=(6, 0))

        # 切割設定
        self.frame_cut = ttk.LabelFrame(self.root, text=" 切割設定 ", padding=8)
        self.frame_cut.grid(row=2, column=0, sticky="ew", **pad)
        frame_cut = self.frame_cut

        self.cut_mode = tk.StringVar(value="auto")
        ttk.Radiobutton(
            frame_cut, text="自動（每 30 分鐘切一段）",
            variable=self.cut_mode, value="auto", command=self._toggle_cut_mode,
        ).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(
            frame_cut, text="自訂切割點",
            variable=self.cut_mode, value="custom", command=self._toggle_cut_mode,
        ).grid(row=1, column=0, sticky="w")

        self.frame_custom = ttk.Frame(frame_cut)
        self.frame_custom.grid(row=2, column=0, sticky="ew", padx=(20, 0), pady=(6, 0))
        ttk.Label(self.frame_custom, text="輸入切割時間點（HH:MM:SS，每行一個）：").pack(anchor="w")
        self.cut_text = scrolledtext.ScrolledText(
            self.frame_custom, width=28, height=5, font=("Consolas", 10)
        )
        self.cut_text.pack(fill="x")
        self.cut_text.insert("1.0", "00:30:00\n01:00:00")
        self.frame_custom.grid_remove()  # 預設隱藏

        # API Key
        self.frame_api = ttk.LabelFrame(self.root, text=" Gemini API Key ", padding=8)
        self.frame_api.grid(row=3, column=0, sticky="ew", **pad)

        api_row = tk.Frame(self.frame_api)
        api_row.pack(anchor="w")
        self.api_var = tk.StringVar()
        self.api_entry = ttk.Entry(api_row, textvariable=self.api_var, width=40, show="•")
        self.api_entry.pack(side="left", padx=(0, 8))
        ttk.Button(api_row, text="顯示", width=5, command=self._toggle_api_show).pack(
            side="left", padx=(0, 8)
        )
        self.save_key_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(api_row, text="記住", variable=self.save_key_var).pack(side="left")

        tk.Label(
            self.frame_api,
            text="🔒 API Key 僅儲存於本機 .env 檔，請勿將 Key 提供給他人。",
            foreground="gray", font=("", 8),
        ).pack(anchor="w", pady=(4, 0))

        # 開始按鈕列（如何取得？ 左邊，開始轉錄 置中）
        frame_start = tk.Frame(self.root)
        frame_start.grid(row=4, column=0, sticky="ew", padx=14, pady=10)
        frame_start.columnconfigure(0, weight=1)
        frame_start.columnconfigure(1, weight=1)
        frame_start.columnconfigure(2, weight=1)

        link = tk.Label(
            frame_start, text="如何取得 API Key？",
            foreground="#0078D4", cursor="hand2", font=("", 9, "underline")
        )
        link.grid(row=0, column=0, sticky="w")
        link.bind("<Button-1>", lambda e: self._show_api_help())

        self.btn_start = ttk.Button(
            frame_start, text="▶  開始轉錄", command=self._start, width=20
        )
        self.btn_start.grid(row=0, column=1, ipady=6)

        ttk.Checkbutton(
            frame_start, text="自動重試", variable=self.auto_retry_var,
        ).grid(row=0, column=2, sticky="w", padx=(10, 0))


        # 進度區
        frame_progress = ttk.LabelFrame(self.root, text=" 處理進度 ", padding=8)
        frame_progress.grid(row=5, column=0, sticky="ew", padx=14, pady=(6, 14))

        self.progress_label = ttk.Label(frame_progress, text="等待開始...")
        self.progress_label.pack(anchor="w")
        self.progress_bar = ttk.Progressbar(frame_progress, mode="determinate")
        self.progress_bar.pack(fill="x", pady=(4, 8))
        self.log_text = scrolledtext.ScrolledText(
            frame_progress, width=56, height=8, state="disabled", font=("Consolas", 9)
        )
        self.log_text.pack(fill="x")

        # 輸出路徑 + 開啟資料夾
        frame_output = tk.Frame(self.root)
        frame_output.grid(row=6, column=0, pady=(0, 12))
        # wraplength 220：兩顆按鈕（開啟資料夾 87 + 重試失敗的 N 段 ~100+）
        # 同時顯示時，長路徑改換行而非把視窗撐寬，見 task-9-report.md Finding 3
        self.output_label = ttk.Label(
            frame_output, text="", foreground="gray", wraplength=220, justify="left"
        )
        self.output_label.pack(side="left", padx=(0, 8))
        self.btn_open_folder = ttk.Button(
            frame_output, text="開啟資料夾", command=self._open_output_folder
        )
        # 預設隱藏，完成後才顯示
        self.btn_retry_failed = ttk.Button(
            frame_output, text="重試失敗的段落", command=self._retry_failed
        )
        # 預設隱藏，有失敗段落時才顯示

        # 初始引導文字
        self.log_text.config(state="normal")
        self.log_text.insert("1.0", "請選擇音訊來源，設定完成後按「開始」。\n")
        self.log_text.config(state="disabled")

        self.root.columnconfigure(0, weight=1)

    # ---- UI 互動 ----
    def _show_api_help(self):
        win = tk.Toplevel(self.root)
        win.title("如何取得 Gemini API Key")
        win.resizable(False, False)
        win.grab_set()  # 鎖定焦點在此視窗

        pad = {"padx": 20, "pady": 6}

        ttk.Label(win, text="申請步驟", font=("", 11, "bold")).pack(anchor="w", padx=20, pady=(16, 4))

        steps = [
            "1. 點擊下方連結，前往 Google AI Studio",
            "2. 使用 Google 帳號登入",
            "3. 點擊「Create API key」",
            "4. 選擇「Create API key in new project」",
            "5. 複製產生的 Key，貼入 SnapTranscript 的 API Key 欄位",
        ]
        for step in steps:
            ttk.Label(win, text=step, justify="left").pack(anchor="w", **pad)

        # 注意事項
        notice_frame = tk.Frame(win, background="#FFF3CD", padx=12, pady=10)
        notice_frame.pack(fill="x", padx=20, pady=(8, 4))
        tk.Label(
            notice_frame,
            text="⚠️  注意：申請後請確認 API Key 狀態顯示為「Free tier」，\n"
                 "若顯示「Set up billing」代表尚未啟用免費方案，\n"
                 "請勿輸入信用卡，直接使用即可享有免費額度。",
            justify="left", background="#FFF3CD", foreground="#856404"
        ).pack(anchor="w")

        # 可點擊超連結
        url = "https://aistudio.google.com/apikey"
        link = tk.Label(win, text=url, foreground="#0078D4", cursor="hand2",
                        font=("", 9, "underline"))
        link.pack(anchor="w", padx=20, pady=(4, 16))
        link.bind("<Button-1>", lambda e: webbrowser.open(url))

        ttk.Button(win, text="關閉", command=win.destroy).pack(pady=(0, 16))

    def _toggle_cut_mode(self):
        if self.cut_mode.get() == "custom":
            self.frame_custom.grid()
        else:
            self.frame_custom.grid_remove()
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
            self.btn_start.config(text="▶  開始下載")
            self._set_widgets_state(self.frame_range, "disabled")
            self._set_widgets_state(self.frame_cut, "disabled")
            self._set_widgets_state(self.frame_api, "disabled")
        else:
            self.btn_start.config(text="▶  開始轉錄")
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
            return "重試失敗的段落"
        n = self._job.failed_count
        if self._job.pending_count > 0:
            return f"繼續未完成的 {n} 段"
        return f"重試失敗的 {n} 段"

    def _unfinished_wording(self) -> str:
        """「部分完成」對話框裡描述未完成段落的措辭。"""
        if self._job is None:
            return "部分段落未完成"
        failed, pending = self._job.attempted_failed_count, self._job.pending_count
        parts = []
        if failed:
            parts.append(f"{failed} 段失敗")
        if pending:
            parts.append(f"{pending} 段未處理")
        return "、".join(parts) or "部分段落未完成"

    def _retry_failed(self):
        """只補跑失敗的段落（背景執行緒）。"""
        if self._job is None or self._job.failed_count == 0:
            return
        if not os.path.exists(self._job.audio_path):
            messagebox.showerror(
                "找不到音訊檔",
                f"原始音訊已不存在，無法補跑：\n{self._job.audio_path}",
            )
            return

        self.is_running = True
        self.btn_start.config(state="disabled")
        self.btn_retry_failed.pack_forget()
        self._log(f"\n開始補跑 {self._job.failed_count} 個失敗段落...")

        t = threading.Thread(target=self._retry_worker, daemon=True)
        t.start()

    def _retry_worker(self):
        """背景執行緒：只跑失敗段落，成功後重新合併覆寫輸出檔。"""
        self.log_start_time = time.time()
        try:
            write_log_header(
                f"補跑 {os.path.basename(self._job.audio_path)} | {MODEL_NAME} | "
                f"{self._job.failed_count}段"
            )
            output_path = self._job.retry_failed()
            self._log(f"\n逐字稿已更新：{output_path}")
            self._finalize_log_file(success=self._job.failed_count == 0)
            self._done(output_path, success=True, failed_count=self._job.failed_count)
        except job.QuotaExhausted as e:
            self._log(f"\n[ERROR] {e}")
            self._finalize_log_file(success=False)
            self._done(self._job.output_path, success=False, failed_count=self._job.failed_count)
        except Exception as e:
            self._log(f"\n[ERROR] {e}")
            write_log(f"補跑中止 -> {type(e).__name__}", "ERROR")
            self._finalize_log_file(success=False)
            self._done(self._job.output_path, success=False, failed_count=self._job.failed_count)

    def _select_save_path(self):
        path = filedialog.asksaveasfilename(
            title="選擇儲存位置與檔名",
            defaultextension=".mp3",
            filetypes=[("MP3 音訊", "*.mp3"), ("所有檔案", "*.*")],
        )
        if path:
            self.yt_save_path_var.set(path)

    def _select_file(self):
        path = filedialog.askopenfilename(
            title="選擇音訊檔案",
            filetypes=[
                ("音訊檔案", "*.mp3 *.wav *.m4a *.aac *.flac *.ogg *.wma *.mp4 *.mov *.mkv"),
                ("所有檔案", "*.*"),
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
                messagebox.showerror("錯誤", "請先選擇音訊檔案")
                return
            source_info = {"mode": "local", "path": audio_path, "action": "transcribe"}
        else:
            url = self.yt_url_var.get().strip()
            save_path = self.yt_save_path_var.get().strip()
            if not url:
                messagebox.showerror("錯誤", "請輸入 YouTube 網址")
                return
            if not save_path:
                messagebox.showerror("錯誤", "請點「另存新檔」選擇儲存位置與檔名")
                return
            source_info = {"mode": "youtube", "url": url, "save_path": save_path,
                           "action": self.yt_action.get()}

        download_only = source_info["action"] == "download_only"

        # 解析自訂切割點（只下載模式不需要）
        cut_points = None
        if not download_only and self.cut_mode.get() == "custom":
            try:
                cut_points = parse_custom_cut_points(self.cut_text.get("1.0", "end"))
            except ValueError as e:
                messagebox.showerror("格式錯誤", str(e))
                return

        # 解析擷取範圍（只下載模式不需要）
        range_bounds = None
        if not download_only and self.range_enabled.get():
            try:
                range_bounds = parse_range(
                    self.range_start_var.get(), self.range_end_var.get()
                )
            except ValueError as e:
                messagebox.showerror("格式錯誤", str(e))
                return

        # 儲存 API Key（只下載模式不需要）
        if not download_only:
            if not api_key:
                messagebox.showerror("錯誤", "請輸入 Gemini API Key")
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
        self.progress_label.config(text="準備中...")
        self.is_running = True
        self.btn_start.config(state="disabled")
        # 新任務開始前清掉上一個 job：若前置檢查（讀取音訊/切段）在
        # self._job 被重新賦值前就失敗，except 分支不能誤用上一個任務的
        # failed_count/audio_path（會導致補跑按鈕指向上一個音訊檔）
        self._job = None

        auto_retry = self.auto_retry_var.get()

        t = threading.Thread(
            target=self._worker,
            args=(source_info, cut_points, client, range_bounds, auto_retry),
            daemon=True,
        )
        t.start()

    def _worker(
        self,
        source_info: dict,
        cut_points: list[int] | None,
        client: genai.Client,
        range_bounds: tuple[int, int] | None,
        auto_retry: bool = False,
    ):
        """背景執行緒：（下載）+ 切割 + 上傳 + 轉錄 + 合併"""
        self.log_start_time = time.time()
        try:
            if source_info["mode"] == "youtube":
                self._log("正在下載 YouTube 音訊，請稍候...")

                def _dl_progress(downloaded, total, speed):
                    speed_str = f"  {speed}" if speed else ""
                    if total > 0:
                        pct = int(downloaded / total * 100)
                        mb_done = downloaded / 1024 / 1024
                        mb_total = total / 1024 / 1024
                        self._set_progress(
                            pct, 100,
                            f"下載中... {pct}%  ({mb_done:.1f} / {mb_total:.1f} MB{speed_str})"
                        )
                    else:
                        mb = downloaded / 1024 / 1024
                        self._set_progress(0, 100, f"下載中... {mb:.1f} MB{speed_str}")

                audio_path, _ = download_youtube_audio(
                    source_info["url"], source_info["save_path"],
                    progress_callback=_dl_progress,
                )
                self._log(f"下載完成：{os.path.basename(audio_path)}")
                if source_info["action"] == "download_only":
                    # 只下載：任務起始行只記檔名，不記完整 URL
                    write_log_header(f"下載 {os.path.basename(audio_path)} | youtube")
                    self._finalize_log_file(success=True)
                    self._done(audio_path, success=True, download_only=True)
                    return
            else:
                audio_path = source_info["path"]

            self._log(f"讀取音訊：{os.path.basename(audio_path)}")
            total_duration = get_audio_duration(audio_path)
            self._log(f"總時長：{seconds_to_hms(total_duration)}")

            # 建立分段清單（自動切點與範圍夾擠的邏輯在 segments.plan_segments，
            # 放在那裡才測得到，見 segments.py 的說明）
            segment_list, range_start, range_end = plan_segments(
                total_duration, cut_points, range_bounds
            )
            if range_bounds is not None:
                self._log(
                    f"擷取範圍：{seconds_to_hms(range_start)} → {seconds_to_hms(range_end)}"
                )

            # 任務起始行：檔名 + 模型 + 段數 + 重試設定，全塞同一行（不記 URL）
            write_log_header(
                f"轉錄 {os.path.basename(audio_path)} | {MODEL_NAME} | "
                f"{len(segment_list)}段 | 自動重試:{'開' if auto_retry else '關'}"
            )
            self._log(f"共 {len(segment_list)} 段，開始處理...")
            self._set_progress(0, len(segment_list), f"0 / {len(segment_list)} 段完成")

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

            self._log(f"\n逐字稿已儲存：{output_path}")
            self._finalize_log_file(success=self._job.failed_count == 0)
            self._done(output_path, success=True, failed_count=self._job.failed_count)

        except job.QuotaExhausted as e:
            self._log(f"\n[ERROR] {e}")
            self._finalize_log_file(success=False)
            self._done(self._job.output_path if self._job else "", success=False,
                       failed_count=self._job.failed_count if self._job else 0)
        except Exception as e:
            self._log(f"\n[ERROR] {e}")
            write_log(f"轉錄中止 -> {type(e).__name__}", "ERROR")
            self._finalize_log_file(success=False)
            self._done(self._job.output_path if self._job else "", success=False,
                       failed_count=self._job.failed_count if self._job else 0)

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
                    reply_holder[0] = messagebox.askyesno("轉錄失敗", question)
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
                                text=f"已下載：{output_path}", foreground="green"
                            )
                            messagebox.showinfo("下載完成", f"音訊已儲存至：\n{output_path}")
                        elif failed_count > 0:
                            total = self._job.total
                            ok = total - failed_count
                            self.output_label.config(
                                text=f"輸出：{output_path}（{ok}/{total} 段成功）",
                                foreground="#b8860b",
                            )
                            self.btn_retry_failed.config(text=self._retry_button_text())
                            self.btn_retry_failed.pack(side="left", padx=(6, 0))
                            messagebox.showwarning(
                                "部分完成",
                                f"逐字稿已儲存（{ok}/{total} 段成功，"
                                f"{self._unfinished_wording()}）：\n"
                                f"{output_path}\n\n"
                                "未完成的段落在檔案中標記為佔位符，"
                                f"可按「{self._retry_button_text()}」補跑。",
                            )
                        else:
                            self.btn_retry_failed.pack_forget()
                            self.output_label.config(
                                text=f"輸出：{output_path}", foreground="green"
                            )
                            messagebox.showinfo("完成", f"逐字稿已儲存：\n{output_path}")
                    else:
                        self.progress_label.config(text="發生錯誤，請查看上方記錄")
                        if output_path:
                            # 中止前已完成的段落仍先存了檔（見 job.py 的中止保護），
                            # 使用者要能找到這份部分逐字稿，不能讓它悄悄躺在磁碟上
                            self._last_output_path = output_path
                            self.btn_open_folder.pack(side="left")
                            self.output_label.config(
                                text=f"輸出（部分完成）：{output_path}",
                                foreground="#b8860b",
                            )
                        if failed_count > 0:
                            self.btn_retry_failed.config(text=self._retry_button_text())
                            self.btn_retry_failed.pack(side="left", padx=(6, 0))
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)
