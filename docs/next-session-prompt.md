# 給下一個對話的 prompt

把底下 `---` 之間的內容整段複製，貼到新對話當第一則訊息。

---

SnapTranscript 專案（`C:\Users\CTH\Documents\Code\SnapTranscript`）。

## 我現在的狀況

我在忙，**大概兩小時才會看一次電腦**。所以：

- 你自己找出「可以自動完成的」「該修的」「需要花時間跑的」任務，排好順序直接開始做，不要每一步都停下來問我。
- 遇到可以自己判斷的決策就自己決定，**但一定要把決策與理由記錄下來**——寫在程式碼註解、`ARCHITECTURE.md`、`PITFALLS.md`、或 `TODO.md` 都可以。重點是之後我想調參數或改做法時，看得到當初為什麼這樣決定、要去哪裡改。
- **可調的東西一律拉成具名常數放進 `config.py`**，不要散在程式碼裡寫死。
- 真的需要我拍板的（會動到我明確指定過的設定、或你判斷不了的取捨），累積起來一次問，不要一個一個丟。

## 專案現況

Python + tkinter + ffmpeg + Gemini API 的 Windows 桌面工具，把會議音訊切段轉成逐字稿。

- 啟動器是 `Run SnapTranscript.bat`
- 測試指令：`./venv/Scripts/python.exe -m unittest discover -s tests -v`（**專案沒有 pytest，不要用**）
- 目前 50 個測試全過，執行不需要 ffmpeg、網路或 API Key
- 2026-08-01 剛做完一輪大重構：`main.py` 從 973 行拆成 8 個模組，並新增「單段轉錄失敗不中止整個任務、結束後可補跑失敗段落」的功能，已合併進 master 並 push
- 各種格式（mp3 / m4a / wav / flac）、擷取範圍、UI 互動路徑都已用真實音訊實測通過

先讀 `README.md`、`ARCHITECTURE.md`、`TODO.md`、`PITFALLS.md` 了解全貌，`CHANGELOG.md` 的 2026-07-31 與 08-01 兩則記錄了最近的改動。

## 硬規則（違反會出事，別踩）

- **不要改 `MODEL_NAME`**，必須維持 `gemini-flash-latest`（我指定的，就算遇到 503 或有更新的模型也不要動）。
- **不要用一般編輯器改 `launcher.ps1`**，它是 UTF-8 with BOM，存錯編碼整個腳本會壞掉（`PITFALLS.md` 有記）。
- **不要在文件或 UI 寫出具體的 API 免費額度數字**（例如「每天 N 次」），Google 會調整，寫死會誤導。要引導使用者去官網查。
- **落檔紀律**：`logs/app.log` 只寫三種東西——任務起始、錯誤行、任務結果。錯誤行只記例外類型與 HTTP status，**絕對不要把例外全文落檔**（可能挾帶 URL 或 token）。逐字稿全文與 API payload 一律不落檔。
- **20 秒重試退避只在使用者勾選「自動重試」時套用**，沒勾選時走詢問對話框且完全不 sleep。這條 `PITFALLS.md` 有明文禁令，也有測試守著。
- **測試不得依賴 ffmpeg、網路或 API Key**。`job.TranscriptionJob` 的 `transcribe_fn` / `cut_fn` / `sleep_fn` 就是為此保留的注入點。
- 改完程式**一定要同步更新 .md 文件**。上一輪重構就是因為沒做到，事後才抓到三處文件與程式碼不符。
- 繁體中文、台灣用語，註解與 docstring 也是。

## Gemini API 額度

**測試額度一天只有 20 次左右，省著用。** 大部分東西用假的 transcribe 函式就能測，不需要真的打 API。真的要打之前先想清楚這次呼叫要驗證什麼。

如果需要語音素材，Windows 內建 TTS 可以生（不花額度）：

```powershell
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SetOutputToWaveFile("out.wav"); $s.Speak("要念的內容"); $s.Dispose()
```

## 不要直接啟動 GUI

`root.mainloop()` 會卡住不返回。要驗證 UI 就用「建立視窗 → `update_idletasks()` → `root.after(300, root.destroy)` → `mainloop()`」的模式，並把 `messagebox.*` 換成不阻塞的假函式。這招在上一輪很好用。

## 已知待辦（自己判斷優先順序，不用照這個順序）

`TODO.md` 有完整清單，摘要：

1. **`transcribe_segment` 沒有任何測試** — 它的 `client` 是參數傳進去的，用假 client 就能測「PROCESSING 輪詢」「非 ACTIVE 拋錯」「呼叫失敗仍刪檔」「回傳空白結果」四條路徑，不需要網路。這是目前最划算的補強。
2. **`ui.py` 的分段計算沒有測試** — 自動 30 分鐘一刀 + 擷取範圍夾擠的邏輯卡在 UI 執行緒函式裡。建議抽成 `segments.plan_segments(...)` 再補測試。
3. `_write_output` 寫檔失敗時（例如磁碟滿）`.tmp` 檔會留在磁碟上不會清。
4. `segments.py` 有兩份一模一樣的時間格式正規表示式，可提成模組常數。
5. **超長音訊（>2 小時）的記憶體與穩定性沒測過**。這種需要跑很久，適合你趁我不在的時候跑。注意這會花 API 額度，要先算好要用幾次。

做完或有進展就記在 `TODO.md` 與 `CHANGELOG.md`，我回來看那兩份就知道發生什麼事。
