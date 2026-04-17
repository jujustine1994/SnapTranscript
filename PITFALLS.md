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

**解法：** 在 `_worker` 裡用 while 迴圈包住 `transcribe_segment` 呼叫，503 時 log 錯誤、跳 dialog 問是否重試，使用者按「是」繼續、按「否」中止。背景執行緒透過 `msg_queue + threading.Event` 阻塞等待主執行緒的 dialog 結果。

**禁止：** 不要把模型名稱從 `gemini-flash-latest` 改掉（使用者指定維持此設定）。不要用固定 sleep 自動重試，應讓使用者決定。
