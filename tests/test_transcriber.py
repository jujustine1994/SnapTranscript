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
