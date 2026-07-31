# 模組拆分 + 段落級容錯與補跑 — 設計文件

日期：2026-07-31

## 背景與問題

使用者回報：勾選「自動重試」後，某段仍在連續 503 後失敗，整個任務中止。

追查 `main.py` 後確認兩個獨立缺陷：

**缺陷一：重試之間沒有等待。** `main.py:793-835` 的重試迴圈失敗後立刻重打，中間沒有任何 `time.sleep()`。但 503 UNAVAILABLE 的語意是「伺服器目前滿載」，0 秒後重打伺服器仍然滿載，5 次重試在短時間內全部燒完。目前的「自動重試 5 次」實際成功率遠低於它應有的水準。

**缺陷二：單段失敗會丟掉整個任務的成果。** 第 N 段重試耗盡後 `raise Exception`（`main.py:821-824`），跳到最外層 `except`（862 行），略過合併寫檔（843-859 行）。結果：

- 前面已成功段落的逐字稿只存在記憶體的 `transcripts` list，隨著任務中止一併丟失
- 暫存音訊檔在 `finally`（876-879 行）被刪除
- 不會繼續處理後續段落（5 段時第 2 段失敗就不跑 3、4、5 段）
- 沒有任何方式只重跑失敗的段落，要救就得整個檔案重來

`ARCHITECTURE.md:135` 已宣稱「若某段 API 呼叫失敗，只需重跑該段，不需重跑整份」——這個承諾當初並未實作。

## 現況結構分析

`main.py` 共 973 行：

| 區塊 | 行數 | 性質 |
|---|---|---|
| 常數 | 20-26 | 純資料 |
| log 函式 | 28-68 | 純函式，無類別相依 |
| banner | 71-89 | 純函式 |
| 時間解析 + 分段 | 92-162 | 純函式，已有測試 |
| ffprobe / ffmpeg / yt-dlp | 165-229 | 純函式 |
| Gemini 呼叫 | 232-267 | 純函式 |
| `SnapTranscriptApp` | 271-961 | 691 行的類別 |
| └ `_build_ui` | 296-493 | 198 行 |
| └ `_worker` | 691-879 | 189 行，整條 pipeline |

前 248 行皆為模組層級純函式，與類別零相依，可直接搬移。問題集中在 691 行的類別，特別是 `_worker`。

**風險：pipeline 零測試覆蓋。** `tests/test_main.py` 僅 9 個測試，只涵蓋 `build_segments` 與 `parse_range`。`_worker` 整條轉錄流程沒有任何測試，且 Gemini 實際轉錄路徑未經 end-to-end 驗證。因此：純搬移安全，重構 `_worker` 不安全，兩者必須分階段進行，並在重構的同時補上測試。

## 決策紀錄

| 決策 | 選擇 | 理由 |
|---|---|---|
| 單段重試耗盡後 | 標記失敗、繼續下一段，事後可補跑 | 不白做工；符合 ARCHITECTURE 既有承諾 |
| 退避策略 | 固定 20 秒 × 5 次 | 使用者經驗：Google 卡住通常 20 秒內恢復。指數退避到 80 秒過久 |
| 拆分範圍 | 全拆，含 `job.py` 並補測試 | pipeline 抽離 tkinter 後才可測試，而這正是新功能要改的地方 |
| 檔案位置 | 平鋪專案根目錄，不進 `src/` | `launcher.ps1:237` 是 `python main.py`，搬進 src 需改 launcher，而 launcher 有 UTF-8 BOM 地雷（見 PITFALLS）。此規模平鋪可讀 |
| 補跑的音訊來源 | 從原始音訊重新切割 | 暫存檔可能數百 MB，留在專案目錄很髒；重切一段 30 分鐘音訊只需數秒 |

## 一、模組切分（階段 ① ②）

純搬移，行為零改變。

| 檔案 | 內容 | 來源行 |
|---|---|---|
| `config.py` | `SCRIPT_DIR` `ENV_PATH` `DEFAULT_CHUNK_SECONDS` `MODEL_NAME` `MAX_AUTO_RETRIES` `RETRY_WAIT_SECONDS`（新增） | 20-26 |
| `logger.py` | `_find_project_root` `LOG_DIR` `LOG_FILE` `write_log` `write_log_header` | 28-68 |
| `segments.py` | `hms_to_seconds` `seconds_to_hms` `parse_custom_cut_points` `parse_range` `build_segments` | 92-162 |
| `audio.py` | `get_audio_duration` `cut_audio_segment` `download_youtube_audio` | 165-229 |
| `transcriber.py` | `transcribe_segment` + prompt + 新增 `classify_error` / `is_quota_error` | 232-267 |
| `ui.py` | `SnapTranscriptApp` | 271-961 |
| `main.py` | `show_cth_banner` + Tk root + `main()` | 71-89, 964-973 |

搬移時 `_write_log` / `_write_log_header` 去掉底線前綴改為 `write_log` / `write_log_header`（跨模組呼叫，不再是私有）。`_find_project_root` 維持底線（僅 `logger.py` 內部使用）。

`classify_error` 是把目前散在 `_worker` 內的字串比對（`main.py:799-808` 的 `"503" in err_str` 等判斷）抽成獨立純函式：

```python
def classify_error(e: Exception) -> tuple[str, str] | None:
    """回傳 (可讀原因, log 用 status)；不可重試的錯誤回傳 None"""
```

`is_quota_error(e) -> bool` 對應 `main.py:865` 的 429 / quota / exhausted 判斷。兩者皆為純函式，可直接測試。

`launcher.ps1` 不需修改。`tests/test_main.py` 的 import 目標改為對應模組，測試內容不變。

## 二、`job.py` 介面（階段 ③）

```python
@dataclass
class SegmentResult:
    index: int          # 從 1 開始
    start_sec: int
    end_sec: int
    text: str | None    # 成功的逐字稿，失敗時為 None
    error: str | None   # 失敗原因（可讀），成功時為 None

@dataclass
class JobCallbacks:
    log: Callable[[str], None]                 # 推 UI 記錄框
    progress: Callable[[int, int, str], None]  # 進度條 + 標籤
    ask: Callable[[str], bool]                 # 未勾自動重試時跳 dialog

class TranscriptionJob:
    def __init__(self, audio_path, segments, client, auto_retry, callbacks,
                 transcribe_fn=transcriber.transcribe_segment,
                 cut_fn=audio.cut_audio_segment,
                 sleep_fn=time.sleep): ...

    def run(self) -> str:          # 跑全部段落，回傳輸出檔路徑
    def retry_failed(self) -> str: # 只跑失敗段落，回傳輸出檔路徑

    @property
    def failed_count(self) -> int
```

末三個 `_fn` 參數為測試注入點：測試傳入可控的 transcribe（依需要拋 503）、假的 cut（不需 ffmpeg）、假的 sleep（不需真的等 20 秒）。**測試執行不需要 ffmpeg、網路或 API Key。**

**模組邊界**：YouTube 下載、ffprobe 取時長、計算切割點留在 `ui.py` 的 `_worker`；`job.py` 只負責「把給定的段落轉錄出來並寫檔」。輸出路徑由 `job` 依 `audio_path` 推導（`<base>_transcript.txt`）並保存為屬性，供 `run()` 與 `retry_failed()` 共用。

## 三、功能行為（階段 ④）

### 退避

`RETRY_WAIT_SECONDS = 20`，固定 20 秒，最多 `MAX_AUTO_RETRIES`（5）次。等待以 1 秒一輪的迴圈實作（非單次 `sleep(20)`），每輪透過 `progress` callback 更新標籤為 `第 2 段重試中... 17 秒`，等待結束後還原為 `N / M 段完成`。

逐秒更新的目的是讓 UI 不會看起來像凍結；迴圈結構同時讓未來加入「取消」功能有接點。

### 段落容錯

單段重試耗盡後不再 raise，改為建立 `SegmentResult(text=None, error=原因)` 並繼續下一段。

**例外：429 配額用盡。** `is_quota_error(e)` 為真時立刻中止整個任務（繼續跑只會持續撞牆），但在中止前先把已完成段落合併寫檔——這是相對現況的改善（現況整份丟失）。

未勾選「自動重試」時維持現有行為：透過 `ask` callback 跳 dialog 詢問，使用者選「否」則該段標記失敗（行為變更：原本是中止整個任務，現在改為與自動重試耗盡一致，標記後繼續）。

### 輸出格式

不論是否有失敗段落都產生逐字稿檔。失敗段落寫入佔位符：

```
=== 第 2 段（00:30:00 - 01:00:00）===

[此段轉錄失敗：Gemini 伺服器回傳 503，可於程式內重試]
```

成功段落格式不變。合併寫檔邏輯為獨立方法，補跑成功後重複呼叫、原地覆寫同一輸出檔。

### 補跑

任務結束後 `failed_count > 0` 時，UI 顯示「重試失敗的 N 段」按鈕，與「開啟資料夾」按鈕並排。

按下後於背景執行緒呼叫 `job.retry_failed()`：只處理 `text is None` 的段落，從 `audio_path` 重新切割音訊（不保留暫存檔），成功則更新該 `SegmentResult`、重新合併覆寫輸出檔。全部補完後按鈕消失。

原始音訊檔已被刪除或移動時，跳錯誤提示，不進入補跑流程。

### 完成訊息

- 全部成功：`逐字稿已儲存：<路徑>`（不變）
- 部分失敗：`逐字稿已儲存（4/5 段成功，1 段失敗）`，並保留補跑按鈕

## 四、Log 規範調整

目前 `_log(msg, level, to_file)` 將「推 UI」與「寫檔」綁在同一個呼叫，靠 `to_file=False` 預設值達成 fail-closed。

拆分後 `job.py` 改為兩者分開呼叫：UI 用 `callbacks.log()`、落檔用 `logger.write_log()`，僅在 `ARCHITECTURE.md` 規定的三個時機（任務起始、錯誤行、任務結果）顯式呼叫 `write_log`。這比現況更明確——不再需要靠預設值防呆，因為兩條路徑在型別上就是分開的。

`ui.py` 保留 `_log` 作為 UI 推送的薄包裝（不再有 `to_file` 參數）。

落檔內容維持既有紀律：不記逐字稿全文、不記 API request/response payload、錯誤行只記 `type(e).__name__` 與 status。

**新增落檔行**：單段最終失敗時記一行 `第N段 最終失敗 -> <status>`。任務結果行改為反映部分成功，例如 `部分成功 4/5 段，耗時 12分30秒`。

`ARCHITECTURE.md` 的「Log / 錯誤紀錄」章節與「檔案清單」「執行流程」需同步更新。

## 五、測試

現有 9 個測試（`build_segments`、`parse_range`）搬到對應模組後維持不變。

新增約 16 個：

**`transcriber.classify_error` / `is_quota_error`**
1. 503 訊息 → 回傳 503 分類
2. UNAVAILABLE 訊息 → 回傳 503 分類
3. 「Gemini 回傳空白結果」→ 回傳空白結果分類
4. 其他錯誤 → 回傳 None
5. 429 / quota / exhausted → `is_quota_error` 為真

**`TranscriptionJob`**
6. 全部段落成功 → 輸出檔含所有段落，`failed_count == 0`
7. 某段第一次 503、第二次成功 → 最終成功，`sleep_fn` 被呼叫一次且參數為 20
8. 某段持續 503 → 重試 5 次後標記失敗，`sleep_fn` 共呼叫 5 次
9. 第 2 段失敗但第 3 段成功 → 第 3 段內容出現在輸出檔
10. 失敗段落 → 輸出檔含佔位符文字
11. `retry_failed()` 成功 → 佔位符被真實內容取代，`failed_count` 歸零
12. `retry_failed()` 再度失敗 → 佔位符保留，`failed_count` 不變
13. 429 → 中止後續段落，但已完成段落已寫檔
14. 未勾自動重試 → 呼叫 `ask` callback；回 `False` 則該段標記失敗並繼續
15. 全部段落皆失敗 → 仍產生輸出檔，內容全為佔位符
16. `progress` callback 在等待期間收到倒數標籤

## 實作階段

四個階段各自為一個 commit，每階段結束後可啟動 App 驗證：

1. **模組層級純搬移** — `config.py` `logger.py` `segments.py` `audio.py` `transcriber.py`；`main.py` 剩類別 + 入口。行為零改變
2. **搬移 UI 類別** — `SnapTranscriptApp` → `ui.py`；`main.py` 剩入口。行為零改變
3. **抽出 `job.py` + 補測試** — `_worker` 的轉錄流程移入 `TranscriptionJob`，行為維持現況（單段失敗仍中止），先讓測試覆蓋現有行為
4. **加功能** — 退避、段落容錯、補跑按鈕，由階段 3 的測試驅動

階段 3 刻意保持行為不變、只搬結構並補測試，讓階段 4 的行為變更有測試作為對照基準。

## 影響範圍

- `main.py`：973 行 → 約 30 行
- 新增：`config.py` `logger.py` `segments.py` `audio.py` `transcriber.py` `job.py` `ui.py`
- `tests/test_main.py`：拆為 `tests/test_segments.py`、`tests/test_transcriber.py`、`tests/test_job.py`
- `launcher.ps1`：不修改
- 文件：`ARCHITECTURE.md`（檔案清單、執行流程、log 章節、設定變數表）、`CHANGELOG.md`、`PITFALLS.md`（503 條目補記退避策略）、`README.md`（補跑功能說明）
