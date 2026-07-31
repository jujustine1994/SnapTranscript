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
        self._sleep = sleep_fn or time.sleep  # Task 7 的重試退避才會用到，目前無呼叫點

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
                    self._wait_before_retry(r, retry_count)
                else:
                    if not self.cb.ask(f"{reason}，是否重試？"):
                        raise Exception("已取消重試") from e
                    self.cb.log(f"[{r.index}/{self.total}] 重試中...")

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
