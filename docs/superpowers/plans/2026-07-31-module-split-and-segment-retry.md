# 模組拆分 + 段落級容錯與補跑 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 973 行的 `main.py` 拆成 8 個聚焦模組，並讓單段轉錄失敗不再毀掉整個任務——改為固定 20 秒退避重試、失敗即標記後續跑、結束後可用按鈕只補跑失敗段落。

**Architecture:** 先做零行為改變的純搬移（Task 1-5），把純函式與 UI 類別移出 `main.py`；再把轉錄流程從 tkinter 類別抽成不認識 UI、只吃 callback 的 `TranscriptionJob`（Task 6），此時補上測試建立行為基準；最後才在有測試保護的 `job.py` 裡改行為（Task 7-9）。

**Tech Stack:** Python 3.13、tkinter、unittest（**本專案沒有 pytest**）、google-genai、yt-dlp、ffmpeg/ffprobe（外部執行檔）

## Global Constraints

- **測試指令一律是** `./venv/Scripts/python.exe -m unittest discover -s tests -v`。不要用 pytest，專案沒裝。
- **不修改 `launcher.ps1`。** 它是 UTF-8 with BOM，用一般編輯器存檔會壞掉（見 `PITFALLS.md`）。所有新 `.py` 檔平鋪在專案根目錄，`launcher.ps1:237` 的 `python main.py` 保持有效。
- **不修改 `MODEL_NAME = "gemini-flash-latest"`**（使用者明確指定維持此設定，見 `PITFALLS.md`）。
- **所有新檔案存成 UTF-8 without BOM**（Python 檔的正常編碼）。只有 `.ps1` 需要 BOM。
- **落檔紀律**：只有三種情況寫進 `logs/app.log`——任務起始、錯誤行、任務結果。不得寫入逐字稿全文、API request/response payload、完整例外堆疊。錯誤行只記 `type(e).__name__` 與 HTTP status。
- **新測試不得依賴 ffmpeg、網路或 API Key。** 一律用注入的假函式。
- 註解與 docstring 用繁體中文，與現有程式碼一致。
- 每個 Task 結束都要 commit，commit message 用繁體中文，結尾加 `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`。

---

## File Structure

拆分後的檔案配置（全部平鋪在專案根目錄）：

| 檔案 | 責任 | 依賴 |
|---|---|---|
| `main.py` | 程式入口：banner + Tk root + `main()` | `ui` |
| `config.py` | 全域常數 | 無 |
| `logger.py` | `logs/app.log` 落檔 | 無 |
| `segments.py` | 時間字串解析 + 分段計算（純函式） | 無 |
| `audio.py` | ffprobe / ffmpeg / yt-dlp | 無 |
| `transcriber.py` | Gemini 呼叫 + prompt + 錯誤分類 | `config` |
| `job.py` | 轉錄流程編排（不認識 tkinter） | `config` `logger` `segments` `audio` `transcriber` |
| `ui.py` | `SnapTranscriptApp`（tkinter） | 全部 |

依賴方向單向由上往下，無循環 import。

測試檔：

| 檔案 | 涵蓋 |
|---|---|
| `tests/test_segments.py` | `build_segments`、`parse_range`（由 `test_main.py` 改名而來） |
| `tests/test_transcriber.py` | `classify_error`、`is_quota_error` |
| `tests/test_job.py` | `TranscriptionJob` 全流程 |

---

## Task 1: 抽出 config.py 與 logger.py

**Files:**
- Create: `config.py`
- Create: `logger.py`
- Modify: `main.py:20-68`（刪除搬走的區塊，改為 import）

**Interfaces:**
- Consumes: 無
- Produces: `config.SCRIPT_DIR` `config.ENV_PATH` `config.DEFAULT_CHUNK_SECONDS` `config.MODEL_NAME` `config.MAX_AUTO_RETRIES`；`logger.LOG_DIR` `logger.LOG_FILE` `logger.write_log(msg: str, level: str = "INFO") -> None` `logger.write_log_header(msg: str) -> None`

這是純搬移，行為零改變。唯一的更名：`_write_log` → `write_log`、`_write_log_header` → `write_log_header`（跨模組呼叫，不再私有）。`_find_project_root` 維持底線前綴（只有 `logger.py` 內部用）。

- [ ] **Step 1: 建立 `config.py`**

```python
"""全域常數設定。"""

import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(SCRIPT_DIR, ".env")
DEFAULT_CHUNK_SECONDS = 30 * 60  # 預設 30 分鐘
MODEL_NAME = "gemini-flash-latest"
MAX_AUTO_RETRIES = 5  # 「自動重試」勾選時，單段最多自動重試次數
```

- [ ] **Step 2: 建立 `logger.py`**

```python
"""執行紀錄：單一 logs/app.log 累積寫入。

落檔規範見 ARCHITECTURE.md「Log / 錯誤紀錄」章節：只有任務起始、錯誤行、
任務結果三種情況落檔，其餘進度訊息只推 UI。
"""

import os
import time


def _find_project_root() -> str:
    """往上找 launcher.ps1 所在目錄＝專案根目錄。

    不可寫死 os.path.join(SCRIPT_DIR, "..", "logs")：主程式在根目錄的專案會算到
    專案外層（Documents\\Code\\logs），污染其他專案。用這個函式，主程式在根目錄
    或 src/ 都對，日後把 .py 搬進 src/ 也不會壞。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    d = here
    while True:
        if os.path.exists(os.path.join(d, "launcher.ps1")):
            return d
        parent = os.path.dirname(d)
        if parent == d:      # 找到磁碟根目錄仍沒找到，退回自己所在目錄，至少不寫到專案外
            return here
        d = parent


LOG_DIR = os.path.join(_find_project_root(), "logs")
LOG_FILE = os.path.join(LOG_DIR, "app.log")


def write_log(msg: str, level: str = "INFO"):
    """寫一行到 logs/app.log。每次開檔→寫→關檔，不持有 handle（地雷十）"""
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] [{level:<5}] {msg}\n")
    except OSError:
        pass   # log 掛掉不能拖垮主程式；也涵蓋兩個實例同時跑撞在一起


def write_log_header(msg: str):
    """任務起始行，唯一有完整日期的行"""
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"=== {time.strftime('%Y-%m-%d %H:%M:%S')} {msg} ===\n")
    except OSError:
        pass
```

- [ ] **Step 3: 從 `main.py` 刪除搬走的區塊並改用 import**

刪除 `main.py` 第 20-68 行（`# ---- 常數 ----` 到 `write_log_header` 結束，含 `_find_project_root`、`LOG_DIR`、`LOG_FILE`）。

在 import 區塊（`from dotenv import load_dotenv, set_key` 之後）加入：

```python
import config
import logger
from config import (
    DEFAULT_CHUNK_SECONDS,
    ENV_PATH,
    MAX_AUTO_RETRIES,
    MODEL_NAME,
    SCRIPT_DIR,
)
from logger import write_log, write_log_header
```

`from config import ...` 與 `from logger import ...` 讓 `main.py` 內既有的裸名稱引用（`SCRIPT_DIR`、`MODEL_NAME`、`_write_log(...)` 等）不需大改。但 `_write_log` / `_write_log_header` 已更名，需把 `main.py` 內這兩處呼叫改名：

- `main.py` 原 870 行、873 行：`_write_log(...)` → `write_log(...)`
- `_init_log_file` 內：`_write_log_header(task_desc)` → `write_log_header(task_desc)`
- `_finalize_log_file` 內：`_write_log(...)` → `write_log(...)`

用這個指令確認沒有漏網之魚（應該無輸出）：

```bash
grep -n "_write_log" main.py
```

- [ ] **Step 4: 驗證 import 正常、測試通過**

```bash
./venv/Scripts/python.exe -c "import main; print('import ok')"
./venv/Scripts/python.exe -m unittest discover -s tests -v
```

Expected: 印出 `import ok`；9 個測試全過。

- [ ] **Step 5: 驗證 App 能啟動**

```bash
./venv/Scripts/python.exe -c "import ast,sys; ast.parse(open('main.py',encoding='utf-8').read()); print('syntax ok')"
```

Expected: `syntax ok`。

接著請使用者手動雙擊 `Run SnapTranscript.bat`，確認視窗正常開啟、UI 元件齊全後回報。**不要自己用 Bash 啟動 GUI**（會卡住背景程序）。

- [ ] **Step 6: Commit**

```bash
git add config.py logger.py main.py
git commit -m "refactor: 抽出 config.py 與 logger.py

純搬移，行為零改變。_write_log / _write_log_header 因跨模組呼叫
去掉底線前綴改為 write_log / write_log_header。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 2: 抽出 segments.py 並搬移測試

**Files:**
- Create: `segments.py`
- Create: `tests/test_segments.py`
- Delete: `tests/test_main.py`
- Modify: `main.py`（刪除搬走的函式，改為 import）

**Interfaces:**
- Consumes: 無
- Produces: `segments.hms_to_seconds(hms: str) -> int` `segments.seconds_to_hms(seconds: float) -> str` `segments.parse_custom_cut_points(text: str) -> list[int]` `segments.parse_range(start_text: str, end_text: str) -> tuple[int, int]` `segments.build_segments(cut_points: list[int], range_start: int, range_end: int) -> list[tuple[int, int]]`

- [ ] **Step 1: 建立 `segments.py`**

把 `main.py` 第 92-161 行的五個函式原封不動搬過來（`# ---- 時間工具 ----` 區塊）：

```python
"""時間字串解析與音訊分段計算（純函式，無外部相依）。"""

import re


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


def parse_range(start_text: str, end_text: str) -> tuple[int, int]:
    """
    解析擷取範圍的起始/結束時間（HH:MM:SS），回傳 (start_sec, end_sec)。
    格式錯誤或起始 >= 結束時拋出 ValueError。
    """
    pattern = re.compile(r"^\d{1,2}:\d{2}:\d{2}$")
    start_text = start_text.strip()
    end_text = end_text.strip()
    if not start_text or not end_text:
        raise ValueError("請輸入起始與結束時間")
    if not pattern.match(start_text):
        raise ValueError(f"格式錯誤：「{start_text}」，請使用 HH:MM:SS 格式（例如 00:10:00）")
    if not pattern.match(end_text):
        raise ValueError(f"格式錯誤：「{end_text}」，請使用 HH:MM:SS 格式（例如 00:45:00）")
    start_sec = hms_to_seconds(start_text)
    end_sec = hms_to_seconds(end_text)
    if start_sec >= end_sec:
        raise ValueError("起始時間必須早於結束時間")
    return start_sec, end_sec


def build_segments(cut_points: list[int], range_start: int, range_end: int) -> list[tuple[int, int]]:
    """從切割點建立 (start_sec, end_sec) 清單，限制在 [range_start, range_end] 範圍內"""
    boundaries = [range_start] + cut_points + [range_end]
    segments = []
    for i in range(len(boundaries) - 1):
        start = boundaries[i]
        end = min(boundaries[i + 1], range_end)
        if end > start:
            segments.append((start, end))
    return segments
```

- [ ] **Step 2: 建立 `tests/test_segments.py`**

內容是 `tests/test_main.py` 的九個測試，只把 `import main` 改成 `import segments`、`main.xxx` 改成 `segments.xxx`：

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import segments


class TestBuildSegments(unittest.TestCase):
    def test_no_cut_points_full_range(self):
        result = segments.build_segments([], 0, 100)
        self.assertEqual(result, [(0, 100)])

    def test_cut_points_within_full_range(self):
        result = segments.build_segments([30, 60], 0, 100)
        self.assertEqual(result, [(0, 30), (30, 60), (60, 100)])

    def test_range_offset(self):
        # 範圍 10:00~50:00（600~3000 秒），自動切點在 30:00（1800 秒）
        result = segments.build_segments([1800], 600, 3000)
        self.assertEqual(result, [(600, 1800), (1800, 3000)])

    def test_no_cut_points_with_range_offset(self):
        result = segments.build_segments([], 600, 1800)
        self.assertEqual(result, [(600, 1800)])


class TestParseRange(unittest.TestCase):
    def test_valid_range(self):
        self.assertEqual(segments.parse_range("00:10:00", "00:45:00"), (600, 2700))

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            segments.parse_range("", "00:45:00")

    def test_bad_format_raises(self):
        with self.assertRaises(ValueError):
            segments.parse_range("10:00", "00:45:00")

    def test_start_after_end_raises(self):
        with self.assertRaises(ValueError):
            segments.parse_range("00:45:00", "00:10:00")

    def test_start_equal_end_raises(self):
        with self.assertRaises(ValueError):
            segments.parse_range("00:10:00", "00:10:00")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: 刪除舊測試檔與其快取**

```bash
git rm tests/test_main.py
rm -rf tests/__pycache__
```

- [ ] **Step 4: 從 `main.py` 刪除搬走的函式並改用 import**

刪除 `main.py` 的 `# ---- 時間工具 ----` 區塊（原 92-161 行五個函式，含 `import re` 若已無其他用途）。

在 import 區塊加入：

```python
from segments import (
    build_segments,
    hms_to_seconds,
    parse_custom_cut_points,
    parse_range,
    seconds_to_hms,
)
```

確認 `main.py` 是否還有用到 `re`：

```bash
grep -n "re\." main.py
```

若無輸出，把 `import re` 從 `main.py` 刪掉。

- [ ] **Step 5: 驗證**

```bash
./venv/Scripts/python.exe -c "import main; print('import ok')"
./venv/Scripts/python.exe -m unittest discover -s tests -v
```

Expected: `import ok`；9 個測試全過（現在來自 `test_segments.py`）。

- [ ] **Step 6: Commit**

```bash
git add segments.py tests/test_segments.py main.py
git commit -m "refactor: 抽出 segments.py，測試改名為 test_segments.py

純搬移，行為零改變。時間解析與分段計算是純函式，無任何外部相依。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 3: 抽出 audio.py

**Files:**
- Create: `audio.py`
- Modify: `main.py`（刪除搬走的函式，改為 import）

**Interfaces:**
- Consumes: 無
- Produces: `audio.get_audio_duration(audio_path: str) -> float` `audio.cut_audio_segment(audio_path: str, start_sec: int, duration_sec: int, output_path: str) -> None` `audio.download_youtube_audio(url: str, save_path: str, progress_callback=None) -> tuple[str, str]`

- [ ] **Step 1: 建立 `audio.py`**

把 `main.py` 原 165-229 行三個函式原封不動搬過來：

```python
"""音訊處理：ffprobe 取時長、ffmpeg 切割、yt-dlp 下載。"""

import os
import subprocess

import yt_dlp


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
```

- [ ] **Step 2: 從 `main.py` 刪除搬走的函式並改用 import**

刪除 `# ---- 音訊處理 ----` 與 `# ---- YouTube 下載 ----` 兩個區塊（原 164-229 行）。

import 區塊加入：

```python
from audio import cut_audio_segment, download_youtube_audio, get_audio_duration
```

刪除 `main.py` 頂端的 `import yt_dlp`。確認 `subprocess` 是否還有用途：

```bash
grep -n "subprocess" main.py
```

若還有（`_open_output_folder` 可能用到），保留 `import subprocess`；若無輸出則刪除。

- [ ] **Step 3: 驗證**

```bash
./venv/Scripts/python.exe -c "import main; print('import ok')"
./venv/Scripts/python.exe -m unittest discover -s tests -v
```

Expected: `import ok`；9 個測試全過。

- [ ] **Step 4: Commit**

```bash
git add audio.py main.py
git commit -m "refactor: 抽出 audio.py

純搬移，行為零改變。ffprobe / ffmpeg / yt-dlp 三個外部工具的包裝集中一處。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 4: 抽出 transcriber.py 並新增錯誤分類函式

**Files:**
- Create: `transcriber.py`
- Create: `tests/test_transcriber.py`
- Modify: `main.py`（刪除 `transcribe_segment`，改為 import）

**Interfaces:**
- Consumes: `config.MODEL_NAME`
- Produces: `transcriber.transcribe_segment(audio_path: str, client) -> str` `transcriber.classify_error(e: Exception) -> tuple[str, str] | None` `transcriber.is_quota_error(e: Exception) -> bool`

`classify_error` 與 `is_quota_error` 是把目前散在 `main.py` 的字串比對抽成純函式：
- `classify_error` 對應 `main.py:799-808` 的 `"503" in err_str` 等判斷
- `is_quota_error` 對應 `main.py:865` 的 429 / quota / exhausted 判斷

這兩個函式現在還沒有呼叫端（Task 6 才接上），但先寫好並測試。

- [ ] **Step 1: 先寫失敗的測試 `tests/test_transcriber.py`**

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import transcriber


class TestClassifyError(unittest.TestCase):
    def test_503_returns_server_reason(self):
        result = transcriber.classify_error(Exception("500 error: 503 UNAVAILABLE"))
        self.assertEqual(result, ("Gemini 伺服器回傳 503", "503 UNAVAILABLE"))

    def test_unavailable_without_503_still_matches(self):
        result = transcriber.classify_error(Exception("ServerError: UNAVAILABLE"))
        self.assertEqual(result, ("Gemini 伺服器回傳 503", "503 UNAVAILABLE"))

    def test_blank_result_returns_blank_reason(self):
        result = transcriber.classify_error(
            Exception("Gemini 回傳空白結果（finish_reason: MALFORMED_RESPONSE）")
        )
        self.assertEqual(result, ("Gemini 回傳空白結果", "空白結果"))

    def test_unknown_error_returns_none(self):
        self.assertIsNone(transcriber.classify_error(Exception("檔案讀取失敗")))

    def test_quota_error_is_not_retryable(self):
        # 429 屬於配額問題，不該被歸類為可重試
        self.assertIsNone(transcriber.classify_error(Exception("429 RESOURCE_EXHAUSTED")))


class TestIsQuotaError(unittest.TestCase):
    def test_429_is_quota(self):
        self.assertTrue(transcriber.is_quota_error(Exception("429 Too Many Requests")))

    def test_quota_keyword_is_quota(self):
        self.assertTrue(transcriber.is_quota_error(Exception("Quota exceeded for model")))

    def test_exhausted_keyword_is_quota(self):
        self.assertTrue(transcriber.is_quota_error(Exception("RESOURCE_EXHAUSTED")))

    def test_503_is_not_quota(self):
        self.assertFalse(transcriber.is_quota_error(Exception("503 UNAVAILABLE")))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 執行測試確認失敗**

```bash
./venv/Scripts/python.exe -m unittest discover -s tests -v
```

Expected: FAIL，錯誤訊息為 `ModuleNotFoundError: No module named 'transcriber'`。

- [ ] **Step 3: 建立 `transcriber.py`**

`transcribe_segment` 是原封不動搬移（`main.py` 原 232-267 行），只把 `MODEL_NAME` 改成 `config.MODEL_NAME`。兩個分類函式是新增的。

```python
"""Gemini 轉錄呼叫與錯誤分類。"""

import time

from google import genai

import config

PROMPT = """請仔細聆聽這段音訊，將所有說話內容以原始語言逐字轉錄。

輸出規則：
1. 純文字輸出，不需要時間戳、編號或任何 JSON / Markdown 格式
2. 依照說話者使用的語言直接轉錄原文，不需翻譯
3. 同一說話者的連續發言合併為一個段落，說話者切換時才換段並空一行
4. 每段開頭標註說話者：優先使用音訊中可辨識的真實姓名或職稱（如「財務長：」「主持人：」），無法辨識則使用「說話者 A：」「說話者 B：」等泛用標籤
5. 背景雜音、靜默段、非語言音（笑聲、清喉嚨等）不需輸出
6. 盡力辨識模糊語音，結合前後文補全語意，忠實呈現內容，不要摘要或省略"""


def transcribe_segment(audio_path: str, client: genai.Client) -> str:
    """上傳音訊至 Gemini，取得純文字逐字稿"""
    audio_file = client.files.upload(file=audio_path)
    while audio_file.state.name == "PROCESSING":
        time.sleep(2)
        audio_file = client.files.get(name=audio_file.name)

    if audio_file.state.name != "ACTIVE":
        raise Exception(f"Gemini 檔案處理失敗（狀態：{audio_file.state.name}），請重試")

    try:
        response = client.models.generate_content(
            model=config.MODEL_NAME,
            contents=[PROMPT, audio_file],
        )
    except Exception:
        client.files.delete(name=audio_file.name)
        raise
    client.files.delete(name=audio_file.name)
    if response.text is None:
        finish_reason = None
        if response.candidates:
            finish_reason = response.candidates[0].finish_reason
        raise Exception(
            f"Gemini 回傳空白結果（finish_reason: {finish_reason}），"
            "可能因內容審查攔截或無法辨識音訊，請重試"
        )
    return response.text.strip()


def is_quota_error(e: Exception) -> bool:
    """判斷是否為 API 配額用盡（429）。這類錯誤重試無用，必須中止。"""
    err = str(e).lower()
    return "429" in err or "quota" in err or "exhausted" in err


def classify_error(e: Exception) -> tuple[str, str] | None:
    """判斷錯誤是否值得重試。

    回傳 (可讀原因, log 用 status)；不值得重試的錯誤回傳 None。
    只依關鍵字判斷並取 status，絕不把例外全文帶出——例外訊息可能挾帶
    URL 或 response body，那些不該落檔（見 ARCHITECTURE.md 落檔紀律）。
    """
    if is_quota_error(e):
        return None
    err_str = str(e)
    if "503" in err_str or "UNAVAILABLE" in err_str:
        return "Gemini 伺服器回傳 503", "503 UNAVAILABLE"
    if "Gemini 回傳空白結果" in err_str:
        return "Gemini 回傳空白結果", "空白結果"
    return None
```

- [ ] **Step 4: 執行測試確認通過**

```bash
./venv/Scripts/python.exe -m unittest discover -s tests -v
```

Expected: 18 個測試全過（9 個 segments + 9 個 transcriber）。

- [ ] **Step 5: 從 `main.py` 刪除 `transcribe_segment` 並改用 import**

刪除 `# ---- Gemini 逐字稿 ----` 區塊（原 232-267 行）。

import 區塊加入：

```python
from transcriber import transcribe_segment
```

確認 `main.py` 是否還用到 `time` 與 `genai`：

```bash
grep -n "time\.\|genai\." main.py
```

`time.time()` 在 `_worker` 與 `_finalize_log_file` 有用，`genai.Client` 在 `_start` 與 `_worker` 型別註記有用，兩個 import 都保留。

- [ ] **Step 6: 驗證**

```bash
./venv/Scripts/python.exe -c "import main; print('import ok')"
./venv/Scripts/python.exe -m unittest discover -s tests -v
```

Expected: `import ok`；18 個測試全過。

- [ ] **Step 7: Commit**

```bash
git add transcriber.py tests/test_transcriber.py main.py
git commit -m "refactor: 抽出 transcriber.py，新增 classify_error / is_quota_error

transcribe_segment 為純搬移。錯誤分類原本是 _worker 裡的字串比對，
抽成純函式後可獨立測試，Task 6 接上呼叫端。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 5: 搬移 SnapTranscriptApp 至 ui.py

**Files:**
- Create: `ui.py`
- Modify: `main.py`（只剩 banner + 入口）

**Interfaces:**
- Consumes: `config` `logger` `segments` `audio` `transcriber` 的全部公開名稱
- Produces: `ui.SnapTranscriptApp(root: tk.Tk)`

純搬移，行為零改變。

- [ ] **Step 1: 建立 `ui.py`**

把 `main.py` 的 `class SnapTranscriptApp`（原 271-961 行，含所有方法）整段搬到 `ui.py`。檔案開頭放 import：

```python
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

from audio import cut_audio_segment, download_youtube_audio, get_audio_duration
from config import (
    DEFAULT_CHUNK_SECONDS,
    ENV_PATH,
    MAX_AUTO_RETRIES,
    MODEL_NAME,
    SCRIPT_DIR,
)
from logger import write_log, write_log_header
from segments import (
    build_segments,
    parse_custom_cut_points,
    parse_range,
    seconds_to_hms,
)
from transcriber import transcribe_segment


class SnapTranscriptApp:
    ...  # 從 main.py 整段搬過來，內容一字不改
```

搬完後執行 `grep -n "hms_to_seconds" ui.py`，若無輸出就從 import 清單移除 `hms_to_seconds`（它只被 `segments.py` 內部使用）。

注意 `ui.py` **不需要** `import subprocess`——`main.py` 原本的 `subprocess` 只被 Task 3 搬走的音訊函式使用，`_open_output_folder` 用的是 `os.startfile`。

- [ ] **Step 2: 改寫 `main.py` 為純入口**

`main.py` 完整內容（取代原檔案）：

```python
"""
SnapTranscript — 會議音訊逐字稿工具
將音訊檔案分段切割，透過 Gemini AI 生成逐字稿，合併輸出為單一 TXT 檔案。
"""

import tkinter as tk

from ui import SnapTranscriptApp


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


def main():
    show_cth_banner()
    root = tk.Tk()
    SnapTranscriptApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 驗證**

```bash
./venv/Scripts/python.exe -c "import main; print('import ok')"
./venv/Scripts/python.exe -m unittest discover -s tests -v
wc -l main.py ui.py
```

Expected: `import ok`；18 個測試全過；`main.py` 約 40 行、`ui.py` 約 700 行。

- [ ] **Step 4: 請使用者手動驗證 App**

請使用者雙擊 `Run SnapTranscript.bat`，確認：視窗開啟、四個區塊（音訊來源／擷取範圍／切割設定／API Key）都在、「自動重試」預設已勾選、切換「YouTube 下載」時 UI 正常變化。**不要自己用 Bash 啟動 GUI。**

- [ ] **Step 5: Commit**

```bash
git add ui.py main.py
git commit -m "refactor: SnapTranscriptApp 搬至 ui.py，main.py 只剩入口

純搬移，行為零改變。main.py 從 973 行縮到約 40 行。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 6: 抽出 job.py（維持現有行為）並補測試

**Files:**
- Create: `job.py`
- Create: `tests/test_job.py`
- Modify: `ui.py`（`_worker` 改為建立 `TranscriptionJob` 並呼叫 `run()`）

**Interfaces:**
- Consumes: `config.SCRIPT_DIR` `config.MAX_AUTO_RETRIES` `logger.write_log` `segments.seconds_to_hms` `audio.cut_audio_segment` `transcriber.transcribe_segment` `transcriber.classify_error` `transcriber.is_quota_error`
- Produces:
  - `job.SegmentResult(index: int, start_sec: int, end_sec: int, text: str | None = None, error: str | None = None)`
  - `job.JobCallbacks(log: Callable[[str], None], progress: Callable[[int, int, str], None], ask: Callable[[str], bool])`
  - `job.QuotaExhausted`（Exception 子類）
  - `job.TranscriptionJob(audio_path, segment_list, client, auto_retry, callbacks, transcribe_fn=None, cut_fn=None, sleep_fn=None)`，方法 `run() -> str`、屬性 `results: list[SegmentResult]` `total: int` `done_count: int` `failed_count: int` `output_path: str`

**本 Task 刻意維持現有行為**：單段重試耗盡仍拋例外中止整個任務。目的是先證明「搬移沒有弄壞東西」，Task 7-9 才改語意。`retry_failed()` 到 Task 9 才加。

- [ ] **Step 1: 先寫失敗的測試 `tests/test_job.py`**

```python
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import job


def make_callbacks(ask_returns=True):
    """回傳 (callbacks, 記錄容器)。記錄容器可用來檢查 UI 收到什麼訊息。"""
    recorded = {"logs": [], "progress": [], "asked": []}

    def _log(msg):
        recorded["logs"].append(msg)

    def _progress(current, total, label):
        recorded["progress"].append((current, total, label))

    def _ask(question):
        recorded["asked"].append(question)
        return ask_returns

    return job.JobCallbacks(log=_log, progress=_progress, ask=_ask), recorded


class FakeSleep:
    """記錄每次 sleep 的秒數，實際不等待。"""

    def __init__(self):
        self.calls = []

    def __call__(self, seconds):
        self.calls.append(seconds)

    @property
    def total(self):
        return sum(self.calls)


def fake_cut(audio_path, start_sec, duration_sec, output_path):
    """不呼叫 ffmpeg，直接寫一個假的暫存檔讓存在性檢查通過。"""
    with open(output_path, "wb") as f:
        f.write(b"fake audio")


class JobTestBase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.audio_path = os.path.join(self.tmpdir.name, "meeting.mp3")
        with open(self.audio_path, "wb") as f:
            f.write(b"fake source audio")
        self.addCleanup(self.tmpdir.cleanup)

    def read_output(self, path):
        with open(path, encoding="utf-8") as f:
            return f.read()

    def make_job(self, transcribe_fn, segment_list=None, auto_retry=True,
                 ask_returns=True, sleep_fn=None):
        callbacks, recorded = make_callbacks(ask_returns=ask_returns)
        self.recorded = recorded
        self.sleeper = sleep_fn or FakeSleep()
        return job.TranscriptionJob(
            audio_path=self.audio_path,
            segment_list=segment_list or [(0, 1800), (1800, 3600)],
            client=None,
            auto_retry=auto_retry,
            callbacks=callbacks,
            transcribe_fn=transcribe_fn,
            cut_fn=fake_cut,
            sleep_fn=self.sleeper,
        )


class TestHappyPath(JobTestBase):
    def test_all_segments_succeed(self):
        j = self.make_job(lambda path, client: "逐字稿內容")
        output_path = j.run()

        self.assertEqual(j.failed_count, 0)
        self.assertEqual(j.done_count, 2)
        text = self.read_output(output_path)
        self.assertIn("=== 第 1 段（00:00:00 - 00:30:00）===", text)
        self.assertIn("=== 第 2 段（00:30:00 - 01:00:00）===", text)
        self.assertEqual(text.count("逐字稿內容"), 2)

    def test_output_path_derived_from_audio_path(self):
        j = self.make_job(lambda path, client: "內容")
        output_path = j.run()
        self.assertEqual(
            output_path, os.path.join(self.tmpdir.name, "meeting_transcript.txt")
        )

    def test_temp_files_removed_after_success(self):
        j = self.make_job(lambda path, client: "內容")
        j.run()
        leftovers = [
            f for f in os.listdir(job.config.SCRIPT_DIR) if f.startswith("_temp_seg_")
        ]
        self.assertEqual(leftovers, [])


class TestRetry(JobTestBase):
    def test_recovers_after_one_503(self):
        state = {"calls": 0}

        def flaky(path, client):
            state["calls"] += 1
            if state["calls"] == 1:
                raise Exception("503 UNAVAILABLE")
            return "成功內容"

        j = self.make_job(flaky)
        output_path = j.run()

        self.assertEqual(j.failed_count, 0)
        self.assertIn("成功內容", self.read_output(output_path))

    def test_unknown_error_propagates(self):
        def boom(path, client):
            raise Exception("磁碟讀取失敗")

        j = self.make_job(boom)
        with self.assertRaises(Exception) as ctx:
            j.run()
        self.assertIn("磁碟讀取失敗", str(ctx.exception))

    def test_quota_error_raises_quota_exhausted(self):
        def quota(path, client):
            raise Exception("429 RESOURCE_EXHAUSTED")

        j = self.make_job(quota)
        with self.assertRaises(job.QuotaExhausted):
            j.run()

    def test_exhausted_retries_raise(self):
        """Task 6 的現有行為：重試耗盡拋例外中止。Task 8 會改成標記後續跑。"""
        def always_503(path, client):
            raise Exception("503 UNAVAILABLE")

        j = self.make_job(always_503)
        with self.assertRaises(Exception):
            j.run()


class TestManualRetry(JobTestBase):
    def test_ask_callback_used_when_auto_retry_off(self):
        state = {"calls": 0}

        def flaky(path, client):
            state["calls"] += 1
            if state["calls"] == 1:
                raise Exception("503 UNAVAILABLE")
            return "成功內容"

        j = self.make_job(flaky, auto_retry=False)
        j.run()
        self.assertEqual(len(self.recorded["asked"]), 1)
        self.assertIn("是否重試", self.recorded["asked"][0])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 執行測試確認失敗**

```bash
./venv/Scripts/python.exe -m unittest discover -s tests -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'job'`。

- [ ] **Step 3: 建立 `job.py`**

```python
"""轉錄流程編排。

刻意不 import tkinter：這個模組只透過 JobCallbacks 與 UI 溝通，因此可以在
沒有 GUI、沒有 ffmpeg、沒有網路的環境下被測試。
"""

import os
import time
from dataclasses import dataclass
from typing import Callable

import audio
import config
import logger
import segments as segmod
import transcriber


class QuotaExhausted(Exception):
    """API 配額用盡（429）。重試無用，必須中止整個任務。"""


@dataclass
class SegmentResult:
    """單一段落的狀態。text 為 None 代表這段還沒成功。"""

    index: int          # 從 1 開始，對應逐字稿的「第 N 段」
    start_sec: int
    end_sec: int
    text: str | None = None    # 成功的逐字稿
    error: str | None = None   # 失敗原因（可讀），成功時為 None


@dataclass
class JobCallbacks:
    """UI 溝通介面。job.py 只認識這三個函式，不認識 tkinter。"""

    log: Callable[[str], None]                 # 推 UI 記錄框
    progress: Callable[[int, int, str], None]  # (目前, 總數, 標籤)
    ask: Callable[[str], bool]                 # 未勾自動重試時跳 dialog


class TranscriptionJob:
    """把給定的段落逐一轉錄並寫出逐字稿檔案。

    末三個 *_fn 參數是測試注入點：測試傳入可控的假函式，就不需要
    ffmpeg、網路或 API Key。
    """

    def __init__(self, audio_path, segment_list, client, auto_retry, callbacks,
                 transcribe_fn=None, cut_fn=None, sleep_fn=None):
        self.audio_path = audio_path
        self.client = client
        self.auto_retry = auto_retry
        self.cb = callbacks
        self._transcribe = transcribe_fn or transcriber.transcribe_segment
        self._cut = cut_fn or audio.cut_audio_segment
        self._sleep = sleep_fn or time.sleep

        self.results = [
            SegmentResult(index=i + 1, start_sec=s, end_sec=e)
            for i, (s, e) in enumerate(segment_list)
        ]
        self.output_path = os.path.splitext(audio_path)[0] + "_transcript.txt"
        self._ext = os.path.splitext(audio_path)[1] or ".mp3"

    # ---- 狀態查詢 ----
    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def done_count(self) -> int:
        return sum(1 for r in self.results if r.text is not None)

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if r.text is None)

    # ---- 主流程 ----
    def run(self) -> str:
        """跑全部段落，回傳輸出檔路徑。"""
        return self._process(list(self.results))

    def _process(self, targets: list[SegmentResult]) -> str:
        for r in targets:
            self._process_one(r)
            self.cb.progress(
                self.done_count, self.total,
                f"{self.done_count} / {self.total} 段完成",
            )
        return self._write_output()

    def _process_one(self, r: SegmentResult):
        start_hms = segmod.seconds_to_hms(r.start_sec)
        end_hms = segmod.seconds_to_hms(r.end_sec)
        self.cb.log(f"\n[{r.index}/{self.total}] 切割 {start_hms} → {end_hms}...")

        temp_path = os.path.join(
            config.SCRIPT_DIR, f"_temp_seg_{r.index - 1}{self._ext}"
        )
        try:
            self._cut(self.audio_path, r.start_sec, r.end_sec - r.start_sec, temp_path)
            if not os.path.exists(temp_path):
                raise Exception(f"第 {r.index} 段切割失敗，請確認 ffmpeg 是否正常運作")

            self.cb.log(f"[{r.index}/{self.total}] 上傳至 Gemini，等待轉錄...")
            r.text = self._transcribe_with_retry(r, temp_path)
            r.error = None
            self.cb.log(f"[{r.index}/{self.total}] 完成")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def _transcribe_with_retry(self, r: SegmentResult, temp_path: str) -> str:
        retry_count = 0
        while True:
            try:
                return self._transcribe(temp_path, self.client)
            except Exception as e:
                if transcriber.is_quota_error(e):
                    logger.write_log(
                        f"轉錄中止 -> {type(e).__name__} | HTTP 429 配額用盡", "ERROR"
                    )
                    raise QuotaExhausted(
                        "API 免費用量已達上限，請等明天配額重置後再試"
                    ) from e

                classified = transcriber.classify_error(e)
                if classified is None:
                    raise
                reason, status = classified

                # 錯誤行只記例外類型 + status + 重試次數（見 ARCHITECTURE.md 落檔紀律）
                logger.write_log(
                    f"第{r.index}段 上傳Gemini -> {type(e).__name__} | "
                    f"{status} | 重試 {retry_count}/{config.MAX_AUTO_RETRIES}",
                    "ERROR",
                )
                self.cb.log(f"[錯誤] {reason}")

                if self.auto_retry:
                    retry_count += 1
                    if retry_count > config.MAX_AUTO_RETRIES:
                        raise Exception(
                            f"{reason}，已自動重試 {config.MAX_AUTO_RETRIES} 次仍失敗"
                        ) from e
                    self.cb.log(
                        f"[{r.index}/{self.total}] 自動重試中... "
                        f"({retry_count}/{config.MAX_AUTO_RETRIES})"
                    )
                else:
                    if not self.cb.ask(f"{reason}，是否重試？"):
                        raise Exception("已取消重試") from e
                    self.cb.log(f"[{r.index}/{self.total}] 重試中...")

    # ---- 輸出 ----
    def _write_output(self) -> str:
        self.cb.log("\n合併逐字稿...")
        lines = []
        for r in self.results:
            if r.text is None:
                continue
            start_hms = segmod.seconds_to_hms(r.start_sec)
            end_hms = segmod.seconds_to_hms(r.end_sec)
            lines.append(f"=== 第 {r.index} 段（{start_hms} - {end_hms}）===")
            lines.append("")
            lines.append(r.text)
            lines.append("")

        merged = "\n".join(lines).strip()
        with open(self.output_path, "w", encoding="utf-8") as f:
            f.write(merged)
        return self.output_path
```

- [ ] **Step 4: 執行測試確認通過**

```bash
./venv/Scripts/python.exe -m unittest discover -s tests -v
```

Expected: 26 個測試全過（9 segments + 9 transcriber + 8 job）。

- [ ] **Step 5: 改寫 `ui.py` 的 `_worker` 使用 `TranscriptionJob`**

`_worker` 中從「任務起始行」之後到「合併逐字稿」寫檔為止的整段（原 `main.py:761-860` 對應的區塊）替換為：

```python
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
            self._finalize_log_file(success=True)
            self._done(output_path, success=True)
```

配套修改：

1. 區域變數 `segments` 改名為 `segment_list`（避免與 `segments` 模組同名遮蔽）。`_worker` 內建立分段清單那幾行一併改：
   ```python
   segment_list = build_segments(auto_points, range_start, range_end)
   ...
   segment_list = build_segments(valid_points, range_start, range_end)
   ```
2. `_log` 簽章簡化為 `def _log(self, msg: str):`，移除 `level` 與 `to_file` 參數（落檔改由 `job.py` / `_finalize_log_file` 直接呼叫 `write_log`）。`ui.py` 內所有 `self._log(..., to_file=False)` 改為 `self._log(...)`。用這個確認清乾淨：
   ```bash
   grep -n "to_file" ui.py
   ```
   應無輸出。
3. `_init_log_file` 方法刪除（已直接呼叫 `write_log_header`）。
4. `__init__` 新增 `self._job = None`。
5. 頂端 import 加入 `import job`，並移除已不使用的名稱。用這個確認哪些變成孤兒後再刪：
   ```bash
   grep -n "transcribe_segment\|cut_audio_segment\|MAX_AUTO_RETRIES\|SCRIPT_DIR" ui.py
   ```
   預期這四個都只剩 import 那行（轉錄與暫存檔邏輯都搬進 `job.py` 了），確認後從 import 清單移除 `from transcriber import transcribe_segment`、`cut_audio_segment`、`MAX_AUTO_RETRIES`、`SCRIPT_DIR`。`ENV_PATH`、`MODEL_NAME`、`DEFAULT_CHUNK_SECONDS`、`get_audio_duration`、`download_youtube_audio` 仍在使用，保留。
6. 外層 `except` 的 429 判斷改用 `job.QuotaExhausted`：
   ```python
        except job.QuotaExhausted as e:
            self._log(f"\n[ERROR] {e}")
            self._finalize_log_file(success=False)
            self._done("", success=False)
        except Exception as e:
            self._log(f"\n[ERROR] {e}")
            write_log(f"轉錄中止 -> {type(e).__name__}", "ERROR")
            self._finalize_log_file(success=False)
            self._done("", success=False)
   ```
   （429 的落檔已由 `job.py` 在拋 `QuotaExhausted` 前寫過，此處不重複寫。）
7. `temp_files` 相關的區域變數與 `finally` 清理區塊刪除（暫存檔生命週期已由 `job.py` 的 `_process_one` 內 `finally` 負責）。`__init__` 的 `self.temp_files` 若無其他用途一併刪除。

- [ ] **Step 6: 驗證**

```bash
./venv/Scripts/python.exe -c "import main; print('import ok')"
./venv/Scripts/python.exe -m unittest discover -s tests -v
grep -n "to_file" ui.py
wc -l ui.py job.py
```

Expected: `import ok`；26 個測試全過；`grep` 無輸出；`ui.py` 約 560 行、`job.py` 約 190 行。

- [ ] **Step 7: 請使用者做一次真實轉錄驗證**

請使用者用一個**短音訊**（3-5 分鐘即可）跑一次完整轉錄，確認逐字稿正常產出、進度條正常、`logs/app.log` 有正確的起始行與結果行。這是整個重構最關鍵的驗證點——`job.py` 是第一個改動執行路徑的 Task。

- [ ] **Step 8: Commit**

```bash
git add job.py tests/test_job.py ui.py
git commit -m "refactor: 轉錄流程抽至 job.py，補上 8 個 pipeline 測試

TranscriptionJob 不 import tkinter，透過 JobCallbacks 與 UI 溝通，
因此可在無 GUI / 無 ffmpeg / 無網路的環境下測試。本次刻意維持現有
行為（單段重試耗盡仍中止），先建立測試基準，行為變更留給後續 Task。

_log 移除 to_file 參數：落檔與推 UI 在型別上分開，不再靠預設值防呆。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 7: 重試改為固定 20 秒退避

**Files:**
- Modify: `config.py`（新增 `RETRY_WAIT_SECONDS`）
- Modify: `job.py`（`_transcribe_with_retry` 加入等待、新增 `_wait_before_retry`）
- Modify: `tests/test_job.py`（新增退避測試）

**Interfaces:**
- Consumes: `config.RETRY_WAIT_SECONDS`
- Produces: 無新公開介面（`_wait_before_retry` 為內部方法）

問題背景：目前重試迴圈失敗後立刻重打。503 UNAVAILABLE 的語意是伺服器滿載，0 秒後重打仍然滿載，5 次重試在短時間內全部燒完。

等待用 1 秒一輪的迴圈實作而非單次 `sleep(20)`，讓進度標籤能顯示倒數（UI 不會看起來像凍結），同時為未來的「取消」功能留接點。

- [ ] **Step 1: 先寫失敗的測試**

在 `tests/test_job.py` 的 `TestRetry` 類別中加入：

```python
    def test_waits_20_seconds_before_retry(self):
        state = {"calls": 0}

        def flaky(path, client):
            state["calls"] += 1
            if state["calls"] == 1:
                raise Exception("503 UNAVAILABLE")
            return "成功內容"

        j = self.make_job(flaky)
        j.run()

        # 退避以 1 秒一輪的倒數迴圈實作，累計等待秒數應為 20
        self.assertEqual(self.sleeper.total, 20)
        self.assertTrue(all(s == 1 for s in self.sleeper.calls))

    def test_countdown_shown_in_progress_label(self):
        state = {"calls": 0}

        def flaky(path, client):
            state["calls"] += 1
            if state["calls"] == 1:
                raise Exception("503 UNAVAILABLE")
            return "成功內容"

        j = self.make_job(flaky)
        j.run()

        labels = [label for _, _, label in self.recorded["progress"]]
        self.assertIn("第 1 段重試中... 20 秒 (1/5)", labels)
        self.assertIn("第 1 段重試中... 1 秒 (1/5)", labels)

    def test_no_wait_when_manual_retry(self):
        """未勾自動重試時走 dialog，不套用退避（使用者按確認的時間就是等待）"""
        state = {"calls": 0}

        def flaky(path, client):
            state["calls"] += 1
            if state["calls"] == 1:
                raise Exception("503 UNAVAILABLE")
            return "成功內容"

        j = self.make_job(flaky, auto_retry=False)
        j.run()
        self.assertEqual(self.sleeper.total, 0)
```

同時修改既有的 `test_exhausted_retries_raise`，加上等待總量斷言：

```python
    def test_exhausted_retries_raise(self):
        """Task 6 的現有行為：重試耗盡拋例外中止。Task 8 會改成標記後續跑。"""
        def always_503(path, client):
            raise Exception("503 UNAVAILABLE")

        j = self.make_job(always_503)
        with self.assertRaises(Exception):
            j.run()
        # 5 次重試 × 每次 20 秒
        self.assertEqual(self.sleeper.total, 100)
```

- [ ] **Step 2: 執行測試確認失敗**

```bash
./venv/Scripts/python.exe -m unittest discover -s tests -v
```

Expected: FAIL，`test_waits_20_seconds_before_retry` 報 `0 != 20`。

- [ ] **Step 3: 在 `config.py` 新增常數**

在 `MAX_AUTO_RETRIES` 那行下方加入：

```python
RETRY_WAIT_SECONDS = 20  # 自動重試前的固定等待秒數（503 多半 20 秒內恢復）
```

- [ ] **Step 4: 在 `job.py` 加入等待邏輯**

在 `_transcribe_with_retry` 的自動重試分支中，把原本的：

```python
                    self.cb.log(
                        f"[{r.index}/{self.total}] 自動重試中... "
                        f"({retry_count}/{config.MAX_AUTO_RETRIES})"
                    )
```

改為：

```python
                    self.cb.log(
                        f"[{r.index}/{self.total}] 自動重試中... "
                        f"({retry_count}/{config.MAX_AUTO_RETRIES})"
                    )
                    self._wait_before_retry(r, retry_count)
```

並在 `_transcribe_with_retry` 之後新增方法：

```python
    def _wait_before_retry(self, r: SegmentResult, retry_count: int):
        """重試前固定等待。

        503 的語意是伺服器滿載，0 秒後重打仍然滿載——不等待的話 5 次重試
        會在數秒內全部燒完。用 1 秒一輪的倒數而非單次 sleep，是為了讓
        進度標籤能更新，UI 才不會看起來像凍結。
        """
        for remaining in range(config.RETRY_WAIT_SECONDS, 0, -1):
            self.cb.progress(
                self.done_count, self.total,
                f"第 {r.index} 段重試中... {remaining} 秒 "
                f"({retry_count}/{config.MAX_AUTO_RETRIES})",
            )
            self._sleep(1)
        self.cb.progress(
            self.done_count, self.total,
            f"{self.done_count} / {self.total} 段完成",
        )
```

- [ ] **Step 5: 執行測試確認通過**

```bash
./venv/Scripts/python.exe -m unittest discover -s tests -v
```

Expected: 29 個測試全過。

- [ ] **Step 6: Commit**

```bash
git add config.py job.py tests/test_job.py
git commit -m "fix: 自動重試改為固定 20 秒退避

原本失敗後立刻重打，但 503 代表伺服器滿載，0 秒後重打仍然滿載，
5 次重試在數秒內全部燒完，等於沒有重試。改為每次等待 20 秒。

等待用 1 秒一輪的倒數迴圈實作，進度標籤顯示剩餘秒數，UI 不會看起來
像凍結，也為未來的取消功能留下接點。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 8: 段落級容錯——失敗即標記，繼續下一段

**Files:**
- Modify: `job.py`（`_transcribe_with_retry` 改回傳 `str | None`、`_write_output` 加佔位符）
- Modify: `tests/test_job.py`（改寫既有的中止測試，新增容錯測試）

**Interfaces:**
- Consumes: 無新增
- Produces: `_transcribe_with_retry` 回傳型別由 `str` 改為 `str | None`（`None` 代表該段失敗，原因已寫入 `r.error`）

行為變更：
- 自動重試耗盡 → 不再拋例外，改為設定 `r.error` 並回傳 `None`，繼續下一段
- 未勾自動重試且使用者按「否」→ 同上（原本是中止整個任務）
- 429 配額用盡 → 維持中止（繼續跑只會持續撞牆），但已完成段落已寫檔
- 輸出檔一律產生，失敗段落寫佔位符

- [ ] **Step 1: 改寫既有測試，新增容錯測試**

把 `tests/test_job.py` 的 `test_exhausted_retries_raise` 整個替換為以下內容（連同新測試一起加進 `TestRetry` 類別）：

```python
    def test_exhausted_retries_marks_failure_and_continues(self):
        def always_503(path, client):
            raise Exception("503 UNAVAILABLE")

        j = self.make_job(always_503)
        output_path = j.run()   # 不再拋例外

        self.assertEqual(j.failed_count, 2)
        self.assertEqual(j.done_count, 0)
        # 每段 5 次重試 × 20 秒 × 2 段
        self.assertEqual(self.sleeper.total, 200)
        text = self.read_output(output_path)
        self.assertIn("[此段轉錄失敗：", text)

    def test_failed_segment_does_not_block_later_segments(self):
        def second_fails(path, client):
            # 第 2 段的暫存檔名是 _temp_seg_1
            if "_temp_seg_1" in path:
                raise Exception("503 UNAVAILABLE")
            return "第一段內容"

        j = self.make_job(second_fails)
        output_path = j.run()

        self.assertEqual(j.done_count, 1)
        self.assertEqual(j.failed_count, 1)
        text = self.read_output(output_path)
        self.assertIn("第一段內容", text)
        self.assertIn("=== 第 2 段（00:30:00 - 01:00:00）===", text)
        self.assertIn("[此段轉錄失敗：", text)

    def test_all_segments_fail_still_writes_output(self):
        def always_503(path, client):
            raise Exception("503 UNAVAILABLE")

        j = self.make_job(always_503)
        output_path = j.run()

        text = self.read_output(output_path)
        self.assertEqual(text.count("[此段轉錄失敗："), 2)
        self.assertIn("=== 第 1 段（00:00:00 - 00:30:00）===", text)
        self.assertIn("=== 第 2 段（00:30:00 - 01:00:00）===", text)

    def test_placeholder_contains_reason_and_hint(self):
        def always_503(path, client):
            raise Exception("503 UNAVAILABLE")

        j = self.make_job(always_503, segment_list=[(0, 1800)])
        output_path = j.run()

        text = self.read_output(output_path)
        self.assertIn("Gemini 伺服器回傳 503", text)
        self.assertIn("可於程式內重試", text)

    def test_quota_error_still_aborts_but_saves_completed(self):
        def first_ok_then_quota(path, client):
            if "_temp_seg_0" in path:
                return "第一段內容"
            raise Exception("429 RESOURCE_EXHAUSTED")

        j = self.make_job(first_ok_then_quota)
        with self.assertRaises(job.QuotaExhausted):
            j.run()

        # 中止前已完成的段落必須先寫檔，不能整份丟掉
        with open(j.output_path, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("第一段內容", text)

    def test_unprocessed_segment_placeholder_has_no_none(self):
        """429 中止時後面段落根本沒被處理，佔位符不能印出「失敗：None」"""
        def first_ok_then_quota(path, client):
            if "_temp_seg_0" in path:
                return "第一段內容"
            raise Exception("429 RESOURCE_EXHAUSTED")

        j = self.make_job(
            first_ok_then_quota,
            segment_list=[(0, 1800), (1800, 3600), (3600, 5400)],
        )
        with self.assertRaises(job.QuotaExhausted):
            j.run()

        with open(j.output_path, encoding="utf-8") as f:
            text = f.read()
        self.assertNotIn("失敗：None", text)
        self.assertIn("任務中止，此段尚未處理", text)
```

在 `TestManualRetry` 類別中新增：

```python
    def test_user_declines_marks_failure_and_continues(self):
        def always_503(path, client):
            raise Exception("503 UNAVAILABLE")

        j = self.make_job(always_503, auto_retry=False, ask_returns=False)
        output_path = j.run()   # 不再拋例外

        self.assertEqual(j.failed_count, 2)
        text = self.read_output(output_path)
        self.assertIn("使用者取消重試", text)
```

- [ ] **Step 2: 執行測試確認失敗**

```bash
./venv/Scripts/python.exe -m unittest discover -s tests -v
```

Expected: FAIL，`test_exhausted_retries_marks_failure_and_continues` 會因為 `run()` 拋例外而失敗。

- [ ] **Step 3: 改寫 `job.py` 的 `_transcribe_with_retry`**

把方法簽章與兩個 `raise` 分支改為回傳 `None`：

```python
    def _transcribe_with_retry(self, r: SegmentResult, temp_path: str) -> str | None:
        """回傳逐字稿；重試耗盡或使用者放棄時設定 r.error 並回傳 None。

        回傳 None 不是錯誤處理的偷懶——單段失敗不該毀掉整個任務，
        呼叫端會標記這段、繼續跑下一段，結束後可用「重試失敗的 N 段」補跑。
        """
        retry_count = 0
        while True:
            try:
                return self._transcribe(temp_path, self.client)
            except Exception as e:
                if transcriber.is_quota_error(e):
                    logger.write_log(
                        f"轉錄中止 -> {type(e).__name__} | HTTP 429 配額用盡", "ERROR"
                    )
                    raise QuotaExhausted(
                        "API 免費用量已達上限，請等明天配額重置後再試"
                    ) from e

                classified = transcriber.classify_error(e)
                if classified is None:
                    raise
                reason, status = classified

                # 錯誤行只記例外類型 + status + 重試次數（見 ARCHITECTURE.md 落檔紀律）
                logger.write_log(
                    f"第{r.index}段 上傳Gemini -> {type(e).__name__} | "
                    f"{status} | 重試 {retry_count}/{config.MAX_AUTO_RETRIES}",
                    "ERROR",
                )
                self.cb.log(f"[錯誤] {reason}")

                if self.auto_retry:
                    retry_count += 1
                    if retry_count > config.MAX_AUTO_RETRIES:
                        return self._mark_failed(
                            r, status,
                            f"{reason}，已自動重試 {config.MAX_AUTO_RETRIES} 次仍失敗",
                        )
                    self.cb.log(
                        f"[{r.index}/{self.total}] 自動重試中... "
                        f"({retry_count}/{config.MAX_AUTO_RETRIES})"
                    )
                    self._wait_before_retry(r, retry_count)
                else:
                    if not self.cb.ask(f"{reason}，是否重試？"):
                        return self._mark_failed(
                            r, status, f"{reason}（使用者取消重試）"
                        )
                    self.cb.log(f"[{r.index}/{self.total}] 重試中...")

    def _mark_failed(self, r: SegmentResult, status: str, reason: str) -> None:
        """標記單段最終失敗，回傳 None 讓呼叫端繼續下一段。"""
        r.error = reason
        logger.write_log(f"第{r.index}段 最終失敗 -> {status}", "ERROR")
        self.cb.log(f"[{r.index}/{self.total}] {reason}，標記後繼續")
        return None
```

- [ ] **Step 4: 改寫 `_process_one` 處理 `None` 回傳**

把 `_process_one` 的 try 區塊改為：

```python
        try:
            self._cut(self.audio_path, r.start_sec, r.end_sec - r.start_sec, temp_path)
            if not os.path.exists(temp_path):
                raise Exception(f"第 {r.index} 段切割失敗，請確認 ffmpeg 是否正常運作")

            self.cb.log(f"[{r.index}/{self.total}] 上傳至 Gemini，等待轉錄...")
            text = self._transcribe_with_retry(r, temp_path)
            if text is None:
                return   # 已由 _mark_failed 記錄原因，繼續下一段
            r.text = text
            r.error = None
            self.cb.log(f"[{r.index}/{self.total}] 完成")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
```

- [ ] **Step 5a: 在 `_process` 加回 429 中止前寫檔**

Task 6 原本的計畫把這段放在 Task 6，但那違反 Task 6「行為零改變」的約束，經裁決挪到這裡。把 `_process` 改為：

```python
    def _process(self, targets: list[SegmentResult]) -> str:
        try:
            for r in targets:
                self._process_one(r)
                self.cb.progress(
                    self.done_count, self.total,
                    f"{self.done_count} / {self.total} 段完成",
                )
        except QuotaExhausted:
            # 配額用盡要中止，但已完成的段落先寫檔，不能整份丟掉
            self._write_output()
            raise
        return self._write_output()
```

本 Task 的 `test_quota_error_still_aborts_but_saves_completed` 與
`test_unprocessed_segment_placeholder_has_no_none` 就是在驗這個行為。

- [ ] **Step 5: 改寫 `_write_output` 加入佔位符**

```python
    def _write_output(self) -> str:
        """合併所有段落寫檔。失敗段落寫佔位符，不因此少一段。

        可重複呼叫：補跑成功後再叫一次就會原地覆寫同一個檔案。
        """
        lines = []
        for r in self.results:
            start_hms = segmod.seconds_to_hms(r.start_sec)
            end_hms = segmod.seconds_to_hms(r.end_sec)
            lines.append(f"=== 第 {r.index} 段（{start_hms} - {end_hms}）===")
            lines.append("")
            if r.text is not None:
                lines.append(r.text)
            else:
                # r.error 為 None 代表這段根本沒被處理到（例如前一段觸發 429 中止），
                # 不能讓佔位符印出「失敗：None」
                reason = r.error or "任務中止，此段尚未處理"
                lines.append(f"[此段轉錄失敗：{reason}，可於程式內重試]")
            lines.append("")

        merged = "\n".join(lines).strip()
        with open(self.output_path, "w", encoding="utf-8") as f:
            f.write(merged)
        return self.output_path
```

保留 `_write_output` 開頭那行 `self.cb.log("\n合併逐字稿...")`，不要在改寫時弄丟。

- [ ] **Step 6: 執行測試確認通過**

```bash
./venv/Scripts/python.exe -m unittest discover -s tests -v
```

Expected: 35 個測試全過。

- [ ] **Step 7: Commit**

```bash
git add job.py tests/test_job.py
git commit -m "feat: 單段轉錄失敗不再中止整個任務

原本第 N 段重試耗盡就 raise，跳過合併寫檔，導致前面已成功段落的
逐字稿隨任務中止一併丟失，後續段落也不會處理。改為標記失敗、繼續
下一段，輸出檔一律產生，失敗段落寫佔位符。

429 配額用盡維持中止（繼續跑只會持續撞牆），但中止前先把已完成
段落寫檔。

ARCHITECTURE.md:135「若某段 API 呼叫失敗，只需重跑該段」的承諾，
到這裡才算補上一半——補跑機制在下一個 commit。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 9: 補跑失敗段落（`retry_failed()` + UI 按鈕）

**Files:**
- Modify: `job.py`（新增 `retry_failed()`）
- Modify: `ui.py`（新增補跑按鈕、`_retry_failed` 處理器、完成訊息分岔）
- Modify: `tests/test_job.py`（新增補跑測試）

**Interfaces:**
- Consumes: `job.TranscriptionJob.results` `job.TranscriptionJob.failed_count`
- Produces: `job.TranscriptionJob.retry_failed() -> str`

- [ ] **Step 1: 先寫失敗的測試**

在 `tests/test_job.py` 新增類別：

```python
class TestRetryFailed(JobTestBase):
    def test_retry_failed_replaces_placeholder(self):
        state = {"fail_second": True}

        def second_fails_first_round(path, client):
            if "_temp_seg_1" in path and state["fail_second"]:
                raise Exception("503 UNAVAILABLE")
            return "補跑成功內容" if "_temp_seg_1" in path else "第一段內容"

        j = self.make_job(second_fails_first_round)
        output_path = j.run()
        self.assertEqual(j.failed_count, 1)
        self.assertIn("[此段轉錄失敗：", self.read_output(output_path))

        state["fail_second"] = False
        j.retry_failed()

        self.assertEqual(j.failed_count, 0)
        text = self.read_output(output_path)
        self.assertNotIn("[此段轉錄失敗：", text)
        self.assertIn("補跑成功內容", text)
        self.assertIn("第一段內容", text)

    def test_retry_failed_only_touches_failed_segments(self):
        state = {"fail_second": True, "calls": []}

        def tracker(path, client):
            state["calls"].append(os.path.basename(path))
            if "_temp_seg_1" in path and state["fail_second"]:
                raise Exception("503 UNAVAILABLE")
            return "內容"

        j = self.make_job(tracker)
        j.run()
        state["fail_second"] = False
        state["calls"].clear()
        j.retry_failed()

        # 補跑只碰第 2 段，第 1 段不該被重打
        self.assertTrue(all("_temp_seg_1" in name for name in state["calls"]))

    def test_retry_failed_can_fail_again(self):
        def always_fails_second(path, client):
            if "_temp_seg_1" in path:
                raise Exception("503 UNAVAILABLE")
            return "第一段內容"

        j = self.make_job(always_fails_second)
        j.run()
        self.assertEqual(j.failed_count, 1)

        output_path = j.retry_failed()
        self.assertEqual(j.failed_count, 1)
        self.assertIn("[此段轉錄失敗：", self.read_output(output_path))

    def test_retry_failed_with_nothing_failed_is_noop(self):
        j = self.make_job(lambda path, client: "內容")
        j.run()
        output_path = j.retry_failed()
        self.assertEqual(j.failed_count, 0)
        self.assertEqual(self.read_output(output_path).count("內容"), 2)
```

- [ ] **Step 2: 執行測試確認失敗**

```bash
./venv/Scripts/python.exe -m unittest discover -s tests -v
```

Expected: FAIL，`AttributeError: 'TranscriptionJob' object has no attribute 'retry_failed'`。

- [ ] **Step 3: 在 `job.py` 新增 `retry_failed()`**

在 `run()` 方法下方加入：

```python
    def retry_failed(self) -> str:
        """只重跑失敗的段落，成功則原地覆寫同一個輸出檔。

        音訊從原始檔重新切割，不保留暫存檔——暫存檔可能數百 MB，
        留在專案目錄很髒，而重切一段 30 分鐘音訊只需數秒。
        """
        return self._process([r for r in self.results if r.text is None])
```

- [ ] **Step 4: 執行測試確認通過**

```bash
./venv/Scripts/python.exe -m unittest discover -s tests -v
```

Expected: 39 個測試全過。

- [ ] **Step 5: `ui.py` 新增補跑按鈕**

在 `_build_ui` 的「輸出路徑 + 開啟資料夾」區塊（原 `main.py:476-484` 對應處），於 `btn_open_folder` 之後加入：

```python
        self.btn_retry_failed = ttk.Button(
            frame_output, text="重試失敗的段落", command=self._retry_failed
        )
        # 預設隱藏，有失敗段落時才顯示
```

- [ ] **Step 6: `ui.py` 新增 `_retry_failed` 處理器**

在 `_open_output_folder` 方法附近加入：

```python
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
            self._done("", success=False, failed_count=self._job.failed_count)
        except Exception as e:
            self._log(f"\n[ERROR] {e}")
            write_log(f"補跑中止 -> {type(e).__name__}", "ERROR")
            self._finalize_log_file(success=False)
            self._done("", success=False, failed_count=self._job.failed_count)
```

- [ ] **Step 7: `ui.py` 的 `_done` 與 `_poll_queue` 加入 `failed_count`**

`_done` 改為：

```python
    def _done(self, output_path: str, success: bool, download_only: bool = False,
              failed_count: int = 0):
        self.msg_queue.put(("done", (output_path, success, download_only, failed_count)))
```

`_poll_queue` 的 `done` 分支改為：

```python
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
                            self.btn_retry_failed.config(
                                text=f"重試失敗的 {failed_count} 段"
                            )
                            self.btn_retry_failed.pack(side="left", padx=(6, 0))
                            messagebox.showwarning(
                                "部分完成",
                                f"逐字稿已儲存（{ok}/{total} 段成功，{failed_count} 段失敗）：\n"
                                f"{output_path}\n\n"
                                "失敗段落在檔案中標記為佔位符，可按「重試失敗的段落」補跑。",
                            )
                        else:
                            self.btn_retry_failed.pack_forget()
                            self.output_label.config(
                                text=f"輸出：{output_path}", foreground="green"
                            )
                            messagebox.showinfo("完成", f"逐字稿已儲存：\n{output_path}")
                    else:
                        self.progress_label.config(text="發生錯誤，請查看上方記錄")
                        if failed_count > 0:
                            self.btn_retry_failed.config(
                                text=f"重試失敗的 {failed_count} 段"
                            )
                            self.btn_retry_failed.pack(side="left", padx=(6, 0))
```

- [ ] **Step 8: `ui.py` 的 `_worker` 傳入 `failed_count`**

`_worker` 成功結束那段改為：

```python
            output_path = self._job.run()

            self._log(f"\n逐字稿已儲存：{output_path}")
            self._finalize_log_file(success=self._job.failed_count == 0)
            self._done(output_path, success=True, failed_count=self._job.failed_count)
```

`_worker` 開頭重置 UI 的部分（`_start` 內）加入隱藏補跑按鈕：

```python
        self.btn_open_folder.pack_forget()
        self.btn_retry_failed.pack_forget()
```

- [ ] **Step 9: 驗證**

```bash
./venv/Scripts/python.exe -c "import main; print('import ok')"
./venv/Scripts/python.exe -m unittest discover -s tests -v
```

Expected: `import ok`；39 個測試全過。

- [ ] **Step 10: 請使用者手動驗證補跑流程**

請使用者跑一次真實轉錄。若剛好遇到 503 導致某段失敗，確認：進度標籤有倒數、失敗後繼續跑下一段、結束時跳「部分完成」對話框、「重試失敗的 N 段」按鈕出現、按下後只補跑失敗段落、成功後按鈕消失且逐字稿檔案的佔位符被真實內容取代。

若沒遇到 503（無法自然觸發），至少確認正常流程（全部成功）行為不變：完成對話框、輸出路徑、按鈕不出現。

- [ ] **Step 11: Commit**

```bash
git add job.py ui.py tests/test_job.py
git commit -m "feat: 新增「重試失敗的 N 段」補跑功能

任務結束後若有失敗段落，UI 出現補跑按鈕，只重跑那幾段，音訊從原始檔
重新切割（不保留暫存檔），成功後原地覆寫同一個輸出檔、佔位符被真實
內容取代。

至此補齊 ARCHITECTURE.md:135「若某段 API 呼叫失敗，只需重跑該段，
不需重跑整份」的既有承諾。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 10: 更新文件

**Files:**
- Modify: `ARCHITECTURE.md`
- Modify: `README.md`
- Modify: `PITFALLS.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: 前九個 Task 的成果
- Produces: 無程式介面

- [ ] **Step 1: 更新 `ARCHITECTURE.md` 檔案清單**

把「檔案清單」表格中 `main.py` 那列替換為：

```markdown
| `main.py` | 程式入口：banner + Tk root |
| `config.py` | 全域常數（模型、切割長度、重試設定） |
| `logger.py` | `logs/app.log` 落檔 |
| `segments.py` | 時間字串解析 + 分段計算（純函式） |
| `audio.py` | ffprobe 取時長 / ffmpeg 切割 / yt-dlp 下載 |
| `transcriber.py` | Gemini 呼叫、prompt、錯誤分類 |
| `job.py` | 轉錄流程編排（不 import tkinter，可獨立測試） |
| `ui.py` | `SnapTranscriptApp` 主視窗 |
| `tests/` | unittest 測試（`python -m unittest discover -s tests`） |
```

- [ ] **Step 2: 更新 `ARCHITECTURE.md` 執行流程**

把「逐段處理」那段（原 38-46 行）替換為：

```
                    └─ 逐段處理（job.TranscriptionJob）：
                          ├─ ffmpeg 切割暫存檔
                          ├─ genai.upload_file 上傳
                          ├─ gemini-flash-latest 轉錄
                          │     └─ 失敗（503 / 空白結果）→ 依「自動重試」設定：
                          │           勾選＝等 RETRY_WAIT_SECONDS 秒後重試，
                          │                 至多 MAX_AUTO_RETRIES 次
                          │           未勾選＝跳 dialog 詢問使用者
                          │     └─ 重試耗盡 / 使用者放棄 → 標記該段失敗，繼續下一段
                          │     └─ 429 配額用盡 → 中止，但已完成段落先寫檔
                          └─ 刪除暫存檔
                    └─ 合併所有段落 → 輸出 _transcript.txt
                          （失敗段落寫佔位符，不因此少一段）
                    └─ 有失敗段落 → UI 顯示「重試失敗的 N 段」按鈕
                          └─ 按下只補跑失敗段落，成功後原地覆寫輸出檔
```

- [ ] **Step 3: 更新 `ARCHITECTURE.md` 設定變數表**

在 `MAX_AUTO_RETRIES` 那列下方加入，並把表頭的 `（main.py）` 改成 `（config.py）`：

```markdown
| `RETRY_WAIT_SECONDS` | 20 | 自動重試前的固定等待秒數 |
```

- [ ] **Step 4: 更新 `ARCHITECTURE.md` Log 章節**

在「落檔只有三種情況」那段之後加入：

```markdown
拆分為模組後，「推 UI」與「落檔」在型別上就是分開的兩件事：`job.py` 用
`JobCallbacks.log()` 推 UI、用 `logger.write_log()` 落檔，不再需要靠
`to_file=False` 預設值防呆。`ui.py` 的 `_log()` 退化為單純的 UI 推送包裝。

段落級失敗新增一種錯誤行：`第N段 最終失敗 -> <status>`，在單段重試耗盡或
使用者放棄重試時寫入。
```

- [ ] **Step 5: 更新 `ARCHITECTURE.md` 輸出格式章節**

在「逐字稿」範例之後加入：

```markdown
轉錄失敗的段落不會消失，改寫佔位符，段落編號與時間範圍照常：

```
=== 第 2 段（00:30:00 - 01:00:00）===

[此段轉錄失敗：Gemini 伺服器回傳 503，已自動重試 5 次仍失敗，可於程式內重試]
```

按 UI 的「重試失敗的 N 段」補跑成功後，佔位符會被真實逐字稿取代，原地覆寫同一個檔案。
```

- [ ] **Step 6: 更新 `README.md`**

在功能說明區加入一段（放在「自動重試」相關敘述附近）：

```markdown
### 轉錄失敗怎麼辦

單一段落轉錄失敗不會影響其他段落——程式會標記該段、繼續處理後面的段落，
最後照常輸出逐字稿，失敗的段落在檔案中顯示為佔位符。

轉錄結束後若有失敗段落，畫面會出現「重試失敗的 N 段」按鈕，按下只會重跑
那幾段，不需要整個檔案重來。補跑成功後逐字稿會自動更新。

勾選「自動重試」（預設開啟）時，每段遇到伺服器錯誤會等 20 秒後重試，最多 5 次。
```

- [ ] **Step 7: 更新 `PITFALLS.md` 的 503 條目**

在「2026-07-16 更新」那段之後加入：

```markdown
**2026-07-31 更新：** 發現原本的自動重試沒有任何等待——失敗後立刻重打，
但 503 的語意是伺服器滿載，0 秒後重打仍然滿載，5 次重試在數秒內全部燒完，
等於沒有重試。改為每次重試前固定等待 `RETRY_WAIT_SECONDS`（20）秒，以 1 秒
一輪的倒數迴圈實作讓 UI 顯示剩餘秒數。同時單段重試耗盡不再中止整個任務，
改為標記後續跑，結束後可用「重試失敗的 N 段」按鈕補跑。
```

並在「禁止」那段補上：

```markdown
不要把重試改回「失敗立刻重打」，也不要把等待改成單次 `sleep(20)`——
倒數迴圈是為了讓 UI 不會看起來像凍結。20 秒退避只在使用者勾選「自動重試」
時套用，未勾選時仍走 dialog 且完全不 sleep，這點不可改。
```

同時修正「解法」那段過時的敘述——原文寫「使用者按「是」繼續、按「否」中止」，
2026-07-31 起按「否」改為標記該段失敗後繼續下一段，不再中止整個任務。把該句改為：

```markdown
**解法：** 由 `job.TranscriptionJob` 的重試迴圈包住 `transcribe_segment` 呼叫，
503 時 log 錯誤、依「自動重試」設定決定自動重試或跳 dialog 詢問。使用者按「否」
或自動重試耗盡時，標記該段失敗並繼續下一段（不中止整個任務），結束後可用
「重試失敗的 N 段」按鈕補跑。背景執行緒透過 `msg_queue + threading.Event`
阻塞等待主執行緒的 dialog 結果。
```

- [ ] **Step 8: 更新 `CHANGELOG.md`**

在最上方加入（沿用檔案現有格式）：

```markdown
## 2026-07-31

### 重構
- `main.py`（973 行）拆分為 `config.py`、`logger.py`、`segments.py`、`audio.py`、`transcriber.py`、`job.py`、`ui.py`，`main.py` 只剩程式入口
- 轉錄流程抽為 `job.TranscriptionJob`，不 import tkinter，透過 callback 與 UI 溝通，可在無 GUI / 無 ffmpeg / 無網路的環境下測試
- 測試從 9 個增加到 39 個，新增 `tests/test_transcriber.py`、`tests/test_job.py`
- `_log()` 移除 `to_file` 參數，落檔與推 UI 在型別上分開

### 修正
- 自動重試原本失敗後立刻重打，等於沒有重試效果；改為每次等待 20 秒（`RETRY_WAIT_SECONDS`），進度標籤顯示倒數
- 單段轉錄失敗原本會中止整個任務，且已完成段落的逐字稿隨之丟失；改為標記該段、繼續下一段，輸出檔一律產生
- 429 配額用盡仍會中止，但中止前先把已完成段落寫檔

### 新增
- 「重試失敗的 N 段」按鈕：轉錄結束後若有失敗段落，可只補跑那幾段，成功後原地覆寫輸出檔
- 逐字稿中失敗段落以佔位符呈現，段落編號與時間範圍不變
```

- [ ] **Step 9: 驗證文件與程式一致**

```bash
grep -n "MAX_AUTO_RETRIES\|RETRY_WAIT_SECONDS" config.py ARCHITECTURE.md
./venv/Scripts/python.exe -m unittest discover -s tests 2>&1 | tail -3
```

Expected: 常數值與文件記載一致；39 個測試全過。

- [ ] **Step 10: Commit**

```bash
git add ARCHITECTURE.md README.md PITFALLS.md CHANGELOG.md
git commit -m "docs: 同步模組拆分與段落級容錯的文件

ARCHITECTURE 更新檔案清單、執行流程、log 章節、輸出格式；
README 補充失敗段落與補跑說明；PITFALLS 的 503 條目補記
「原本沒有等待」這個根因；CHANGELOG 記錄本次變更。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## 完成標準

全部 Task 結束後應滿足：

- `wc -l main.py` 約 40 行；`ui.py` 約 600 行；`job.py` 約 220 行
- `./venv/Scripts/python.exe -m unittest discover -s tests` 顯示 39 個測試全過，且執行不需要 ffmpeg、網路或 API Key
- `grep -n "to_file" ui.py job.py` 無輸出
- `git status` 乾淨，專案根目錄沒有殘留的 `_temp_seg_*` 檔案
- 雙擊 `Run SnapTranscript.bat` 能正常啟動，完整跑完一次短音訊轉錄
