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
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

from google import genai
from dotenv import load_dotenv, set_key

# ---- 常數 ----
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(SCRIPT_DIR, ".env")
DEFAULT_CHUNK_SECONDS = 20 * 60  # 預設 20 分鐘
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
3. 依說話順序逐句輸出，句與句之間空一行
4. 若能明確分辨不同說話者，在每句前加「說話者 A：」「說話者 B：」等標記
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

        self._build_ui()
        self._load_api_key()
        self._poll_queue()

    # ---- UI 建置 ----
    def _build_ui(self):
        pad = {"padx": 14, "pady": 6}

        # 音訊檔案
        frame_file = ttk.LabelFrame(self.root, text=" 音訊檔案 ", padding=8)
        frame_file.grid(row=0, column=0, sticky="ew", **pad)

        self.file_var = tk.StringVar()
        ttk.Entry(frame_file, textvariable=self.file_var, width=56, state="readonly").pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(frame_file, text="選擇檔案", command=self._select_file).pack(side="left")

        # 切割設定
        frame_cut = ttk.LabelFrame(self.root, text=" 切割設定 ", padding=8)
        frame_cut.grid(row=1, column=0, sticky="ew", **pad)

        self.cut_mode = tk.StringVar(value="auto")
        ttk.Radiobutton(
            frame_cut, text="自動（每 20 分鐘切一段）",
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
        self.cut_text.insert("1.0", "00:20:00\n00:40:00")
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

        # 開始按鈕
        self.btn_start = ttk.Button(
            self.root, text="▶  開始轉錄", command=self._start, width=20
        )
        self.btn_start.grid(row=3, column=0, pady=10)

        # 進度區
        frame_progress = ttk.LabelFrame(self.root, text=" 處理進度 ", padding=8)
        frame_progress.grid(row=4, column=0, sticky="ew", **pad)

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
    def _toggle_cut_mode(self):
        if self.cut_mode.get() == "custom":
            self.frame_custom.grid()
        else:
            self.frame_custom.grid_remove()
        self.root.update_idletasks()

    def _toggle_api_show(self):
        self.api_entry.config(show="" if self.api_entry.cget("show") else "•")

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
        audio_path = self.file_var.get()
        api_key = self.api_var.get().strip()

        if not audio_path:
            messagebox.showerror("錯誤", "請先選擇音訊檔案")
            return
        if not api_key:
            messagebox.showerror("錯誤", "請輸入 Gemini API Key")
            return

        # 解析自訂切割點
        cut_points = None
        if self.cut_mode.get() == "custom":
            try:
                cut_points = parse_custom_cut_points(self.cut_text.get("1.0", "end"))
            except ValueError as e:
                messagebox.showerror("格式錯誤", str(e))
                return

        # 儲存 API Key
        if self.save_key_var.get():
            set_key(ENV_PATH, "GEMINI_API_KEY", api_key)

        client = genai.Client(api_key=api_key)

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
            target=self._worker, args=(audio_path, cut_points, client), daemon=True
        )
        t.start()

    def _worker(self, audio_path: str, cut_points: list[int] | None, client: genai.Client):
        """背景執行緒：切割 + 上傳 + 轉錄 + 合併"""
        temp_files: list[str] = []
        try:
            self._log(f"讀取音訊：{os.path.basename(audio_path)}")
            total_duration = get_audio_duration(audio_path)
            self._log(f"總時長：{seconds_to_hms(total_duration)}")

            # 建立分段清單
            if cut_points is None:
                # 自動模式：每 20 分鐘一刀
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

    def _done(self, output_path: str, success: bool):
        self.msg_queue.put(("done", (output_path, success)))

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
                    output_path, success = data
                    self.is_running = False
                    self.btn_start.config(state="normal")
                    if success:
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
