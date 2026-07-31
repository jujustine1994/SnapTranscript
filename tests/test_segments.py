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
