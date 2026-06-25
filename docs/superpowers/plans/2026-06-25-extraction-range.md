# 擷取範圍（部分音訊轉錄）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓使用者可以勾選「只處理音訊的一部分」，指定起始/結束時間，只轉錄該範圍，範圍外完全不切割、不上傳。

**Architecture:** 在 `main.py` 單檔 tkinter app 中新增一個「擷取範圍」UI 區塊與對應的純邏輯函式（`parse_range`、`build_segments` 改為接受範圍邊界）。範圍是切割設定的篩選前提：自動/自訂切割只在範圍內運作。不勾選時行為與現況完全一致。

**Tech Stack:** Python 3.13、tkinter、既有 `main.py`（無測試框架已安裝，用標準函式庫 `unittest` 測試純邏輯函式，不引入新依賴）。

## Global Constraints

- 不可修改 `MODEL_NAME = "gemini-flash-latest"`（[[feedback_model_name]]，使用者明確要求不要動）。
- 切割點輸入格式維持 `HH:MM:SS`，與現有 `parse_custom_cut_points` 一致的錯誤訊息風格。
- 不勾選「擷取範圍」時，所有行為必須與目前版本完全一致（回歸測試重點）。
- 不引入新的 pip 依賴（沿用標準函式庫 `unittest`）。

---

## File Structure

- Modify: `main.py` — 唯一程式碼檔案，本次新增：
  - `build_segments()` 簽名改為 `(cut_points, range_start, range_end)`
  - 新函式 `parse_range(start_text, end_text) -> tuple[int, int]`
  - `SnapTranscriptApp._build_ui()` 新增「擷取範圍」`LabelFrame`
  - 新增 `SnapTranscriptApp._toggle_range_mode()`
  - `SnapTranscriptApp._start()` 新增範圍驗證與傳遞
  - `SnapTranscriptApp._worker()` 新增範圍套用邏輯
- Create: `tests/test_main.py` — 純邏輯函式（`build_segments`、`parse_range`）的單元測試，用 `python -m unittest tests.test_main` 執行。

---

### Task 1: `build_segments` 改為範圍邊界 + 新增 `parse_range`

**Files:**
- Modify: `main.py:87-96`（`build_segments`）
- Modify: `main.py:599-608`（`_worker` 內兩處呼叫 `build_segments` 的地方）
- Create: `tests/test_main.py`

**Interfaces:**
- Produces: `build_segments(cut_points: list[int], range_start: int, range_end: int) -> list[tuple[int, int]]`
- Produces: `parse_range(start_text: str, end_text: str) -> tuple[int, int]`（格式錯誤或起始 ≥ 結束時拋 `ValueError`）

- [ ] **Step 1: 建立測試檔，先寫會失敗的測試**

建立 `tests/test_main.py`：

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main


class TestBuildSegments(unittest.TestCase):
    def test_no_cut_points_full_range(self):
        segments = main.build_segments([], 0, 100)
        self.assertEqual(segments, [(0, 100)])

    def test_cut_points_within_full_range(self):
        segments = main.build_segments([30, 60], 0, 100)
        self.assertEqual(segments, [(0, 30), (30, 60), (60, 100)])

    def test_range_offset(self):
        # 範圍 10:00~50:00（600~3000 秒），自動切點在 30:00（1800 秒）
        segments = main.build_segments([1800], 600, 3000)
        self.assertEqual(segments, [(600, 1800), (1800, 3000)])

    def test_no_cut_points_with_range_offset(self):
        segments = main.build_segments([], 600, 1800)
        self.assertEqual(segments, [(600, 1800)])


class TestParseRange(unittest.TestCase):
    def test_valid_range(self):
        self.assertEqual(main.parse_range("00:10:00", "00:45:00"), (600, 2700))

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            main.parse_range("", "00:45:00")

    def test_bad_format_raises(self):
        with self.assertRaises(ValueError):
            main.parse_range("10:00", "00:45:00")

    def test_start_after_end_raises(self):
        with self.assertRaises(ValueError):
            main.parse_range("00:45:00", "00:10:00")

    def test_start_equal_end_raises(self):
        with self.assertRaises(ValueError):
            main.parse_range("00:10:00", "00:10:00")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 執行測試，確認失敗**

Run: `venv\Scripts\python.exe -m unittest tests.test_main -v`
Expected: `AttributeError: module 'main' has no attribute 'parse_range'`（以及 `build_segments` 因簽名不符而 `TypeError`）

- [ ] **Step 3: 修改 `build_segments` 簽名**

把 `main.py:87-96` 的：

```python
def build_segments(cut_points: list[int], total_duration: float) -> list[tuple[int, int]]:
    """從切割點建立 (start_sec, end_sec) 清單"""
    boundaries = [0] + cut_points + [int(total_duration)]
    segments = []
    for i in range(len(boundaries) - 1):
        start = boundaries[i]
        end = min(boundaries[i + 1], int(total_duration))
        if end > start:
            segments.append((start, end))
    return segments
```

改為：

```python
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
```

- [ ] **Step 4: 新增 `parse_range`**

在 `parse_custom_cut_points`（`main.py:70-84`）之後加入：

```python
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
```

- [ ] **Step 5: 更新 `_worker` 內的呼叫端，維持目前行為（範圍 = 整段音訊）**

把 `main.py:599-608` 的：

```python
            # 建立分段清單
            if cut_points is None:
                # 自動模式：每 30 分鐘一刀
                auto_points = list(
                    range(DEFAULT_CHUNK_SECONDS, int(total_duration), DEFAULT_CHUNK_SECONDS)
                )
                segments = build_segments(auto_points, total_duration)
            else:
                valid_points = [p for p in cut_points if 0 < p < total_duration]
                segments = build_segments(valid_points, total_duration)
```

改為：

```python
            # 建立分段清單
            range_start, range_end = 0, int(total_duration)
            if cut_points is None:
                # 自動模式：每 30 分鐘一刀
                auto_points = list(
                    range(range_start + DEFAULT_CHUNK_SECONDS, range_end, DEFAULT_CHUNK_SECONDS)
                )
                segments = build_segments(auto_points, range_start, range_end)
            else:
                valid_points = [p for p in cut_points if range_start < p < range_end]
                segments = build_segments(valid_points, range_start, range_end)
```

- [ ] **Step 6: 執行測試，確認通過**

Run: `venv\Scripts\python.exe -m unittest tests.test_main -v`
Expected: 9 個測試全部 `OK`

- [ ] **Step 7: 手動確認既有行為沒壞**

Run: `venv\Scripts\python.exe main.py`
用任意本地音訊檔，不勾選任何新功能（此時還沒新增 UI），跑一次自動模式轉錄，確認跟修改前行為一致（能正常切割、上傳、產生逐字稿）。

- [ ] **Step 8: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "refactor: build_segments 改為接受範圍邊界，新增 parse_range"
```

---

### Task 2: 新增「擷取範圍」UI 區塊

**Files:**
- Modify: `main.py`（`__init__`、`_build_ui`、`_toggle_cut_mode` 旁新增 `_toggle_range_mode`、`_update_btn_label`）

**Interfaces:**
- Consumes: 無新依賴於 Task 1 的函式（UI 階段先不接邏輯，Task 3 才接）
- Produces：
  - `self.range_enabled: tk.BooleanVar`
  - `self.range_start_var: tk.StringVar`
  - `self.range_end_var: tk.StringVar`
  - `self.frame_range: ttk.LabelFrame`（給 Task 3 與 `_update_btn_label` 的停用清單使用）

- [ ] **Step 1: 在 `__init__` 新增變數**

在 `main.py:213-219`（`self.source_mode = tk.StringVar(value="local")` 等變數宣告區塊）後面加入：

```python
        self.range_enabled = tk.BooleanVar(value=False)
        self.range_start_var = tk.StringVar()
        self.range_end_var = tk.StringVar()
```

- [ ] **Step 2: 在 `_build_ui` 插入「擷取範圍」區塊，並把後續區塊的 row 往後挪一格**

目前 `main.py:226-296` 一帶的 grid row 配置：`frame_source`=row0、`frame_cut`=row1、`frame_api`=row2、`frame_start`=row3、`frame_progress`=row4、`frame_output`=row5。

在 `main.py:293`（`# 切割設定` 註解之前，也就是 `frame_source` 整段結束之後）插入：

```python
        # 擷取範圍
        self.frame_range = ttk.LabelFrame(self.root, text=" 擷取範圍 ", padding=8)
        self.frame_range.grid(row=1, column=0, sticky="ew", **pad)

        ttk.Checkbutton(
            self.frame_range, text="只處理音訊的一部分",
            variable=self.range_enabled, command=self._toggle_range_mode,
        ).grid(row=0, column=0, sticky="w")

        self.frame_range_inputs = ttk.Frame(self.frame_range)
        self.frame_range_inputs.grid(row=1, column=0, sticky="w", padx=(20, 0), pady=(6, 0))
        ttk.Label(self.frame_range_inputs, text="起始時間：").grid(row=0, column=0, sticky="w")
        ttk.Entry(self.frame_range_inputs, textvariable=self.range_start_var, width=10).grid(
            row=0, column=1, padx=(0, 16)
        )
        ttk.Label(self.frame_range_inputs, text="結束時間：").grid(row=0, column=2, sticky="w")
        ttk.Entry(self.frame_range_inputs, textvariable=self.range_end_var, width=10).grid(
            row=0, column=3
        )
        ttk.Label(self.frame_range_inputs, text="（HH:MM:SS，例如 00:10:00）").grid(
            row=1, column=0, columnspan=4, sticky="w", pady=(2, 0)
        )
        self.frame_range_inputs.grid_remove()  # 預設隱藏

        tk.Label(
            self.frame_range,
            text="⚠️ 下方切割點為原始音訊的絕對時間，需落在此範圍內才會生效",
            foreground="gray", font=("", 8),
        ).grid(row=2, column=0, sticky="w", pady=(6, 0))
```

接著把原本 `main.py:294-381` 區段裡這幾行的 `row=` 數值各 `+1`：
- `main.py:295` `self.frame_cut.grid(row=1, ...)` → `row=2`
- `main.py:320` `self.frame_api.grid(row=2, ...)` → `row=3`
- `main.py:341` `frame_start.grid(row=3, ...)` → `row=4`
- `main.py:361` `frame_progress.grid(row=4, ...)` → `row=5`
- `main.py:374` `frame_output.grid(row=5, ...)` → `row=6`

- [ ] **Step 3: 新增 `_toggle_range_mode`**

在 `_toggle_cut_mode`（`main.py:430-435`）後面加入：

```python
    def _toggle_range_mode(self):
        if self.range_enabled.get():
            self.frame_range_inputs.grid()
        else:
            self.frame_range_inputs.grid_remove()
        self.root.update_idletasks()
```

- [ ] **Step 4: 把「擷取範圍」區塊加入「只下載音訊」模式的停用清單**

把 `main.py:459-470` 的 `_update_btn_label`：

```python
    def _update_btn_label(self):
        is_download_only = (
            self.source_mode.get() == "youtube" and self.yt_action.get() == "download_only"
        )
        if is_download_only:
            self.btn_start.config(text="▶  開始下載")
            self._set_widgets_state(self.frame_cut, "disabled")
            self._set_widgets_state(self.frame_api, "disabled")
        else:
            self.btn_start.config(text="▶  開始轉錄")
            self._set_widgets_state(self.frame_cut, "normal")
            self._set_widgets_state(self.frame_api, "normal")
```

改為：

```python
    def _update_btn_label(self):
        is_download_only = (
            self.source_mode.get() == "youtube" and self.yt_action.get() == "download_only"
        )
        if is_download_only:
            self.btn_start.config(text="▶  開始下載")
            self._set_widgets_state(self.frame_range, "disabled")
            self._set_widgets_state(self.frame_cut, "disabled")
            self._set_widgets_state(self.frame_api, "disabled")
        else:
            self.btn_start.config(text="▶  開始轉錄")
            self._set_widgets_state(self.frame_range, "normal")
            self._set_widgets_state(self.frame_cut, "normal")
            self._set_widgets_state(self.frame_api, "normal")
```

- [ ] **Step 5: 手動驗證 UI**

Run: `venv\Scripts\python.exe main.py`

確認：
1. 視窗開啟時「擷取範圍」勾選框預設不勾，起始/結束輸入框不顯示。
2. 勾選後出現起始/結束輸入框；取消勾選後消失。
3. 切到「YouTube 下載」+「只下載音訊（不需 API Key）」時，「擷取範圍」整塊變成灰底唯讀，跟「切割設定」「Gemini API Key」一致。
4. 整體版面排列正常（沒有元件互相重疊或被截斷）。

- [ ] **Step 6: Commit**

```bash
git add main.py
git commit -m "feat: 新增「擷取範圍」UI 區塊"
```

---

### Task 3: `_start()` 驗證 + `_worker()` 套用範圍邏輯

**Files:**
- Modify: `main.py:504-561`（`_start`）
- Modify: `main.py:563-609`（`_worker` 簽名與分段邏輯）

**Interfaces:**
- Consumes: `parse_range(start_text, end_text) -> tuple[int, int]`（Task 1）、`build_segments(cut_points, range_start, range_end)`（Task 1）、`self.range_enabled` / `self.range_start_var` / `self.range_end_var`（Task 2）
- Produces: `_worker(self, source_info, cut_points, client, range_bounds)`，`range_bounds` 是 `tuple[int, int] | None`

- [ ] **Step 1: 在 `_start()` 解析並驗證範圍**

把 `main.py:528-535`：

```python
        # 解析自訂切割點（只下載模式不需要）
        cut_points = None
        if not download_only and self.cut_mode.get() == "custom":
            try:
                cut_points = parse_custom_cut_points(self.cut_text.get("1.0", "end"))
            except ValueError as e:
                messagebox.showerror("格式錯誤", str(e))
                return
```

改為：

```python
        # 解析自訂切割點（只下載模式不需要）
        cut_points = None
        if not download_only and self.cut_mode.get() == "custom":
            try:
                cut_points = parse_custom_cut_points(self.cut_text.get("1.0", "end"))
            except ValueError as e:
                messagebox.showerror("格式錯誤", str(e))
                return

        # 解析擷取範圍（只下載模式不需要）
        range_bounds = None
        if not download_only and self.range_enabled.get():
            try:
                range_bounds = parse_range(
                    self.range_start_var.get(), self.range_end_var.get()
                )
            except ValueError as e:
                messagebox.showerror("格式錯誤", str(e))
                return
```

- [ ] **Step 2: 把 `range_bounds` 傳入背景執行緒**

把 `main.py:558-561`：

```python
        t = threading.Thread(
            target=self._worker, args=(source_info, cut_points, client), daemon=True
        )
        t.start()
```

改為：

```python
        t = threading.Thread(
            target=self._worker, args=(source_info, cut_points, client, range_bounds), daemon=True
        )
        t.start()
```

- [ ] **Step 3: 更新 `_worker` 簽名與分段邏輯**

把 `main.py:563`：

```python
    def _worker(self, source_info: dict, cut_points: list[int] | None, client: genai.Client):
```

改為：

```python
    def _worker(
        self,
        source_info: dict,
        cut_points: list[int] | None,
        client: genai.Client,
        range_bounds: tuple[int, int] | None,
    ):
```

把 `main.py:599-608`（Task 1 Step 5 已改過的版本）：

```python
            # 建立分段清單
            range_start, range_end = 0, int(total_duration)
            if cut_points is None:
                # 自動模式：每 30 分鐘一刀
                auto_points = list(
                    range(range_start + DEFAULT_CHUNK_SECONDS, range_end, DEFAULT_CHUNK_SECONDS)
                )
                segments = build_segments(auto_points, range_start, range_end)
            else:
                valid_points = [p for p in cut_points if range_start < p < range_end]
                segments = build_segments(valid_points, range_start, range_end)
```

改為：

```python
            # 建立分段清單
            if range_bounds is not None:
                range_start, range_end = range_bounds
                if range_start >= int(total_duration):
                    raise Exception("擷取範圍超出音訊總長度，請重新設定")
                range_end = min(range_end, int(total_duration))
                self._log(
                    f"擷取範圍：{seconds_to_hms(range_start)} → {seconds_to_hms(range_end)}"
                )
            else:
                range_start, range_end = 0, int(total_duration)

            if cut_points is None:
                # 自動模式：每 30 分鐘一刀
                auto_points = list(
                    range(range_start + DEFAULT_CHUNK_SECONDS, range_end, DEFAULT_CHUNK_SECONDS)
                )
                segments = build_segments(auto_points, range_start, range_end)
            else:
                valid_points = [p for p in cut_points if range_start < p < range_end]
                segments = build_segments(valid_points, range_start, range_end)
```

- [ ] **Step 4: 執行既有單元測試，確認沒有迴歸**

Run: `venv\Scripts\python.exe -m unittest tests.test_main -v`
Expected: 9 個測試全部 `OK`（這個 Task 沒改 `build_segments`/`parse_range` 本身，純粹是接線，測試應維持綠燈）

- [ ] **Step 5: 手動驗證完整流程**

Run: `venv\Scripts\python.exe main.py`

用一個已知總長度的本地音訊檔（例如總長 01:10:11，README 範例），分別測試：

1. **不勾選範圍**：自動模式跑一次，確認跟修改前行為一致（整段轉錄，切點同舊版）。
2. **勾選範圍 + 自動切割**：設定起始 `00:10:00`、結束 `00:50:00`，確認 log 印出「擷取範圍：00:10:00 → 00:50:00」，且自動切點落在 `00:40:00`（= 10:00 + 30 分），共 2 段（10:00~40:00、40:00~50:00），範圍外完全沒有切割/上傳紀錄。
3. **勾選範圍 + 自訂切割**：自訂切割點輸入包含範圍外的時間點（如 `01:00:00`），確認該點被忽略，不會產生多餘分段。
4. **錯誤情境**：結束時間超過音訊總長度、起始時間 ≥ 音訊總長度、起始 ≥ 結束、格式錯誤，各驗證對應的錯誤訊息會跳出且不會開始處理。

- [ ] **Step 6: Commit**

```bash
git add main.py
git commit -m "feat: 擷取範圍套用至切割邏輯，串接 UI 與分段流程"
```

---

## Self-Review Notes

- **Spec coverage**：UI 區塊（Task 2）、驗證規則（Task 3 Step 1）、邏輯整合（Task 1 + Task 3）、不在範圍內的事項（單段範圍、YouTube 模式一視同仁、download_only 停用——Task 2 Step 4）、測試重點（Task 1 單元測試 + Task 3 手動驗證涵蓋全部四個情境）皆有對應任務。
- **Placeholder scan**：所有步驟皆為完整可執行的程式碼或明確指令，無 TBD/待補。
- **Type consistency**：`build_segments(cut_points, range_start, range_end)`、`parse_range(start_text, end_text) -> tuple[int, int]`、`_worker(self, source_info, cut_points, client, range_bounds)` 在三個 Task 間命名與簽名一致。
