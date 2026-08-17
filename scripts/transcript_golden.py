# -*- coding: utf-8 -*-
"""逐字稿輸出檔的逐字回歸驗收（golden file）。

**用途：改動 `job._write_output` 或它用到的任何字串之前先存一份基準，改完再
比對。** 單元測試驗的是邏輯，這支驗的是「真的寫出來的那份 `_transcript.txt`
有沒有變」——2026-08-16 的多語言遷移就是靠它確認繁中輸出逐 byte 不變。

作法：餵一組固定的假 `SegmentResult`（涵蓋成功／試過但失敗／根本沒輪到跑
三種狀態），走**真正的** `TranscriptionJob._write_output()` 寫檔，再把產出的
bytes 連同 sha256 存下來。不打網路、不需要 ffmpeg、不花 API 額度，可以隨便重跑。

    ./venv/Scripts/python.exe scripts/transcript_golden.py make  <基準資料夾>
    # ...改 code...
    ./venv/Scripts/python.exe scripts/transcript_golden.py make  <新資料夾>
    ./venv/Scripts/python.exe scripts/transcript_golden.py check <基準> <新>

`check` 回傳 exit code 0 = 完全一致，1 = 有差異（會印出 unified diff）。

⚠ 這支刻意比對 **bytes** 不是字串：逐字稿是 UTF-8 落檔，換行與編碼的變化
（`\n` 變 `\r\n`、少了結尾換行）用字串比對看不出來，但使用者的下游工具會炸。
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import job  # noqa: E402


# 固定的假資料。三種段落狀態各一，涵蓋 `_write_output` 的所有分支：
#   1. 成功            → 寫出逐字稿本文
#   2. 試過但失敗       → 寫出帶 r.error 的佔位符
#   3. 根本沒輪到跑     → 寫出「任務中止」的佔位符（r.error 是 None）
# 內容刻意包含中英日字元與換行，編碼跑掉時才看得出來。
FIXTURE = [
    (1, 0, 1800, "說話者 A：這是第一段的逐字稿內容。\n\n說話者 B：Yes, understood.", None),
    (2, 1800, 3600, None, "Gemini 伺服器回傳 503，已自動重試 5 次仍失敗"),
    (3, 3600, 5400, "司会者：本日はご参加ありがとうございます。", None),
    (4, 5400, 7200, None, None),
]


def _build_output() -> bytes:
    """跑真正的 `_write_output`，回傳落檔後的 bytes。"""
    logged: list[str] = []
    callbacks = job.JobCallbacks(
        log=logged.append,
        progress=lambda cur, total, label: None,
        ask=lambda question: False,
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "golden_fixture.mp3")
        j = job.TranscriptionJob(
            audio_path=audio_path,
            segment_list=[(s, e) for _, s, e, _, _ in FIXTURE],
            client=None,
            auto_retry=True,
            callbacks=callbacks,
            transcribe_fn=lambda *a, **k: "",
            cut_fn=lambda *a, **k: None,
            sleep_fn=lambda *a, **k: None,
        )
        for result, (index, _s, _e, text, error) in zip(j.results, FIXTURE):
            assert result.index == index, "fixture 的段號與 job 建出來的對不上"
            result.text = text
            result.error = error
        out_path = j._write_output()
        with open(out_path, "rb") as f:
            return f.read()


def make(outdir: str) -> None:
    os.makedirs(outdir, exist_ok=True)
    data = _build_output()
    txt_path = os.path.join(outdir, "transcript_golden.txt")
    with open(txt_path, "wb") as f:
        f.write(data)
    manifest = {
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "segments": len(FIXTURE),
    }
    with open(os.path.join(outdir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"已寫入 {txt_path}")
    print(f"  sha256 = {manifest['sha256']}")
    print(f"  bytes  = {manifest['bytes']}")


def check(base_dir: str, new_dir: str) -> int:
    base_path = os.path.join(base_dir, "transcript_golden.txt")
    new_path = os.path.join(new_dir, "transcript_golden.txt")
    with open(base_path, "rb") as f:
        base = f.read()
    with open(new_path, "rb") as f:
        new = f.read()
    if base == new:
        print(f"一致：{len(base)} bytes，sha256 = {hashlib.sha256(base).hexdigest()}")
        return 0
    print("不一致！")
    print(f"  基準 {len(base)} bytes sha256 = {hashlib.sha256(base).hexdigest()}")
    print(f"  新版 {len(new)} bytes sha256 = {hashlib.sha256(new).hexdigest()}")
    diff = difflib.unified_diff(
        base.decode("utf-8", "replace").splitlines(),
        new.decode("utf-8", "replace").splitlines(),
        fromfile="base", tofile="new", lineterm="",
    )
    for line in diff:
        print(line)
    return 1


def main(argv: list[str]) -> int:
    if len(argv) >= 3 and argv[1] == "make":
        make(argv[2])
        return 0
    if len(argv) >= 4 and argv[1] == "check":
        return check(argv[2], argv[3])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
