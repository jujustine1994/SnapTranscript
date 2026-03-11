```
/*  ================================  *\
 *                                    *
 *          C  T  H                   *
 *        created by CTH              *
 *                                    *
\*  ================================  */
```

規則檔: windows-tool.md
類型: Windows 工具

# SnapTranscript

將會議音訊檔案分段切割，透過 Gemini AI 生成繁體中文逐字稿，合併輸出為單一 TXT 檔案。

## 執行方式

雙擊 `啟動.bat`，首次執行會自動建立虛擬環境並安裝套件。

## 系統需求

- Windows 10/11
- Python 3.10+
- ffmpeg（已安裝於系統 PATH）
- Gemini API Key

## 首次設定

1. 雙擊 `啟動.bat`
2. 等待虛擬環境建立完成
3. 在視窗中輸入 Gemini API Key（勾選「記住」可自動儲存至 `.env`）

## 技術棧

- Python 3.13 + tkinter（GUI）
- ffmpeg（音訊切割）
- google-generativeai `gemini-flash-latest`（逐字稿）
- python-dotenv（API Key 管理）
- uv（套件管理）

## .gitignore 重要項目

- `venv/`、`__pycache__/`、`*.pyc`
- `.env`（含 API Key，絕不上傳）
- `_temp_seg_*`（處理中暫存檔）
