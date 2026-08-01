"""全域常數設定。"""

import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(SCRIPT_DIR, ".env")
DEFAULT_CHUNK_SECONDS = 30 * 60  # 預設 30 分鐘
MODEL_NAME = "gemini-flash-latest"
MAX_AUTO_RETRIES = 5  # 「自動重試」勾選時，單段最多自動重試次數
RETRY_WAIT_SECONDS = 20  # 自動重試前的固定等待秒數（503 多半 20 秒內恢復）
FILE_UPLOAD_POLL_SECONDS = 2  # 上傳後輪詢 Gemini 檔案狀態的間隔秒數
# 自動切割時，短於這個秒數的「尾巴段」併回前一段，不單獨成段。
# 例如 30 分 05 秒的音訊，若照 30 分一刀會多出一個 5 秒的段落，白花一次 API
# 呼叫換來幾乎沒內容的逐字稿。設 0 可關閉這個行為。
# 只作用於自動模式——自訂切割點是使用者明確指定的，不該被程式合併掉。
#
# 5 分鐘（使用者 2026-08-01 指定）：這代表最長的一段會是
# DEFAULT_CHUNK_SECONDS + MIN_SEGMENT_SECONDS - 1 = 34 分 59 秒。
# 換算輸出約 21,000 tokens，佔 65,536 上限的 32%，仍有充裕緩衝。
# 若之後把 DEFAULT_CHUNK_SECONDS 調大，記得回頭檢查這個加總。
MIN_SEGMENT_SECONDS = 5 * 60
