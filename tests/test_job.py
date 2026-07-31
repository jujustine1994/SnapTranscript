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
        # 5 次重試 × 每次 20 秒
        self.assertEqual(self.sleeper.total, 100)

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


if __name__ == "__main__":
    unittest.main()
