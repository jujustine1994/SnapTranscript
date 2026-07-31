"""時間字串解析與音訊分段計算（純函式，無外部相依）。"""

import re


def hms_to_seconds(hms: str) -> int:
    """HH:MM:SS → 秒數"""
    parts = hms.strip().split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + int(s)
    if len(parts) == 2:
        m, s = parts
        return int(m) * 60 + int(s)
    return int(parts[0])


def seconds_to_hms(seconds: float) -> str:
    """秒數 → HH:MM:SS"""
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def parse_custom_cut_points(text: str) -> list[int]:
    """
    解析自訂切割點文字（每行一個 HH:MM:SS），回傳排序後的秒數清單。
    格式錯誤時拋出 ValueError。
    """
    pattern = re.compile(r"^\d{1,2}:\d{2}:\d{2}$")
    points = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if not pattern.match(line):
            raise ValueError(f"格式錯誤：「{line}」，請使用 HH:MM:SS 格式（例如 00:22:30）")
        points.append(hms_to_seconds(line))
    return sorted(set(points))


def parse_range(start_text: str, end_text: str) -> tuple[int, int]:
    """
    解析擷取範圍的起始/結束時間（HH:MM:SS），回傳 (start_sec, end_sec)。
    格式錯誤或起始 >= 結束時拋出 ValueError。
    """
    pattern = re.compile(r"^\d{1,2}:\d{2}:\d{2}$")
    start_text = start_text.strip()
    end_text = end_text.strip()
    if not start_text or not end_text:
        raise ValueError("請輸入起始與結束時間")
    if not pattern.match(start_text):
        raise ValueError(f"格式錯誤：「{start_text}」，請使用 HH:MM:SS 格式（例如 00:10:00）")
    if not pattern.match(end_text):
        raise ValueError(f"格式錯誤：「{end_text}」，請使用 HH:MM:SS 格式（例如 00:45:00）")
    start_sec = hms_to_seconds(start_text)
    end_sec = hms_to_seconds(end_text)
    if start_sec >= end_sec:
        raise ValueError("起始時間必須早於結束時間")
    return start_sec, end_sec


def build_segments(cut_points: list[int], range_start: int, range_end: int) -> list[tuple[int, int]]:
    """從切割點建立 (start_sec, end_sec) 清單，限制在 [range_start, range_end] 範圍內"""
    boundaries = [range_start] + cut_points + [range_end]
    segments = []
    for i in range(len(boundaries) - 1):
        start = boundaries[i]
        end = min(boundaries[i + 1], range_end)
        if end > start:
            segments.append((start, end))
    return segments
