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

### 2026-03-12（二）
- 修改：預設切割間隔從 20 分鐘改為 30 分鐘
- 文件：ARCHITECTURE.md 補充 token 限制設計決策（輸出 token 才是切割關鍵原因）

### 2026-03-12（一）
- 新增：「如何取得 API Key？」說明彈窗（含申請步驟、Google AI Studio 連結、Free tier 注意事項）
- 新增：README 補充 API Key 申請教學段落
- 修改：「如何取得 API Key？」改為文字連結樣式，與「開始轉錄」主按鈕區隔視覺層級
- 修改：「開始轉錄」按鈕加大高度
- 修改：音訊檔案 Entry 改為自動撐滿寬度（grid layout）
- 修改：處理進度區塊底部補充間距，避免框線被截斷

### 2026-03-11
- 新增：專案初始建置，完成所有基礎功能
- 修改：Gemini prompt 改為原文轉錄，不再強制翻譯成繁體中文
