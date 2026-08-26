import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import config
import transcriber


# ---- 假的 Gemini client ----
# transcribe_segment 的 client 是參數傳進去的，所以整條路徑都能離線測：
# 不需要網路、API Key，也不會吃掉 Gemini 額度。
class FakeState:
    def __init__(self, name):
        self.name = name


class FakeFile:
    def __init__(self, state, name="files/abc123"):
        self.state = FakeState(state)
        self.name = name


class FakeFiles:
    """states 是每次回傳的檔案狀態序列：第一個給 upload，之後每個給 get。"""

    def __init__(self, states):
        self._states = list(states)
        self.uploaded = []
        self.deleted = []
        self.get_calls = 0

    def upload(self, file):
        self.uploaded.append(file)
        return FakeFile(self._states[0])

    def get(self, name):
        self.get_calls += 1
        return FakeFile(self._states[min(self.get_calls, len(self._states) - 1)])

    def delete(self, name):
        self.deleted.append(name)


class FakeResponse:
    def __init__(self, text, finish_reason=None):
        self.text = text
        self.candidates = (
            [type("C", (), {"finish_reason": finish_reason})()] if finish_reason else []
        )


class FakeModels:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def generate_content(self, model, contents):
        self.calls.append(model)
        if self.error:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, states=("ACTIVE",), response=None, error=None):
        self.files = FakeFiles(states)
        self.models = FakeModels(response, error)


class TestTranscribeSegment(unittest.TestCase):
    def setUp(self):
        self.slept = []

    def _sleep(self, sec):
        self.slept.append(sec)

    def test_active_returns_stripped_text(self):
        client = FakeClient(response=FakeResponse("  逐字稿內容  "))
        result = transcriber.transcribe_segment("seg.mp3", client, sleep_fn=self._sleep)
        self.assertEqual(result, "逐字稿內容")
        self.assertEqual(client.files.uploaded, ["seg.mp3"])
        self.assertEqual(client.models.calls, [config.MODEL_NAME])
        self.assertEqual(self.slept, [])  # ACTIVE 直接過，不該等

    def test_processing_polls_until_active(self):
        client = FakeClient(
            states=("PROCESSING", "PROCESSING", "ACTIVE"),
            response=FakeResponse("好了"),
        )
        result = transcriber.transcribe_segment("seg.mp3", client, sleep_fn=self._sleep)
        self.assertEqual(result, "好了")
        self.assertEqual(client.files.get_calls, 2)
        self.assertEqual(self.slept, [config.FILE_UPLOAD_POLL_SECONDS] * 2)

    def test_non_active_state_raises(self):
        client = FakeClient(states=("FAILED",), response=FakeResponse("不該用到"))
        with self.assertRaises(Exception) as ctx:
            transcriber.transcribe_segment("seg.mp3", client, sleep_fn=self._sleep)
        self.assertIn("FAILED", str(ctx.exception))
        self.assertEqual(client.models.calls, [])  # 沒進到 ACTIVE 就不該呼叫模型

    def test_generate_failure_still_deletes_uploaded_file(self):
        client = FakeClient(error=RuntimeError("503 UNAVAILABLE"))
        with self.assertRaises(RuntimeError):
            transcriber.transcribe_segment("seg.mp3", client, sleep_fn=self._sleep)
        # 不刪的話失敗重試會在 Gemini 端一直堆檔案
        self.assertEqual(client.files.deleted, ["files/abc123"])

    def test_success_deletes_uploaded_file(self):
        client = FakeClient(response=FakeResponse("內容"))
        transcriber.transcribe_segment("seg.mp3", client, sleep_fn=self._sleep)
        self.assertEqual(client.files.deleted, ["files/abc123"])

    def test_blank_text_raises_with_finish_reason(self):
        client = FakeClient(
            response=FakeResponse(None, finish_reason="MALFORMED_RESPONSE")
        )
        with self.assertRaises(Exception) as ctx:
            transcriber.transcribe_segment("seg.mp3", client, sleep_fn=self._sleep)
        msg = str(ctx.exception)
        self.assertIn("Gemini 回傳空白結果", msg)
        self.assertIn("MALFORMED_RESPONSE", msg)
        # 空白結果拋出的訊息必須讓 classify_error 認得，否則不會走重試流程
        self.assertEqual(
            transcriber.classify_error(ctx.exception), ("Gemini 回傳空白結果", "空白結果")
        )
        self.assertEqual(client.files.deleted, ["files/abc123"])

    def test_blank_text_without_candidates_still_raises(self):
        client = FakeClient(response=FakeResponse(None))
        with self.assertRaises(Exception) as ctx:
            transcriber.transcribe_segment("seg.mp3", client, sleep_fn=self._sleep)
        self.assertIn("Gemini 回傳空白結果", str(ctx.exception))


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
        # 訊息同時含 429 與 UNAVAILABLE：quota 判斷若沒排在 503 之前，這裡會回傳 503 tuple
        self.assertIsNone(
            transcriber.classify_error(Exception("429 RESOURCE_EXHAUSTED: model UNAVAILABLE"))
        )


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
