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
