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
- 目前 111 個測試全過，執行不需要 ffmpeg、網路或 API Key
- 2026-08-01 做完兩輪：`main.py` 從 973 行拆成 8 個模組 + 段落級容錯，以及一輪測試補強與衛生修正，都已合併進 master
- 2026-08-02 又做了一輪：`_worker` 拆分、重試邏輯稽核（修掉手動模式 log 永遠寫「重試 0/5」的缺陷）

## ⚠️ GitHub 帳號目前被停權

2026-08-02 起 `jujustine1994` 被 GitHub 停權，push 會回 403（`Your account is suspended`），未登入抓 `github.com/jujustine1994` 也是 404。使用者已知情、正在處理，**不要花時間排查 git 設定或憑證，那不是問題所在**。

- 本地 `master` 目前領先 `origin/master` 數個 commit，帳號恢復後 `git push origin master` 即可，不需重做任何事
- 完整離線備份：`C:\Users\CTH\Documents\SnapTranscript-backup-20260802.bundle`（`git bundle`，含所有分支與歷史，已驗證）
- 這段期間照常 commit 到本地就好
- 各種格式（mp3 / m4a / wav / flac）、擷取範圍、UI 互動路徑都已用真實音訊實測通過
- 超長音訊已用 2.5 小時素材測過（記憶體全程 88 MB 無漂移），但還沒用真實 Gemini 呼叫跑完整份

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

1. **超長音訊用真實 Gemini 呼叫跑完整份** — 切割與記憶體已驗證，缺的是連續 5 段以上真實呼叫的穩定性。會花 5~6 次額度，動手前先確認。
2. `ui.py` 的 `_worker` 仍偏長（下載、分段、建立 job、三個 except 分支都在裡面）。分段那塊已抽走，剩下的要拆得先想清楚 UI 狀態怎麼傳。

## 使用者已經拍板、不要再問的決定

- **重試維持固定 20 秒 × 5 次**。有資料顯示這個預算偶爾不夠（2026-08-01 那次燒完 100 秒失敗、29 秒後補跑就成功），使用者知道這個代價，選擇維持。不要再提議改成指數退避。
- **逐字稿維持 UTF-8 無 BOM**。使用者不用 Excel 開這些檔，不需要 BOM。
- **`MIN_SEGMENT_SECONDS` 維持 5 分鐘**。
- **`requirements.txt` 不鎖版本**。2026-08-02 實測過：`uv pip install -r`（launcher 用的指令，沒有 `--upgrade`）不會升級已安裝的套件，所以「哪天啟動就壞掉」不會發生；而且 `google-genai` 2.16.0 已驗證相容（API 介面、物件屬性、101 個測試全過）。理由與證據寫在 `TODO.md`，不要再提議鎖版本。

做完或有進展就記在 `TODO.md` 與 `CHANGELOG.md`，我回來看那兩份就知道發生什麼事。
