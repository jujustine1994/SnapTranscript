# CHANGELOG — SnapTranscript

## 現狀總覽

**已完成功能：**
- tkinter 視窗介面（選檔、切割設定、API Key、進度顯示）
- 自動切割模式（每 30 分鐘）
- 自訂切割點（HH:MM:SS，每行一個）
- ffmpeg 音訊切割（優先 copy codec，失敗自動重新編碼）
- Gemini gemini-flash-latest 逐字稿
- 合併輸出含段落標記的 TXT 檔案
- API Key 自動儲存 / 讀取（.env）
- 背景執行緒處理，UI 不凍結
- YouTube 音訊下載（yt-dlp，原始最佳音質轉 mp3）
- YouTube 下載進度顯示（% + MB + 速度）
- YouTube 模式可選「下載後轉錄」或「只下載音訊（不需 API Key）」

**未完成 / 待優化：**
- 尚未測試實際 Gemini API 回應格式
- 尚未測試各種音訊格式（mp3 / m4a / wav）

---

## 更新記錄

### 2026-03-17（一）
- 新增：YouTube 音訊下載功能（yt-dlp，原始最佳音質轉 mp3）
- 新增：音訊來源切換 — 本地上傳 / YouTube 下載（radio button）
- 新增：YouTube 模式可選「下載後馬上轉錄」或「只下載音訊（不需 API Key）」
- 新增：YouTube 下載使用「另存新檔」對話框，可自訂儲存位置與檔名
- 新增：下載進度即時顯示（進度條 + 百分比 + 已下載 MB / 總 MB + 速度）
- 新增：啟動按鈕依模式動態改名（「開始轉錄」/ 「開始下載」）
- 修改：launcher.ps1 加入 yt-dlp 安裝說明
- 修改：launcher.ps1 每次啟動自動補裝缺少套件，並清理損壞的 dist-info

### 2026-03-16（一）
- 新增：launcher.ps1 加入系統架構偵測（`$isArm64`）
- 新增：ARM64 電腦找不到 Python 時，顯示警告訊息引導移除舊版 x64 再重裝
- 新增：ffmpeg 在 ARM64 安裝完成後提示「x64 版透過模擬執行，功能正常但速度略慢」

### 2026-03-12（三）
- 新增：launcher.ps1 自動安裝 ffmpeg（winget `Gyan.FFmpeg`），步驟從 3 步擴充為 4 步
- 修改：每個缺少的元件加上說明文字，告知用途與影響
- 修改：每次成功安裝後加 pause，讓使用者確認後再繼續
- 修改：Python / ffmpeg 需重開視窗時，補充說明 Windows PATH 更新機制

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
