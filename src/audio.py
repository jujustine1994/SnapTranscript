"""音訊處理：ffprobe 取時長、ffmpeg 切割、yt-dlp 下載。"""

import os
import subprocess

import yt_dlp

from i18n import t


def get_audio_duration(audio_path: str) -> float:
    """用 ffprobe 取得音訊總時長（秒）。

    失敗時拋出訊息看得懂的例外。原本直接 `float(result.stdout)`，ffprobe 一失敗
    使用者看到的是 `could not convert string to float: b'xxx.mp3: No such file
    or directory'`——完全看不出要做什麼。而且原本把 stderr 併進 stdout
    （`stderr=subprocess.STDOUT`），錯誤訊息會混進要解析的數字裡。
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(t("err.audio.not_found", path=audio_path))

    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path,
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        raise RuntimeError(t("err.audio.no_ffprobe")) from None

    raw = result.stdout.strip()
    try:
        return float(raw)
    except ValueError:
        raise RuntimeError(
            t("err.audio.bad_duration", name=os.path.basename(audio_path))
        ) from None


def cut_audio_segment(audio_path: str, start_sec: int, duration_sec: int, output_path: str):
    """用 ffmpeg 切割指定時段，優先 copy codec，失敗再重新編碼。

    不拋例外：呼叫端（`job._process_one`）靠「輸出檔存不存在」判斷成敗，
    這樣單段切割失敗只會標記該段，不會中止整個任務。所以兩次都失敗時
    必須把殘檔刪掉——ffmpeg 失敗仍可能留下 0 byte 或半截的檔案，
    留著會讓存在性檢查誤判成功，接著把壞掉的音訊上傳給 Gemini。
    """
    base_cmd = ["ffmpeg", "-ss", str(start_sec), "-t", str(duration_sec), "-i", audio_path]

    # 嘗試 copy（速度快，不重新編碼）
    result = subprocess.run(
        base_cmd + ["-acodec", "copy", "-y", output_path],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        # 回退：重新編碼為 mp3
        result = subprocess.run(
            base_cmd + ["-acodec", "libmp3lame", "-y", output_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    if result.returncode != 0 and os.path.exists(output_path):
        try:
            os.remove(output_path)
        except OSError:
            pass


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
        raise FileNotFoundError(t("err.audio.download_missing", path=audio_path))

    return audio_path, title
