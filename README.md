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

雙擊 `Run SnapTranscript.bat`，首次執行會自動建立虛擬環境並安裝套件。

## 系統需求

- Windows 10/11
- Python 3.10+
- ffmpeg（已安裝於系統 PATH）
- Gemini API Key

## 首次設定

1. 雙擊 `Run SnapTranscript.bat`
2. 等待虛擬環境建立完成
3. 在視窗中輸入 Gemini API Key（勾選「記住」可自動儲存至 `.env`）

## 只轉錄音訊的一部分

勾選「擷取範圍」下的「只處理音訊的一部分」，輸入起始/結束時間（HH:MM:SS），即可只轉錄該段範圍，範圍外完全不切割、不上傳。不勾選則維持整段轉錄。

## 切割設定

自動模式每 30 分鐘切一段。若最後剩下的尾巴不到 1 分鐘，會併入前一段，不會單獨
切出一個幾秒鐘的段落。自訂切割點則完全照你輸入的位置切，不做任何合併。

## 自動重試

「開始轉錄」按鈕右側的「自動重試」勾選框：勾選後，若 Gemini 回傳 503 或空白結果，會自動重試（最多 5 次）不再跳出詢問視窗；不勾選則維持每次跳出視窗詢問是否重試。

### 轉錄失敗怎麼辦

單一段落轉錄失敗不會影響其他段落——程式會標記該段、繼續處理後面的段落，
最後照常輸出逐字稿，失敗的段落在檔案中顯示為佔位符。

轉錄結束後若有失敗段落，畫面會出現「重試失敗的 N 段」按鈕，按下只會重跑
那幾段，不需要整個檔案重來。補跑成功後逐字稿會自動更新。

勾選「自動重試」（預設開啟）時，每段遇到伺服器錯誤會等 20 秒後重試，最多 5 次。

## 取得 Gemini API Key（免費）

1. 前往 [Google AI Studio](https://aistudio.google.com/apikey)（需登入 Google 帳號）
2. 點擊「Create API key」
3. 選擇「Create API key in new project」
4. 複製產生的 Key，貼入 SnapTranscript 的 API Key 欄位

> 視窗中點「如何取得？」按鈕可直接開啟上方網址。

> 免費額度以 [Google AI Studio](https://aistudio.google.com/apikey) 頁面顯示為準。若出現「配額已達上限」錯誤，等隔天配額自動重置即可。

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
