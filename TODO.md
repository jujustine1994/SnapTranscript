# TODO — SnapTranscript

## 待辦

- [ ] 實際執行測試（選音訊 → 轉錄 → 輸出）
- [ ] 確認 Gemini 回應內容符合預期格式
- [ ] 測試不同音訊格式（mp3 / m4a / wav / flac）
- [ ] 測試超長音訊（>2 小時）的記憶體與穩定性

## 設定步驟（首次使用）

1. 確認 ffmpeg 已安裝：在命令列執行 `ffmpeg -version`
2. 準備 Gemini API Key（從 Google AI Studio 取得）
3. 雙擊 `啟動.bat` → 自動建立 venv → 輸入 API Key → 開始使用
