# 擷取範圍（部分音訊轉錄）設計

## 背景

目前 SnapTranscript 一律轉錄整段音訊，再依「切割設定」（自動每 30 分鐘 / 自訂切割點）分段送 Gemini。使用者希望能只挑音訊裡的一段時間範圍（例如 00:10:00 ~ 00:45:00）來轉錄，範圍外完全不處理、不上傳，省時間與 API 用量。

## 目標

- 新增可選的「擷取範圍」設定：勾選後可指定起始/結束時間，只轉錄這段範圍。
- 預設不勾選＝整段轉錄，原有行為完全不變。
- 範圍與既有「切割設定（自動/自訂）」共同運作：切割設定決定範圍內怎麼分段送 Gemini，而不是取代它。

## UI 設計

在「音訊來源」與「切割設定」之間新增 `LabelFrame`「擷取範圍」：

- `Checkbutton`「只處理音訊的一部分」，變數 `self.range_enabled`（`tk.BooleanVar`，預設 `False`）
- 勾選後顯示一個子 `Frame`（未勾選時 `grid_remove()`），內含：
  - 「起始時間」`Entry` → `self.range_start_var`
  - 「結束時間」`Entry` → `self.range_end_var`
  - 格式提示：`HH:MM:SS`
- 灰色說明文字（固定顯示，不受勾選影響）：
  「⚠️ 下方切割點為原始音訊的絕對時間，需落在此範圍內才會生效」

## 驗證規則

在 `_start()` 驗證階段（沿用現有 messagebox 錯誤提示風格）：

1. 若 `range_enabled` 為真：
   - 起始/結束欄位都不可空白
   - 都必須符合 `HH:MM:SS` 格式（沿用 `hms_to_seconds` / 既有 regex 邏輯）
   - 起始 < 結束
   - 兩者都需 ≤ 音訊總長度（此檢查在背景執行緒拿到 `total_duration` 後做，因為 UI 階段還沒讀音訊檔；若超出範圍則丟錯誤訊息並中止，行為與切割點驗證一致）

## 邏輯整合（`_worker`）

新增函式 `parse_range(text_start, text_end) -> tuple[int, int]`，回傳 `(start_sec, end_sec)`，沿用 `hms_to_seconds`，格式錯誤拋 `ValueError`（訊息風格同 `parse_custom_cut_points`）。

`_worker` 內取得 `total_duration` 後：

```
if range_enabled:
    range_start, range_end = range_bounds  # 已在 _start() 解析好傳入
    if range_end > total_duration or range_start >= total_duration:
        raise Exception("擷取範圍超出音訊總長度，請重新設定")
else:
    range_start, range_end = 0, int(total_duration)
```

`build_segments` 改為接受範圍邊界（新增參數 `range_start: int = 0`），呼叫端傳入 `range_end` 取代原本的 `total_duration`：

```python
def build_segments(cut_points: list[int], range_start: int, range_end: int) -> list[tuple[int, int]]:
    boundaries = [range_start] + cut_points + [range_end]
    ...
```

分段點計算依範圍調整：

- **自動模式**：切點 = `range_start + n * DEFAULT_CHUNK_SECONDS`（`n=1,2,...`），只取小於 `range_end` 的點。
- **自訂模式**：沿用使用者輸入的絕對切割點 `cut_points`，過濾為 `range_start < p < range_end` 的點（範圍外的切點忽略，不報錯，與既有「自動丟棄超出總長度的切點」邏輯一致）。

切音訊呼叫 `cut_audio_segment(audio_path, start_sec, duration_sec, output_path)` 不需改動，因為 `start_sec`／`duration_sec` 本就是絕對秒數換算後的相對值。

## 不在範圍內

- 不支援多段非連續範圍（一次只能選一段起訖）。
- 不在 YouTube 模式做任何特殊處理：範圍設定對本地上傳與 YouTube 下載後轉錄一視同仁；「只下載音訊」模式維持停用切割/範圍區塊（沿用現有 `_update_btn_label` 停用邏輯，需把「擷取範圍」frame 加入該停用清單）。

## 測試重點

- 不勾選範圍：行為與現在完全一致（迴歸測試）。
- 勾選範圍 + 自動切割：驗證切點正確從 `range_start` 起算，且最後一段在 `range_end` 結束。
- 勾選範圍 + 自訂切割：範圍外的切割點被忽略；範圍內的切割點正常生效。
- 起始/結束格式錯誤、起始≥結束、範圍超出總長度的錯誤提示。
- 「只下載音訊」模式下「擷取範圍」區塊應被停用（灰底不可互動），與切割設定/API Key 區塊行為一致。
