"""全域常數設定 + 使用者偏好（config.json）的讀寫。

`.env` 只放機密（API Key），非機密的偏好走 `config.json`——兩者分開，
使用者把設定貼給別人看時不會連 Key 一起送出去。
"""

import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(SCRIPT_DIR, ".env")
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
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

# ---- 使用者偏好（config.json）----
#
# language 預設**必須是空字串**，不是 "zh_tw"：填 "zh_tw" 就分不出「他選了
# 繁中」和「他沒選過」，只能再多一個 language_chosen 布林值——兩個欄位描述
# 同一件事，遲早不同步。空字串代表沒選過，首次啟動要跳語言視窗。
DEFAULT_CONFIG = {"language": ""}


def load_config(path: str = CONFIG_PATH) -> dict:
    """讀 config.json。檔案不存在、壞掉、或不是 dict 一律回預設值。

    設定檔讀不起來不該讓工具開不了——大不了當成第一次啟動再問一次語言。
    """
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
    except (OSError, ValueError):
        return cfg
    if isinstance(loaded, dict):
        cfg.update(loaded)
    return cfg


def save_config(cfg: dict, path: str = CONFIG_PATH) -> None:
    """寫 config.json。寫不進去就算了，不拖垮主程式。

    磁碟滿、目錄唯讀、兩個實例同時寫……這些情況下使用者頂多是下次啟動
    要重選一次語言，不值得讓整個工具當掉。
    """
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except OSError:
        pass
