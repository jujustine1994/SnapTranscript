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

    def test_retry_failed_saves_completed_before_quota_abort(self):
        """補跑途中若又遇 429，該次補跑中已成功的段落仍要先寫檔。

        這條測試守住「retry_failed 必須複用 _process」的約束：若有人把
        retry_failed 改成繞過 _process 自己迴圈（跳過 except QuotaExhausted
        先寫檔再拋出的保護），本測試必須抓到。
        """
        state = {"retry_round": False}

        def transcribe_fn(path, client):
            if "_temp_seg_0" in path:
                return "第一段內容"
            if "_temp_seg_1" in path:
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


if __name__ == "__main__":
    unittest.main()
