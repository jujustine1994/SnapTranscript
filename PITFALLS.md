# PITFALLS — SnapTranscript

踩過的坑，遇到問題再累積。

---

<!-- 格式：
## 問題標題
**問題：** 描述
**原因：** 根因
**解法：** 怎麼修
**禁止：** 不能再做什麼
-->

## dist-info 損壞導致 uv 無法安裝新套件

**問題：** launcher.ps1 執行 `uv pip install -r requirements.txt` 時出現：
```
x Failed to read `pyasn1-modules==0.4.2`
|-> Failed to read metadata from installed package
`-> failed to open file `...pyasn1_modules-0.4.2.dist-info\METADATA`: 系統找不到指定的檔案。
```
接著程式啟動失敗，報 `ModuleNotFoundError`（新套件未裝入）。

**原因：** venv 裡某個套件的 `.dist-info` 資料夾存在，但內部的 `METADATA` 檔遺失（可能因為安裝中斷或磁碟異常）。uv 讀取已安裝套件清單時碰到這條損壞記錄，直接中止整個安裝流程，導致新套件（如 yt-dlp）未被安裝。

**解法：** 在 `uv pip install` 之前，掃描並刪除所有缺少 `METADATA` 的 `.dist-info` 目錄，讓 uv 重新安裝該套件：
```powershell
$broken = Get-ChildItem "venv\Lib\site-packages" -Directory -Filter "*dist-info" -ErrorAction SilentlyContinue | Where-Object {
    -not (Test-Path (Join-Path $_.FullName "METADATA"))
}
foreach ($dir in $broken) {
    Write-Host "[INFO] 清理損壞的套件資訊：$($dir.Name)" -ForegroundColor Yellow
    Remove-Item -Recurse -Force $dir.FullName
}
uv pip install -r requirements.txt --python venv\Scripts\python.exe -q
```

**禁止：** 不能用 `-q` 靜默模式掩蓋錯誤後繼續執行（會讓使用者誤以為安裝成功）。清理步驟必須放在 `uv pip install` 之前。

---

## launcher.ps1 閃退：UTF-8 without BOM 導致中文語法錯誤

**問題：** 雙擊 `Run SnapTranscript.bat` 後視窗閃退，直接跑 `launcher.ps1` 出現一堆 parse error，中文字全爛成亂碼。

**原因：** Windows PowerShell 5.x 讀取 .ps1 檔案時，預設用系統編碼（台灣環境為 CP950），不是 UTF-8。檔案若存成 UTF-8 without BOM，PowerShell 無法識別編碼，中文字解析失敗，連帶把整個語法結構搞壞（括號、引號對不上），導致腳本直接無法執行。

**解法：** 將 `launcher.ps1` 重存為 **UTF-8 with BOM**。PowerShell 看到 BOM（`EF BB BF`）才會正確用 UTF-8 讀取。用 Python 轉換：
```python
with open('launcher.ps1', 'r', encoding='utf-8') as f:
    content = f.read()
with open('launcher.ps1', 'w', encoding='utf-8-sig') as f:
    f.write(content)
```

**禁止：** 之後修改 `launcher.ps1` 不能用預設存檔（VS Code 預設 UTF-8 without BOM）。存檔前確認右下角顯示 `UTF-8 with BOM`，或在 VS Code 用「以編碼方式儲存」→ `UTF-8 with BOM`。

---

## Gemini API 503 UNAVAILABLE

**問題：** 呼叫 `client.models.generate_content()` 時拋出 503，訊息為 `This model is currently experiencing high demand`。

**原因：** `gemini-flash-latest` alias 自 2026-01-21 起指向 `gemini-3-flash-preview`（預覽版），伺服器資源有限，高流量時段容易打不到。503 是暫時性，等一下重試通常就過。

**解法：** 由 `job.TranscriptionJob` 的重試迴圈包住 `transcribe_segment` 呼叫，
503 時 log 錯誤、依「自動重試」設定決定自動重試或跳 dialog 詢問。使用者按「否」
或自動重試耗盡時，標記該段失敗並繼續下一段（不中止整個任務），結束後可用
「重試失敗的 N 段」按鈕補跑。背景執行緒透過 `msg_queue + threading.Event`
阻塞等待主執行緒的 dialog 結果。

**2026-07-16 更新：** 新增「自動重試」勾選框（2026-07-31 起預設勾選），勾選後跳過 dialog、自動重試，上限 `MAX_AUTO_RETRIES`（5）次後才中止該段。這不違反下方禁止事項——是否自動重試仍由使用者透過勾選框主動決定，不是程式片面用固定 sleep 悄悄重試。

**2026-07-31 更新：** 發現原本的自動重試沒有任何等待——失敗後立刻重打，
但 503 的語意是伺服器滿載，0 秒後重打仍然滿載，5 次重試在數秒內全部燒完，
等於沒有重試。改為每次重試前固定等待 `RETRY_WAIT_SECONDS`（20）秒，以 1 秒
一輪的倒數迴圈實作讓 UI 顯示剩餘秒數。同時單段重試耗盡不再中止整個任務，
改為標記後續跑，結束後可用「重試失敗的 N 段」按鈕補跑。

**禁止：** 不要把模型名稱從 `gemini-flash-latest` 改掉（使用者指定維持此設定）。不要在使用者沒有主動選擇的情況下（沒勾選「自動重試」）用固定 sleep 靜默重試，應讓使用者決定。

不要把重試改回「失敗立刻重打」，也不要把等待改成單次 `sleep(20)`——
倒數迴圈是為了讓 UI 不會看起來像凍結。20 秒退避只在使用者勾選「自動重試」
時套用，未勾選時仍走 dialog 且完全不 sleep，這點不可改。

---

## Gemini 回傳空白結果（finish_reason: MALFORMED_RESPONSE）

**問題：** `client.models.generate_content()` 成功回傳（沒有拋 exception），但 `response.text` 是 `None`，`response.candidates[0].finish_reason` 顯示 `MALFORMED_RESPONSE`。同一段音訊有時第一次就過、有時要重試好幾次才過，沒有明顯規律。

**原因：** Google 沒有公開這個 finish_reason 的判定邏輯，目前只能推測：`gemini-flash-latest` 是滾動別名，指向的版本可能還在調整、伺服器端偶發性內部錯誤，或模型推理（thinking）過程失敗導致回傳格式不完整。**不確定是哪一種，無法斷定根因**，只能觀察到「重試通常會過」這個現象，所以才加上 2026-07-16 的「自動重試」功能因應。

**解法：** 目前無法根治，只能重試。可勾選「自動重試」讓程式自動重試（上限 5 次），或維持手動 dialog 確認。若之後想降低出錯率，可考慮改用非 `-latest` 的穩定版模型號碼，但目前使用者指定維持 `gemini-flash-latest`（見上方 503 條目）。

**禁止：** 不要把這個錯誤誤判為配額用盡或帳號問題去排查（那類錯誤訊息會包含 `429` / `quota` / `exhausted`，`main.py` 已有另外的判斷邏輯）。
