"""
SnapTranscript — 會議音訊逐字稿工具
將音訊檔案分段切割，透過 Gemini AI 生成逐字稿，合併輸出為單一 TXT 檔案。
"""

import os
import re
import time
import queue
import threading
import subprocess
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

import yt_dlp
from google import genai
from dotenv import load_dotenv, set_key

# ---- 常數 ----
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(SCRIPT_DIR, ".env")
DEFAULT_CHUNK_SECONDS = 30 * 60  # 預設 30 分鐘
MODEL_NAME = "gemini-flash-latest"


# ---- CTH Banner ----
def show_cth_banner():
    b = "\033[90m"   # 邊框：深灰
    c = "\033[96m"   # CTH 字母：亮青
    y = "\033[93m"   # 署名：金黃
    r = "\033[0m"    # reset

    print(f"{b}/*  ================================  *\\{r}")
    print(f"{b} *                                    *{r}")
    print(f"{b} *    {c}██████╗████████╗██╗  ██╗{b}        *{r}")
    print(f"{b} *   {c}██╔════╝   ██║   ██║  ██║{b}        *{r}")
    print(f"{b} *   {c}██║        ██║   ███████║{b}        *{r}")
    print(f"{b} *   {c}██║        ██║   ██╔══██║{b}        *{r}")
    print(f"{b} *   {c}╚██████╗   ██║   ██║  ██║{b}        *{r}")
    print(f"{b} *    {c}╚═════╝   ╚═╝   ╚═╝  ╚═╝{b}        *{r}")
    print(f"{b} *                                    *{r}")
    print(f"{b} *          {y}created by CTH{b}            *{r}")
    print(f"{b}\\*  ================================  */{r}")
    print()


# ---- 時間工具 ----
def hms_to_seconds(hms: str) -> int:
    """HH:MM:SS → 秒數"""
    parts = hms.strip().split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + int(s)
    if len(parts) == 2:
        m, s = parts
        return int(m) * 60 + int(s)
    return int(parts[0])


def seconds_to_hms(seconds: float) -> str:
    """秒數 → HH:MM:SS"""
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def parse_custom_cut_points(text: str) -> list[int]:
    """
    解析自訂切割點文字（每行一個 HH:MM:SS），回傳排序後的秒數清單。
    格式錯誤時拋出 ValueError。
    """
    pattern = re.compile(r"^\d{1,2}:\d{2}:\d{2}$")
    points = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if not pattern.match(line):
            raise ValueError(f"格式錯誤：「{line}」，請使用 HH:MM:SS 格式（例如 00:22:30）")
        points.append(hms_to_seconds(line))
    return sorted(set(points))


def build_segments(cut_points: list[int], total_duration: float) -> list[tuple[int, int]]:
    """從切割點建立 (start_sec, end_sec) 清單"""
    boundaries = [0] + cut_points + [int(total_duration)]
    segments = []
    for i in range(len(boundaries) - 1):
        start = boundaries[i]
        end = min(boundaries[i + 1], int(total_duration))
        if end > start:
            segments.append((start, end))
    return segments


# ---- 音訊處理 ----
def get_audio_duration(audio_path: str) -> float:
    """用 ffprobe 取得音訊總時長（秒）"""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path,
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return float(result.stdout.strip())


def cut_audio_segment(audio_path: str, start_sec: int, duration_sec: int, output_path: str):
    """用 ffmpeg 切割指定時段，優先 copy codec，失敗再重新編碼"""
    base_cmd = ["ffmpeg", "-ss", str(start_sec), "-t", str(duration_sec), "-i", audio_path]

    # 嘗試 copy（速度快，不重新編碼）
    result = subprocess.run(
        base_cmd + ["-acodec", "copy", "-y", output_path],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        # 回退：重新編碼為 mp3
        subprocess.run(
            base_cmd + ["-acodec", "libmp3lame", "-y", output_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )


# ---- YouTube 下載 ----
def download_youtube_audio(url: str, save_path: str, progress_callback=None) -> tuple[str, str]:
    """用 yt-dlp 下載 YouTube 音訊（原始最佳音質轉 mp3），回傳 (音訊路徑, 影片標題)"""
    # outtmpl 使用指定路徑（去掉副檔名讓 yt-dlp 自行補）
    outtmpl = os.path.splitext(save_path)[0] + ".%(ext)s"
    result = {}

    def _hook(d):
        if d["status"] == "downloading" and progress_callback:
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            speed = (d.get("_speed_str") or "").strip()
            progress_callback(downloaded, total, speed)
        elif d["status"] == "finished":
            result["pre_path"] = d["filename"]

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
        "progress_hooks": [_hook],
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "youtube_audio")

    # postprocessor 轉完後副檔名一定是 .mp3
    audio_path = os.path.splitext(save_path)[0] + ".mp3"

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"下載後找不到音訊檔案：{audio_path}")

    return audio_path, title


# ---- Gemini 逐字稿 ----
def transcribe_segment(audio_path: str, client: genai.Client) -> str:
    """上傳音訊至 Gemini，取得純文字逐字稿"""
    audio_file = client.files.upload(file=audio_path)
    while audio_file.state.name == "PROCESSING":
        time.sleep(2)
        audio_file = client.files.get(name=audio_file.name)

    prompt = """請仔細聆聽這段音訊，將所有說話內容以原始語言逐字轉錄。

輸出規則：
1. 純文字輸出，不需要時間戳、編號或任何 JSON / Markdown 格式
2. 依照說話者使用的語言直接轉錄原文，不需翻譯
3. 同一說話者的連續發言合併為一個段落，說話者切換時才換段並空一行
4. 每段開頭標註說話者：優先使用音訊中可辨識的真實姓名或職稱（如「財務長：」「主持人：」），無法辨識則使用「說話者 A：」「說話者 B：」等泛用標籤
5. 背景雜音、靜默段、非語言音（笑聲、清喉嚨等）不需輸出
6. 盡力辨識模糊語音，結合前後文補全語意，忠實呈現內容，不要摘要或省略"""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=[prompt, audio_file],
    )
    client.files.delete(name=audio_file.name)
    return response.text.strip()


# ---- 主視窗 ----
class SnapTranscriptApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("SnapTranscript")
        self.root.resizable(False, False)

        self.msg_queue: queue.Queue = queue.Queue()
        self.is_running = False
        self.temp_files: list[str] = []
        self.source_mode = tk.StringVar(value="local")
        self.yt_url_var = tk.StringVar()
        self.yt_save_path_var = tk.StringVar()
        self.yt_action = tk.StringVar(value="transcribe")

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

        # 切割設定
        frame_cut = ttk.LabelFrame(self.root, text=" 切割設定 ", padding=8)
        frame_cut.grid(row=1, column=0, sticky="ew", **pad)

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
        frame_api = ttk.LabelFrame(self.root, text=" Gemini API Key ", padding=8)
        frame_api.grid(row=2, column=0, sticky="ew", **pad)

        self.api_var = tk.StringVar()
        self.api_entry = ttk.Entry(frame_api, textvariable=self.api_var, width=50, show="•")
        self.api_entry.pack(side="left", padx=(0, 8))
        ttk.Button(frame_api, text="顯示", width=5, command=self._toggle_api_show).pack(
            side="left", padx=(0, 8)
        )
        self.save_key_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame_api, text="記住", variable=self.save_key_var).pack(side="left")

        # 開始按鈕列（如何取得？ 左邊，開始轉錄 置中）
        frame_start = tk.Frame(self.root)
        frame_start.grid(row=3, column=0, sticky="ew", padx=14, pady=10)
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


        # 進度區
        frame_progress = ttk.LabelFrame(self.root, text=" 處理進度 ", padding=8)
        frame_progress.grid(row=4, column=0, sticky="ew", padx=14, pady=(6, 14))

        self.progress_label = ttk.Label(frame_progress, text="等待開始...")
        self.progress_label.pack(anchor="w")
        self.progress_bar = ttk.Progressbar(frame_progress, length=490, mode="determinate")
        self.progress_bar.pack(fill="x", pady=(4, 8))
        self.log_text = scrolledtext.ScrolledText(
            frame_progress, width=66, height=8, state="disabled", font=("Consolas", 9)
        )
        self.log_text.pack(fill="x")

        # 輸出路徑
        self.output_label = ttk.Label(self.root, text="", foreground="gray")
        self.output_label.grid(row=5, column=0, pady=(0, 12))

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

    def _update_btn_label(self):
        if self.source_mode.get() == "youtube" and self.yt_action.get() == "download_only":
            self.btn_start.config(text="▶  開始下載")
        else:
            self.btn_start.config(text="▶  開始轉錄")

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
        self.progress_bar["value"] = 0
        self.progress_label.config(text="準備中...")
        self.is_running = True
        self.btn_start.config(state="disabled")

        t = threading.Thread(
            target=self._worker, args=(source_info, cut_points, client), daemon=True
        )
        t.start()

    def _worker(self, source_info: dict, cut_points: list[int] | None, client: genai.Client):
        """背景執行緒：（下載）+ 切割 + 上傳 + 轉錄 + 合併"""
        temp_files: list[str] = []
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
                    self._done(audio_path, success=True, download_only=True)
                    return
            else:
                audio_path = source_info["path"]

            self._log(f"讀取音訊：{os.path.basename(audio_path)}")
            total_duration = get_audio_duration(audio_path)
            self._log(f"總時長：{seconds_to_hms(total_duration)}")

            # 建立分段清單
            if cut_points is None:
                # 自動模式：每 30 分鐘一刀
                auto_points = list(
                    range(DEFAULT_CHUNK_SECONDS, int(total_duration), DEFAULT_CHUNK_SECONDS)
                )
                segments = build_segments(auto_points, total_duration)
            else:
                valid_points = [p for p in cut_points if 0 < p < total_duration]
                segments = build_segments(valid_points, total_duration)

            self._log(f"共 {len(segments)} 段，開始處理...")
            self._set_progress(0, len(segments), f"0 / {len(segments)} 段完成")

            transcripts = []
            ext = os.path.splitext(audio_path)[1] or ".mp3"

            for i, (start_sec, end_sec) in enumerate(segments):
                start_hms = seconds_to_hms(start_sec)
                end_hms = seconds_to_hms(end_sec)
                duration_sec = end_sec - start_sec

                self._log(f"\n[{i + 1}/{len(segments)}] 切割 {start_hms} → {end_hms}...")

                temp_path = os.path.join(SCRIPT_DIR, f"_temp_seg_{i}{ext}")
                temp_files.append(temp_path)
                cut_audio_segment(audio_path, start_sec, duration_sec, temp_path)

                if not os.path.exists(temp_path):
                    raise Exception(f"第 {i + 1} 段切割失敗，請確認 ffmpeg 是否正常運作")

                self._log(f"[{i + 1}/{len(segments)}] 上傳至 Gemini，等待轉錄...")
                transcript = transcribe_segment(temp_path, client)
                transcripts.append((i + 1, start_hms, end_hms, transcript))
                self._log(f"[{i + 1}/{len(segments)}] 完成")
                self._set_progress(i + 1, len(segments), f"{i + 1} / {len(segments)} 段完成")

                os.remove(temp_path)
                temp_files.remove(temp_path)

            # 合併逐字稿
            self._log("\n合併逐字稿...")
            lines = []
            for idx, start_hms, end_hms, text in transcripts:
                lines.append(f"=== 第 {idx} 段（{start_hms} - {end_hms}）===")
                lines.append("")
                lines.append(text)
                lines.append("")

            merged = "\n".join(lines).strip()
            base = os.path.splitext(audio_path)[0]
            output_path = base + "_transcript.txt"
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(merged)

            self._log(f"\n逐字稿已儲存：{output_path}")
            self._done(output_path, success=True)

        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower() or "exhausted" in err.lower():
                self._log("\n[ERROR] API 免費用量已達上限，請等明天配額重置後再試")
            else:
                self._log(f"\n[ERROR] {e}")
            self._done("", success=False)
        finally:
            for f in temp_files:
                if os.path.exists(f):
                    os.remove(f)

    # ---- 執行緒安全 UI 更新 ----
    def _log(self, msg: str):
        self.msg_queue.put(("log", msg))

    def _set_progress(self, current: int, total: int, label: str):
        self.msg_queue.put(("progress", (current, total, label)))

    def _done(self, output_path: str, success: bool, download_only: bool = False):
        self.msg_queue.put(("done", (output_path, success, download_only)))

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
                elif msg_type == "done":
                    output_path, success, download_only = data
                    self.is_running = False
                    self.btn_start.config(state="normal")
                    if success:
                        if download_only:
                            self.output_label.config(
                                text=f"已下載：{output_path}", foreground="green"
                            )
                            messagebox.showinfo("下載完成", f"音訊已儲存至：\n{output_path}")
                        else:
                            self.output_label.config(
                                text=f"輸出：{output_path}", foreground="green"
                            )
                            messagebox.showinfo("完成", f"逐字稿已儲存：\n{output_path}")
                    else:
                        self.progress_label.config(text="發生錯誤，請查看上方記錄")
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)


# ---- 入口 ----
def main():
    show_cth_banner()
    root = tk.Tk()
    SnapTranscriptApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
