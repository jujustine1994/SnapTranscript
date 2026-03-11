# CHANGELOG — SnapTranscript

## 現狀總覽

**已完成功能：**
- tkinter 視窗介面（選檔、切割設定、API Key、進度顯示）
- 自動切割模式（每 20 分鐘）
- 自訂切割點（HH:MM:SS，每行一個）
- ffmpeg 音訊切割（優先 copy codec，失敗自動重新編碼）
- Gemini gemini-flash-latest 逐字稿
- 合併輸出含段落標記的 TXT 檔案
- API Key 自動儲存 / 讀取（.env）
- 背景執行緒處理，UI 不凍結

**未完成 / 待優化：**
- 尚未測試實際 Gemini API 回應格式
- 尚未測試各種音訊格式（mp3 / m4a / wav）

---

## 更新記錄

### 2026-03-11
- 新增：專案初始建置，完成所有基礎功能
