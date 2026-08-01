import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import segments

HALF_HOUR = 30 * 60


class TestPlanSegments(unittest.TestCase):
    """自動切點 + 擷取範圍夾擠的邏輯。2026-08-01 前這段卡在 ui.py 的執行緒
    函式裡，沒有任何測試守著。"""

    def test_auto_short_audio_single_segment(self):
        segs, start, end = segments.plan_segments(600.0)
        self.assertEqual(segs, [(0, 600)])
        self.assertEqual((start, end), (0, 600))

    def test_auto_cuts_every_chunk(self):
        segs, _, _ = segments.plan_segments(2 * HALF_HOUR)
        self.assertEqual(segs, [(0, 1800), (1800, 3600)])

    def test_auto_exactly_one_chunk_is_one_segment(self):
        segs, _, _ = segments.plan_segments(float(HALF_HOUR))
        self.assertEqual(segs, [(0, 1800)])

    def test_auto_short_tail_merges_into_previous(self):
        # 30 分 05 秒：不合併的話會多出一個 5 秒的段落，白花一次 API 呼叫
        segs, _, _ = segments.plan_segments(HALF_HOUR + 5.0)
        self.assertEqual(segs, [(0, 1805)])

    def test_auto_tail_at_threshold_stays_separate(self):
        segs, _, _ = segments.plan_segments(HALF_HOUR + config.MIN_SEGMENT_SECONDS)
        self.assertEqual(segs, [(0, 1800), (1800, 1800 + config.MIN_SEGMENT_SECONDS)])

    def test_min_segment_zero_disables_merge(self):
        segs, _, _ = segments.plan_segments(HALF_HOUR + 5.0, min_segment_seconds=0)
        self.assertEqual(segs, [(0, 1800), (1800, 1805)])

    def test_duration_is_truncated_not_rounded(self):
        # ffprobe 回傳的是浮點秒數；切割點必須是整數
        segs, _, end = segments.plan_segments(600.9)
        self.assertEqual(segs, [(0, 600)])
        self.assertEqual(end, 600)

    def test_long_audio_three_hours(self):
        segs, _, _ = segments.plan_segments(3 * 3600.0)
        self.assertEqual(len(segs), 6)
        self.assertEqual(segs[0], (0, 1800))
        self.assertEqual(segs[-1], (9000, 10800))

    # ---- 擷取範圍 ----
    def test_range_offsets_auto_cut_points(self):
        # 10:00 → 1:20:00，自動切點應從 40:00、1:10:00 落下（相對範圍起點）
        segs, start, end = segments.plan_segments(3 * 3600.0, range_bounds=(600, 4800))
        self.assertEqual(segs, [(600, 2400), (2400, 4200), (4200, 4800)])
        self.assertEqual((start, end), (600, 4800))

    def test_range_end_clamped_to_duration(self):
        segs, start, end = segments.plan_segments(1000.0, range_bounds=(100, 99999))
        self.assertEqual(segs, [(100, 1000)])
        self.assertEqual((start, end), (100, 1000))

    def test_range_start_beyond_duration_raises(self):
        with self.assertRaises(ValueError):
            segments.plan_segments(600.0, range_bounds=(700, 900))

    def test_range_start_equal_duration_raises(self):
        with self.assertRaises(ValueError):
            segments.plan_segments(600.0, range_bounds=(600, 900))

    # ---- 自訂切割點 ----
    def test_custom_points_inside_range_only(self):
        segs, _, _ = segments.plan_segments(
            3600.0, cut_points=[300, 1200, 3000], range_bounds=(600, 2400)
        )
        # 300 在範圍外、3000 也在範圍外，只有 1200 生效
        self.assertEqual(segs, [(600, 1200), (1200, 2400)])

    def test_custom_point_on_boundary_ignored(self):
        # 等於範圍端點的切點會切出長度 0 的段落，必須濾掉
        segs, _, _ = segments.plan_segments(
            3600.0, cut_points=[600, 2400], range_bounds=(600, 2400)
        )
        self.assertEqual(segs, [(600, 2400)])

    def test_custom_points_no_tail_merge(self):
        # 自訂切點是使用者指定的，即使尾巴只有 5 秒也照切
        segs, _, _ = segments.plan_segments(1805.0, cut_points=[1800])
        self.assertEqual(segs, [(0, 1800), (1800, 1805)])

    def test_custom_empty_list_is_single_segment(self):
        segs, _, _ = segments.plan_segments(3600.0, cut_points=[])
        self.assertEqual(segs, [(0, 3600)])


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
