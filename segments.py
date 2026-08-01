"""時間字串解析與音訊分段計算（純函式，只相依 config 的常數）。"""

import re

import config

# HH:MM:SS 格式（小時可 1~2 位）。切割點與擷取範圍共用同一份，
# 兩邊各留一份的話改格式時容易只改到一邊。
TIME_PATTERN = re.compile(r"^\d{1,2}:\d{2}:\d{2}$")


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
    points = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if not TIME_PATTERN.match(line):
            raise ValueError(f"格式錯誤：「{line}」，請使用 HH:MM:SS 格式（例如 00:22:30）")
        points.append(hms_to_seconds(line))
    return sorted(set(points))


def parse_range(start_text: str, end_text: str) -> tuple[int, int]:
    """
    解析擷取範圍的起始/結束時間（HH:MM:SS），回傳 (start_sec, end_sec)。
    格式錯誤或起始 >= 結束時拋出 ValueError。
    """
    start_text = start_text.strip()
    end_text = end_text.strip()
    if not start_text or not end_text:
        raise ValueError("請輸入起始與結束時間")
    if not TIME_PATTERN.match(start_text):
        raise ValueError(f"格式錯誤：「{start_text}」，請使用 HH:MM:SS 格式（例如 00:10:00）")
    if not TIME_PATTERN.match(end_text):
        raise ValueError(f"格式錯誤：「{end_text}」，請使用 HH:MM:SS 格式（例如 00:45:00）")
    start_sec = hms_to_seconds(start_text)
    end_sec = hms_to_seconds(end_text)
    if start_sec >= end_sec:
        raise ValueError("起始時間必須早於結束時間")
    return start_sec, end_sec


def parse_min_segment_minutes(
    text: str, chunk_seconds: int = config.DEFAULT_CHUNK_SECONDS
) -> int:
    """把 UI 的「尾巴不足 N 分鐘併入前段」輸入轉成秒數。0 代表關閉合併。

    上限必須小於 `chunk_seconds`，這不是隨便訂的：`plan_segments()` 合併尾巴的
    做法是撤掉「最後一刀」，只撤一刀。門檻若 >= 一段的長度，撤掉後的那段會變成
    兩倍長（30 分的設定會切出 60 分的段落），輸出 token 可能撞上 65,536 上限
    而被靜默截斷——逐字稿會少一截且沒有任何錯誤訊息。
    """
    text = text.strip()
    if not text:
        raise ValueError("請輸入尾巴合併門檻（分鐘），填 0 代表不合併")
    try:
        minutes = int(text)
    except ValueError:
        raise ValueError(
            f"格式錯誤：「{text}」，請輸入整數分鐘（例如 5），填 0 代表不合併"
        ) from None
    if minutes < 0:
        raise ValueError("尾巴合併門檻不能是負數，填 0 代表不合併")
    limit = chunk_seconds // 60
    if minutes >= limit:
        raise ValueError(
            f"尾巴合併門檻必須小於切割長度（{limit} 分鐘），"
            f"否則合併後的段落會長到可能超出 Gemini 的輸出上限"
        )
    return minutes * 60


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


def plan_segments(
    total_duration: float,
    cut_points: list[int] | None = None,
    range_bounds: tuple[int, int] | None = None,
    chunk_seconds: int = config.DEFAULT_CHUNK_SECONDS,
    min_segment_seconds: int = config.MIN_SEGMENT_SECONDS,
) -> tuple[list[tuple[int, int]], int, int]:
    """決定整個任務要跑哪些段落。

    回傳 `(segment_list, range_start, range_end)`——後兩者是夾擠到音訊實際
    長度之後的有效範圍，UI 拿去顯示「擷取範圍：X → Y」。

    - `cut_points=None` 代表自動模式：從 `range_start` 起每 `chunk_seconds` 一刀，
      不足 `min_segment_seconds` 的尾巴併回前一段。
    - `cut_points` 有值代表自訂模式：只有落在範圍「內部」的切點才生效，
      等於範圍端點的切點會切出長度 0 的段落，沒有意義。自訂切點不套用尾巴合併，
      使用者指定的位置就照切。
    - `range_bounds=None` 代表整段處理。

    這段邏輯 2026-08-01 從 `ui.py._worker` 抽出來——原本卡在 UI 執行緒函式裡，
    要測就得起 tkinter，導致自動切點與範圍夾擠一直沒有測試守著。
    """
    duration = int(total_duration)
    if range_bounds is not None:
        range_start, range_end = range_bounds
        if range_start >= duration:
            raise ValueError("擷取範圍超出音訊總長度，請重新設定")
        range_end = min(range_end, duration)
    else:
        range_start, range_end = 0, duration

    if cut_points is None:
        points = list(range(range_start + chunk_seconds, range_end, chunk_seconds))
        # 尾巴太短就把最後一刀撤掉，讓它併回前一段（見 config.MIN_SEGMENT_SECONDS）
        if points and range_end - points[-1] < min_segment_seconds:
            points.pop()
    else:
        points = [p for p in cut_points if range_start < p < range_end]

    return build_segments(points, range_start, range_end), range_start, range_end
