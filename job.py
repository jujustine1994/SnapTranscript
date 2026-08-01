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
        # 暫存檔名帶 PID：兩個 SnapTranscript 同時跑時，檔名若只有段號會互相
        # 覆寫、甚至把對方剛切好的檔案在 finally 裡刪掉，造成假的「切割失敗」
        # 或段落內容錯置（實測重現過）
        self._temp_tag = os.getpid()

    # ---- 狀態查詢 ----
    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def done_count(self) -> int:
        return sum(1 for r in self.results if r.text is not None)

    @property
    def failed_count(self) -> int:
        """尚未成功的段落數（補跑要處理的就是這些）。

        包含兩種：真的試過但失敗的，以及根本還沒輪到跑的（例如前一段觸發
        429 中止）。要分辨用 attempted_failed_count / pending_count。
        """
        return sum(1 for r in self.results if r.text is None)

    @property
    def attempted_failed_count(self) -> int:
        """試過但失敗的段落數（r.error 有值才算）。"""
        return sum(1 for r in self.results if r.text is None and r.error is not None)

    @property
    def pending_count(self) -> int:
        """根本沒輪到跑的段落數（任務中途中止時才會有）。"""
        return sum(1 for r in self.results if r.text is None and r.error is None)

    # ---- 主流程 ----
    def run(self) -> str:
        """跑全部段落，回傳輸出檔路徑。"""
        return self._process(list(self.results))

    def retry_failed(self) -> str:
        """只重跑失敗的段落，成功則原地覆寫同一個輸出檔。

        音訊從原始檔重新切割，不保留暫存檔——暫存檔可能數百 MB，
        留在專案目錄很髒，而重切一段 30 分鐘音訊只需數秒。
        """
        return self._process([r for r in self.results if r.text is None])

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
        except Exception:
            # 任何未分類的原因中止（網路中斷、逾時、程式錯誤...），也要先
            # 保住已完成的段落，不能讓部分逐字稿隨中止一起消失
            self._write_output()
            raise
        return self._write_output()

    def _process_one(self, r: SegmentResult):
        start_hms = segmod.seconds_to_hms(r.start_sec)
        end_hms = segmod.seconds_to_hms(r.end_sec)
        self.cb.log(f"\n[{r.index}/{self.total}] 切割 {start_hms} → {end_hms}...")

        temp_path = os.path.join(
            config.SCRIPT_DIR, f"_temp_seg_{self._temp_tag}_{r.index - 1}{self._ext}"
        )
        try:
            self._cut(self.audio_path, r.start_sec, r.end_sec - r.start_sec, temp_path)
            if not os.path.exists(temp_path):
                self._mark_failed(
                    r, "切割失敗",
                    f"第 {r.index} 段切割失敗，請確認 ffmpeg 是否正常運作",
                )
                return

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
                        "已達 Gemini API 用量上限（可能是短時間內請求過多，或當日額度用盡）。"
                        "已完成的段落已存檔，請稍後用「重試失敗的段落」補跑。"
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
        """合併所有段落寫檔。失敗段落寫佔位符，不因此少一段。

        可重複呼叫：補跑成功後再叫一次就會原地覆寫同一個檔案。
        """
        self.cb.log("\n合併逐字稿...")
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
        # 先寫暫存檔再 os.replace：補跑是原地覆寫既有逐字稿，中途中斷不能
        # 讓使用者手上已有的成功段落被截斷（os.replace 在 Windows 上是原子的）
        tmp_path = self.output_path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(merged)
            os.replace(tmp_path, self.output_path)
        except OSError:
            # 寫檔失敗（磁碟滿、權限、路徑被移除...）時把半截的 .tmp 收乾淨，
            # 否則使用者的音訊資料夾會留下一個看不懂的 xxx_transcript.txt.tmp。
            # 清除本身失敗就算了——原始的寫檔錯誤才是要讓使用者看到的那個。
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
            raise
        return self.output_path
