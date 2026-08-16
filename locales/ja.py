"""locales/ja.py — 日本語

改這裡的譯文不影響任何邏輯：程式一律用 key 比對。改錯最壞的情況只是
畫面顯示怪怪的。

⚠ 帶變數的訊息一律用**具名** placeholder（{path} 而不是 {0}）——翻譯時
語序一變，位置參數就錯位。四種語言的 placeholder 集合必須完全一致，
tests/test_i18n.py 會檢查。
"""

from __future__ import annotations

STRINGS: dict[str, str] = {
}
