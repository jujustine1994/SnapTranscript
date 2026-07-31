"""全域常數設定。"""

import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(SCRIPT_DIR, ".env")
DEFAULT_CHUNK_SECONDS = 30 * 60  # 預設 30 分鐘
MODEL_NAME = "gemini-flash-latest"
MAX_AUTO_RETRIES = 5  # 「自動重試」勾選時，單段最多自動重試次數
RETRY_WAIT_SECONDS = 20  # 自動重試前的固定等待秒數（503 多半 20 秒內恢復）
