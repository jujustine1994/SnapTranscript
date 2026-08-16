"""Gemini 轉錄呼叫與錯誤分類。"""

import time

from google import genai

import config
from i18n import t

# ⚠ PROMPT 是**資料不是介面文字**，永遠不跟著介面語言走（見 i18n.py 的設計約束）。
# 它是送給 Gemini 的機器指令，而且第 2 條明寫「依照說話者使用的語言直接轉錄
# 原文」——逐字稿的語言跟著**音訊**走，跟使用者選了什麼介面語言完全無關。
# 接上介面語言的話，使用者換個介面語言就把轉錄結果整個換掉，而且畫面上完全
# 看不出來，要打開逐字稿才知道。
PROMPT = """請仔細聆聽這段音訊，將所有說話內容以原始語言逐字轉錄。

輸出規則：
1. 純文字輸出，不需要時間戳、編號或任何 JSON / Markdown 格式
2. 依照說話者使用的語言直接轉錄原文，不需翻譯
3. 同一說話者的連續發言合併為一個段落，說話者切換時才換段並空一行
4. 每段開頭標註說話者：優先使用音訊中可辨識的真實姓名或職稱（如「財務長：」「主持人：」），無法辨識則使用「說話者 A：」「說話者 B：」等泛用標籤
5. 背景雜音、靜默段、非語言音（笑聲、清喉嚨等）不需輸出
6. 盡力辨識模糊語音，結合前後文補全語意，忠實呈現內容，不要摘要或省略"""


def transcribe_segment(audio_path: str, client: genai.Client, sleep_fn=None) -> str:
    """上傳音訊至 Gemini，取得純文字逐字稿。

    `sleep_fn` 是測試注入點：傳入假的 sleep 就能測輪詢迴圈而不用真的等，
    正式執行時維持 `time.sleep`。
    """
    sleep = sleep_fn or time.sleep
    audio_file = client.files.upload(file=audio_path)
    while audio_file.state.name == "PROCESSING":
        sleep(config.FILE_UPLOAD_POLL_SECONDS)
        audio_file = client.files.get(name=audio_file.name)

    if audio_file.state.name != "ACTIVE":
        # 這條路徑不刪檔：檔案沒進到 ACTIVE，Gemini 端本來就沒有可用的檔案資源，
        # 而 FAILED 狀態的檔案 Google 會自行回收（48 小時內）
        raise Exception(t("err.gemini.file_failed", state=audio_file.state.name))

    try:
        response = client.models.generate_content(
            model=config.MODEL_NAME,
            contents=[PROMPT, audio_file],
        )
    except Exception:
        # 呼叫失敗也要刪雲端檔：不刪的話配額會被卡住的檔案吃掉，
        # 而重試會再上傳一份新的
        client.files.delete(name=audio_file.name)
        raise
    client.files.delete(name=audio_file.name)
    if response.text is None:
        finish_reason = None
        if response.candidates:
            finish_reason = response.candidates[0].finish_reason
        # ⚠ 這條訊息**不可以 i18n 化**：下方 classify_error() 拿
        # 「Gemini 回傳空白結果」這個字面去 `in err_str` 比對，決定這個錯誤
        # 要不要重試。它同時是例外訊息又是分類鍵＝**資料**。一翻就自己把自己
        # 查斷——classify_error 回 None、空白結果不再重試、直接中止整個任務，
        # 而且不會有任何錯誤訊息，測試也抓不到。
        raise Exception(
            f"Gemini 回傳空白結果（finish_reason: {finish_reason}），"
            "可能因內容審查攔截或無法辨識音訊，請重試"
        )
    return response.text.strip()


def is_quota_error(e: Exception) -> bool:
    """判斷是否為 API 配額用盡（429）。這類錯誤重試無用，必須中止。"""
    err = str(e).lower()
    return "429" in err or "quota" in err or "exhausted" in err


def classify_error(e: Exception) -> tuple[str, str] | None:
    """判斷錯誤是否值得重試。

    回傳 (可讀原因, log 用 status)；不值得重試的錯誤回傳 None。
    只依關鍵字判斷並取 status，絕不把例外全文帶出——例外訊息可能挾帶
    URL 或 response body，那些不該落檔（見 ARCHITECTURE.md 落檔紀律）。
    """
    if is_quota_error(e):
        return None
    err_str = str(e)
    if "503" in err_str or "UNAVAILABLE" in err_str:
        return "Gemini 伺服器回傳 503", "503 UNAVAILABLE"
    if "Gemini 回傳空白結果" in err_str:
        return "Gemini 回傳空白結果", "空白結果"
    return None
