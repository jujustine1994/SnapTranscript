# SnapTranscript — 架構說明

## 工具總覽

會議音訊逐字稿工具。選取音訊檔 → 分段切割 → Gemini 轉錄 → 合併輸出 TXT。

## 檔案清單

| 檔案 | 用途 |
|------|------|
| `Run SnapTranscript.bat` | 薄殼啟動器：只呼叫 launcher.ps1 |
| `launcher.ps1` | 環境檢查、首次安裝說明、建立 venv、啟動主程式 |
| `main.py` | 主程式：GUI + 切割邏輯 + Gemini API 呼叫 |
| `requirements.txt` | Python 套件清單 |
| `.env` | API Key 儲存（不進版控） |
| `.gitignore` | 排除 venv、.env、暫存檔 |

## 執行流程

```
Run SnapTranscript.bat
  └─ launcher.ps1
        └─ 環境檢查（Python / uv / venv）
        └─ tkinter 視窗啟動
              ├─ 使用者選音訊檔
              ├─ 選切割模式（自動 20 分 / 自訂 HH:MM:SS）
              ├─ 輸入 / 確認 API Key
              └─ 按「開始轉錄」→ 背景執行緒
                    ├─ ffprobe 取得音訊總時長
                    ├─ 建立分段清單 [(start, end), ...]
                    └─ 逐段處理：
                          ├─ ffmpeg 切割暫存檔
                          ├─ genai.upload_file 上傳
                          ├─ gemini-flash-latest 轉錄
                          └─ 刪除暫存檔
                    └─ 合併所有段落 → 輸出 _transcript.txt
```

## 關鍵設定變數（main.py）

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `DEFAULT_CHUNK_SECONDS` | 1200（20分） | 自動切割間隔 |
| `MODEL_NAME` | `gemini-flash-latest` | Gemini 模型 |
| `ENV_PATH` | `<專案根目錄>/.env` | API Key 儲存位置 |

## 輸出格式

```
=== 第 1 段（00:00:00 - 00:20:00）===

[逐字稿內容...]

=== 第 2 段（00:20:00 - 00:40:00）===

[逐字稿內容...]
```

輸出檔案路徑：與音訊檔同目錄，檔名加上 `_transcript.txt` 後綴。

## 暫存檔

- 格式：`_temp_seg_0.mp3`（與音訊同副檔名）
- 位置：專案根目錄
- 處理完畢自動刪除，異常退出也會在 finally 清除
