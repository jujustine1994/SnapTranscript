import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import audio


def fake_run(stdout=b"", returncode=0):
    """做一個假的 subprocess.run 回傳值，測試就不需要真的 ffmpeg。"""
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout)


class TestGetAudioDuration(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.audio_path = os.path.join(self.tmpdir.name, "meeting.mp3")
        with open(self.audio_path, "wb") as f:
            f.write(b"fake")

    def test_parses_duration(self):
        with patch.object(audio.subprocess, "run", return_value=fake_run(b"9015.024000\n")):
            self.assertAlmostEqual(audio.get_audio_duration(self.audio_path), 9015.024)

    def test_missing_file_raises_readable_error(self):
        """原本會是 `could not convert string to float: b'...'`，看不出要做什麼。"""
        missing = os.path.join(self.tmpdir.name, "gone.mp3")
        with self.assertRaises(FileNotFoundError) as ctx:
            audio.get_audio_duration(missing)
        msg = str(ctx.exception)
        self.assertIn("找不到音訊檔案", msg)
        self.assertNotIn("could not convert", msg)

    def test_corrupt_file_raises_readable_error(self):
        # ffprobe 對非音訊檔會回傳空 stdout（錯誤走 stderr）
        with patch.object(audio.subprocess, "run", return_value=fake_run(b"", returncode=1)):
            with self.assertRaises(RuntimeError) as ctx:
                audio.get_audio_duration(self.audio_path)
        msg = str(ctx.exception)
        self.assertIn("無法讀取音訊長度", msg)
        self.assertNotIn("could not convert", msg)

    def test_ffprobe_not_installed_raises_readable_error(self):
        with patch.object(audio.subprocess, "run", side_effect=FileNotFoundError()):
            with self.assertRaises(RuntimeError) as ctx:
                audio.get_audio_duration(self.audio_path)
        self.assertIn("ffmpeg", str(ctx.exception))

    def test_stderr_not_merged_into_stdout(self):
        """stderr 併進 stdout 的話，ffprobe 的警告會混進要解析的數字裡。"""
        captured = {}

        def _run(cmd, **kwargs):
            captured.update(kwargs)
            return fake_run(b"120.0")

        with patch.object(audio.subprocess, "run", side_effect=_run):
            audio.get_audio_duration(self.audio_path)
        self.assertEqual(captured["stderr"], subprocess.PIPE)
        self.assertNotEqual(captured["stderr"], subprocess.STDOUT)


class TestCutAudioSegment(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.src = os.path.join(self.tmpdir.name, "meeting.mp3")
        self.out = os.path.join(self.tmpdir.name, "_temp_seg_0.mp3")
        with open(self.src, "wb") as f:
            f.write(b"fake source")

    def test_copy_success_keeps_output(self):
        def _run(cmd, **kwargs):
            with open(self.out, "wb") as f:
                f.write(b"segment")
            return fake_run(returncode=0)

        with patch.object(audio.subprocess, "run", side_effect=_run) as m:
            audio.cut_audio_segment(self.src, 0, 1800, self.out)
        self.assertTrue(os.path.exists(self.out))
        self.assertEqual(m.call_count, 1)   # copy 成功就不該再跑重新編碼

    def test_falls_back_to_reencode_when_copy_fails(self):
        calls = []

        def _run(cmd, **kwargs):
            calls.append(cmd)
            if "copy" in cmd:
                return fake_run(returncode=1)
            with open(self.out, "wb") as f:
                f.write(b"segment")
            return fake_run(returncode=0)

        with patch.object(audio.subprocess, "run", side_effect=_run):
            audio.cut_audio_segment(self.src, 0, 1800, self.out)
        self.assertEqual(len(calls), 2)
        self.assertIn("libmp3lame", calls[1])
        self.assertTrue(os.path.exists(self.out))

    def test_partial_output_removed_when_both_attempts_fail(self):
        """ffmpeg 失敗仍可能留下 0 byte 或半截的檔案。留著的話 job 的存在性
        檢查會誤判切割成功，接著把壞掉的音訊上傳給 Gemini。"""
        def _run(cmd, **kwargs):
            with open(self.out, "wb") as f:
                f.write(b"")        # 半截／空檔
            return fake_run(returncode=1)

        with patch.object(audio.subprocess, "run", side_effect=_run):
            audio.cut_audio_segment(self.src, 0, 1800, self.out)
        self.assertFalse(
            os.path.exists(self.out), "兩次都失敗時不該留下殘檔"
        )

    def test_no_crash_when_failure_leaves_no_file(self):
        with patch.object(audio.subprocess, "run", return_value=fake_run(returncode=1)):
            audio.cut_audio_segment(self.src, 0, 1800, self.out)
        self.assertFalse(os.path.exists(self.out))


if __name__ == "__main__":
    unittest.main()
