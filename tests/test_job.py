import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import job


def _is_segment(path, index):
    """精確判斷 path 是否為第 index 段（從 0 起算）的暫存檔。

    暫存檔名格式是 `_temp_seg_<pid>_<index><副檔名>`，PID 是為了讓兩個
    SnapTranscript 同時跑時不會共用檔名（見 job.py 的 _temp_tag）。

    不可用 `f"_{index}" in path` 做子字串比對：段數到兩位數時
    `_1` 會誤匹配 `_10`，PID 裡的數字也會誤中。
    """
    name = os.path.basename(path)
    return name.rsplit(".", 1)[0].endswith(f"_{index}")


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

        # 隔離真實的 logs/app.log 與專案根目錄：測試不該把假錯誤灌進使用者
        # 真實的除錯紀錄，也不該把暫存檔寫進真實的 config.SCRIPT_DIR。
        self.written_logs = []

        def _fake_write_log(msg, level="INFO"):
            self.written_logs.append((level, msg))

        patcher_log = patch.object(job.logger, "write_log", side_effect=_fake_write_log)
        patcher_dir = patch.object(job.config, "SCRIPT_DIR", self.tmpdir.name)
        patcher_log.start()
        patcher_dir.start()
        self.addCleanup(patcher_log.stop)
        self.addCleanup(patcher_dir.stop)

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
        """未分類例外仍要中止任務，但中止前已完成的段落必須先寫檔——

        這正是「單段失敗不中止整個任務」這個分支要解決的缺陷，只是換了
        觸發路徑（未分類例外而非 429）：不能因為換了路徑就又復發。
        """
        def second_segment_booms(path, client):
            if _is_segment(path, 0):
                return "第一段內容"
            raise Exception("磁碟讀取失敗")

        j = self.make_job(second_segment_booms)
        with self.assertRaises(Exception) as ctx:
            j.run()
        self.assertIn("磁碟讀取失敗", str(ctx.exception))

        # 第 1 段已完成，即使第 2 段的未分類例外中止了整個任務，
        # 第 1 段的逐字稿也必須已經存檔
        text = self.read_output(j.output_path)
        self.assertIn("第一段內容", text)

    def test_quota_error_raises_quota_exhausted(self):
        def quota(path, client):
            raise Exception("429 RESOURCE_EXHAUSTED")

        j = self.make_job(quota)
        with self.assertRaises(job.QuotaExhausted):
            j.run()

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
            if _is_segment(path, 1):
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
            if _is_segment(path, 0):
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
            if _is_segment(path, 0):
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

    def test_user_declines_marks_failure_and_continues(self):
        def always_503(path, client):
            raise Exception("503 UNAVAILABLE")

        j = self.make_job(always_503, auto_retry=False, ask_returns=False)
        output_path = j.run()   # 不再拋例外

        self.assertEqual(j.failed_count, 2)
        text = self.read_output(output_path)
        self.assertIn("使用者取消重試", text)


class TestRetryFailed(JobTestBase):
    def test_retry_failed_replaces_placeholder(self):
        state = {"fail_second": True}

        def second_fails_first_round(path, client):
            if _is_segment(path, 1) and state["fail_second"]:
                raise Exception("503 UNAVAILABLE")
            return "補跑成功內容" if _is_segment(path, 1) else "第一段內容"

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
            if _is_segment(path, 1) and state["fail_second"]:
                raise Exception("503 UNAVAILABLE")
            return "內容"

        j = self.make_job(tracker)
        j.run()
        state["fail_second"] = False
        state["calls"].clear()
        j.retry_failed()

        # 補跑只碰第 2 段，第 1 段不該被重打
        self.assertTrue(all(_is_segment(name, 1) for name in state["calls"]))

    def test_retry_failed_can_fail_again(self):
        def always_fails_second(path, client):
            if _is_segment(path, 1):
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

    def test_retry_failed_saves_completed_before_quota_abort(self):
        """補跑途中若又遇 429，該次補跑中已成功的段落仍要先寫檔。

        這條測試守住「retry_failed 必須複用 _process」的約束：若有人把
        retry_failed 改成繞過 _process 自己迴圈（跳過 except QuotaExhausted
        先寫檔再拋出的保護），本測試必須抓到。
        """
        state = {"retry_round": False}

        def transcribe_fn(path, client):
            if _is_segment(path, 0):
                return "第一段內容"
            if _is_segment(path, 1):
                if state["retry_round"]:
                    return "補跑第二段成功"
                raise Exception("503 UNAVAILABLE")
            # _temp_seg_2（第三段）
            if state["retry_round"]:
                raise Exception("429 RESOURCE_EXHAUSTED")
            raise Exception("503 UNAVAILABLE")

        j = self.make_job(
            transcribe_fn,
            segment_list=[(0, 600), (600, 1200), (1200, 1800)],
        )
        output_path = j.run()
        self.assertEqual(j.failed_count, 2)

        state["retry_round"] = True
        with self.assertRaises(job.QuotaExhausted):
            j.retry_failed()

        # 第三段觸發 429 中止整次補跑，但第二段在中止前已補跑成功，
        # 必須先被寫進輸出檔，不能被整批丟掉
        text = self.read_output(output_path)
        self.assertIn("補跑第二段成功", text)


class TestCutFailure(JobTestBase):
    def test_cut_failure_marks_segment_failed_and_continues(self):
        """ffmpeg 切割失敗（音訊檔在轉錄途中被移走/刪除）不該拖垮整個任務，
        只應該降級成單段失敗，讓其他段落照跑。"""
        def noop_cut(audio_path, start_sec, duration_sec, output_path):
            pass   # 什麼都不做，temp_path 就不會存在

        callbacks, recorded = make_callbacks()
        self.recorded = recorded
        j = job.TranscriptionJob(
            audio_path=self.audio_path,
            segment_list=[(0, 1800), (1800, 3600)],
            client=None,
            auto_retry=True,
            callbacks=callbacks,
            transcribe_fn=lambda path, client: "第二段內容",
            cut_fn=noop_cut,
            sleep_fn=FakeSleep(),
        )
        output_path = j.run()   # 不應拋例外

        self.assertEqual(j.failed_count, 2)
        text = self.read_output(output_path)
        self.assertIn("切割失敗", text)

    def test_cut_failure_does_not_block_other_segments(self):
        """第 1 段切割失敗，第 2 段用真的假切割函式，應該正常成功。"""
        def cut_only_second(audio_path, start_sec, duration_sec, output_path):
            if _is_segment(output_path, 1):
                fake_cut(audio_path, start_sec, duration_sec, output_path)
            # 第 1 段：什麼都不做，temp_path 不存在

        callbacks, recorded = make_callbacks()
        self.recorded = recorded
        j = job.TranscriptionJob(
            audio_path=self.audio_path,
            segment_list=[(0, 1800), (1800, 3600)],
            client=None,
            auto_retry=True,
            callbacks=callbacks,
            transcribe_fn=lambda path, client: "第二段內容",
            cut_fn=cut_only_second,
            sleep_fn=FakeSleep(),
        )
        output_path = j.run()

        self.assertEqual(j.done_count, 1)
        self.assertEqual(j.failed_count, 1)
        text = self.read_output(output_path)
        self.assertIn("第二段內容", text)
        self.assertIn("切割失敗", text)


class TestFailureCounts(JobTestBase):
    """failed_count 要能分辨「試過但失敗」與「根本沒輪到跑」。

    429 中止時後面的段落連跑都沒跑，全部算成「失敗 N 段」會誤導使用者。
    """

    def test_all_failures_are_attempted(self):
        def always_503(path, client):
            raise Exception("503 UNAVAILABLE")

        j = self.make_job(always_503)
        j.run()
        self.assertEqual(j.failed_count, 2)
        self.assertEqual(j.attempted_failed_count, 2)
        self.assertEqual(j.pending_count, 0)

    def test_quota_abort_leaves_untouched_segments_pending(self):
        def first_ok_then_quota(path, client):
            if _is_segment(path, 0):
                return "第一段內容"
            raise Exception("429 RESOURCE_EXHAUSTED")

        j = self.make_job(
            first_ok_then_quota,
            segment_list=[(0, 1800), (1800, 3600), (3600, 5400)],
        )
        with self.assertRaises(job.QuotaExhausted):
            j.run()

        # 第2段觸發 429 中止但沒被標記失敗，第3段根本沒輪到 → 兩段都是 pending
        self.assertEqual(j.failed_count, 2)
        self.assertEqual(j.attempted_failed_count, 0)
        self.assertEqual(j.pending_count, 2)

    def test_mixed_failed_and_pending(self):
        def second_fails_third_quota(path, client):
            if _is_segment(path, 1):
                raise Exception("503 UNAVAILABLE")
            if _is_segment(path, 2):
                raise Exception("429 RESOURCE_EXHAUSTED")
            return "內容"

        j = self.make_job(
            second_fails_third_quota,
            segment_list=[(0, 1800), (1800, 3600), (3600, 5400), (5400, 7200)],
        )
        with self.assertRaises(job.QuotaExhausted):
            j.run()

        self.assertEqual(j.attempted_failed_count, 1)   # 第2段重試耗盡
        self.assertEqual(j.pending_count, 2)            # 第3段中止 + 第4段沒輪到
        self.assertEqual(j.failed_count, 3)


class TestTempFileIsolation(JobTestBase):
    """暫存檔名必須帶 PID，否則兩個 SnapTranscript 同時跑會互相刪檔。

    實測重現過：舊程序收尾時的 finally 把新程序剛切好的暫存檔刪掉，
    新程序的 os.path.exists 檢查失敗，記了一行假的「切割失敗」。
    """

    def test_temp_path_contains_pid(self):
        seen = []

        def capture(audio_path, start_sec, duration_sec, output_path):
            seen.append(os.path.basename(output_path))
            fake_cut(audio_path, start_sec, duration_sec, output_path)

        j = self.make_job(lambda p, c: "內容")
        j._cut = capture
        j.run()

        pid = str(os.getpid())
        self.assertTrue(all(pid in name for name in seen), seen)

    def test_two_jobs_do_not_share_temp_paths(self):
        """同一支程式裡兩個 job 的暫存檔名不得互撞（模擬兩個實例）。"""
        paths_a, paths_b = [], []

        def make_capture(bucket):
            def capture(audio_path, start_sec, duration_sec, output_path):
                bucket.append(os.path.basename(output_path))
                fake_cut(audio_path, start_sec, duration_sec, output_path)
            return capture

        job_a = self.make_job(lambda p, c: "A")
        job_a._cut = make_capture(paths_a)
        job_b = self.make_job(lambda p, c: "B")
        job_b._temp_tag = f"{os.getpid()}x"   # 模擬另一個行程的 PID
        job_b._cut = make_capture(paths_b)

        job_a.run()
        job_b.run()
        self.assertEqual(set(paths_a) & set(paths_b), set())


class TestAtomicWrite(JobTestBase):
    def test_no_tmp_file_left_after_write(self):
        """_write_output 先寫 .tmp 再 os.replace，成功後不該留下 .tmp 殘檔。"""
        j = self.make_job(lambda path, client: "內容")
        output_path = j.run()

        self.assertTrue(os.path.exists(output_path))
        self.assertFalse(os.path.exists(output_path + ".tmp"))

    def test_retry_write_does_not_truncate_on_success(self):
        """補跑成功後原地覆寫，既有段落內容應完整保留（原子寫入，不會截斷）。"""
        state = {"fail_second": True}

        def transcribe_fn(path, client):
            if _is_segment(path, 1) and state["fail_second"]:
                raise Exception("503 UNAVAILABLE")
            return "補跑成功內容" if _is_segment(path, 1) else "第一段內容"

        j = self.make_job(transcribe_fn)
        j.run()
        state["fail_second"] = False
        output_path = j.retry_failed()

        text = self.read_output(output_path)
        self.assertIn("第一段內容", text)
        self.assertIn("補跑成功內容", text)
        self.assertFalse(os.path.exists(output_path + ".tmp"))


class TestLogHygiene(JobTestBase):
    def test_error_log_never_contains_raw_exception_text(self):
        """落檔紀律：錯誤行只記 type(e).__name__ 與 status，絕不能把例外
        全文落檔——例外訊息可能挾帶 URL / response body。用一個訊息帶有
        敏感內容的例外，斷言落檔內容完全不含那段敏感文字。"""
        def leaky(path, client):
            raise Exception(
                "503 UNAVAILABLE https://secret.example.com/leak?token=abc123"
            )

        j = self.make_job(leaky, segment_list=[(0, 1800)])
        j.run()

        all_msgs = " ".join(msg for _level, msg in self.written_logs)
        self.assertNotIn("secret.example.com", all_msgs)
        self.assertNotIn("token=abc123", all_msgs)


if __name__ == "__main__":
    unittest.main()
