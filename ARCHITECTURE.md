# SnapTranscript — 架構說明

## 工具總覽

會議音訊逐字稿工具。支援本地音訊上傳或 YouTube 音訊下載，分段切割後透過 Gemini 轉錄，合併輸出 TXT。

## 檔案清單

| 檔案 | 用途 |
|------|------|
| `Run SnapTranscript.bat` | 薄殼啟動器：只呼叫 launcher.ps1 |
| `launcher.ps1` | 環境檢查、首次安裝說明、建立 venv、啟動主程式 |
| `main.py` | 主程式：GUI + YouTube 下載 + 切割邏輯 + Gemini API 呼叫 |
| `requirements.txt` | Python 套件清單（google-genai、python-dotenv、yt-dlp） |
| `.env` | API Key 儲存（不進版控） |
| `.gitignore` | 排除 venv、.env、暫存檔 |

## 執行流程

```
Run SnapTranscript.bat
  └─ launcher.ps1
        └─ 環境檢查（Python / uv / ffmpeg / venv）
        └─ tkinter 視窗啟動
              ├─ 選音訊來源
              │     ├─ 【本地上傳】選取音訊檔
              │     └─ 【YouTube 下載】輸入網址 + 另存新檔對話框
              │           ├─ 下載後馬上轉錄
              │           └─ 只下載音訊（不需 API Key）→ 下載完結束
              ├─ 選切割模式（自動 30 分 / 自訂 HH:MM:SS）
              ├─ 輸入 / 確認 API Key
              └─ 按「開始」→ 背景執行緒
                    ├─ [YouTube 模式] yt-dlp 下載音訊（原始最佳音質轉 mp3）
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
| `DEFAULT_CHUNK_SECONDS` | 1800（30分） | 自動切割間隔 |
| `MODEL_NAME` | `gemini-flash-latest` | Gemini 模型 |
| `ENV_PATH` | `<專案根目錄>/.env` | API Key 儲存位置 |

## 輸出格式

### 逐字稿（本地上傳 / YouTube 下載後轉錄）

```
=== 第 1 段（00:00:00 - 00:30:00）===

[逐字稿內容...]

=== 第 2 段（00:30:00 - 01:00:00）===

[逐字稿內容...]
```

輸出路徑：
- **本地上傳**：與音訊檔同目錄，檔名加上 `_transcript.txt` 後綴
- **YouTube 下載後轉錄**：與下載音訊同目錄，檔名加上 `_transcript.txt` 後綴
- **YouTube 只下載**：只輸出 mp3，無逐字稿

## YouTube 下載設計

- 使用 `yt-dlp`，格式選擇 `bestaudio/best`，postprocessor 轉 mp3
- 存檔路徑由「另存新檔」對話框決定，使用者可自訂位置與檔名
- 下載進度透過 progress hook 回傳至 UI（%、MB、速度）
- Token 計算以音訊時長為準，與 mp3 bitrate 無關（32 tokens/秒）

## 切割設計決策：為何切 30 分鐘

### 模型規格（`gemini-flash-latest`）

本專案一律使用 `gemini-flash-latest`：指向 Gemini Flash 系列最新版本的別名，自動熱切換（可能是穩定版、預覽版或實驗版），無需手動更新模型 ID。

下表以目前別名指向版本的規格為參考基準，實際限制以 Google 官方文件為準：

| 限制 | 數值 |
|------|------|
| 最大輸入 tokens | 1,048,576（約 11 小時音訊） |
| 最大輸出 tokens | 65,536 |

### 為何需要切割（輸出 token 是關鍵）

輸入限制幾乎不是問題（11 小時容量遠超一般會議），但**輸出 token 上限才是真正的瓶頸**。

快速中文語速約 300~400 字/分鐘，換算 token：

| 會議長度 | 估計輸出 tokens | 是否安全 |
|----------|----------------|----------|
| 30 分鐘  | ~18,000        | ✅ 安全（上限 27%）|
| 60 分鐘  | ~36,000        | ✅ 安全（上限 55%）|
| 90 分鐘  | ~54,000        | ⚠️ 接近邊緣 |
| 120 分鐘 | ~72,000        | ❌ 超出上限 |

### 為何選 30 分鐘而非整份送出

- 每段輸出約 18,000 tokens，僅用上限的 27%，有充裕緩衝
- 若某段 API 呼叫失敗，只需重跑該段，不需重跑整份
- 缺點：段落接縫處可能有少量遺漏，說話者標籤在不同段落間可能不一致

### 暫存檔

- 格式：`_temp_seg_0.mp3`（與音訊同副檔名）
- 位置：專案根目錄
- 處理完畢自動刪除，異常退出也會在 finally 清除
