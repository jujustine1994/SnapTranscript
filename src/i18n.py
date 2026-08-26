"""i18n.py — 介面顯示文字的多語言查表。

用法：
    from i18n import t
    ttk.Button(text=t("gui.btn.start"))

啟動時呼叫一次 set_lang(cfg["language"])，之後全程式共用。

## 設計約束（改這個檔前先讀）

1. **t() 永不 raise、永不回空字串。** 查找順序是
   `目標語言 → 母語言 → key 本身`。最壞情況畫面顯示 `gui.btn.start` 這串
   key，一眼看得出哪裡漏翻；回空字串會變成看不見的按鈕，那才是災難。

2. **機器鍵不進這裡。** 會被寫進檔案、或拿去跟檔案裡的值比對的字串是
   **資料**不是介面文字。本專案的實例：
   - `_transcript.txt` 的段落標頭與失敗佔位符（`job._write_output`）
   - `transcriber.PROMPT`（送給 Gemini 的指令）
   - `transcriber.classify_error` 用來比對的 `"Gemini 回傳空白結果"`

3. **log 檔不吃這裡的翻譯。** log 是給維護者除錯用的，跟著使用者語言變
   等於自廢。`logger.write_log()` / `write_log_header()` 的字面留在
   `ui.py` / `job.py` 呼叫點原地不動，靠 `tests/test_i18n.py` 的
   `LOG_LITERALS` 精確字串豁免集合放行（**不整檔豁免**，否則等於把防退化
   測試關掉）。
"""

from __future__ import annotations

import importlib

# (代號, 下拉選單顯示名, 字型)
#
# 代號     存進 config.json 的值，也是 locales/<代號>.py 的檔名
# 顯示名   用各語言自己的說法，任何語言下使用者都認得出哪個是哪個
# 字型     ui_font() 用；本專案**刻意不呼叫**（見該函式的說明）
LANGUAGES: list[tuple[str, str, str]] = [
    ("zh_tw", "繁體中文", "微軟正黑體"),
    ("zh_cn", "简体中文", "Microsoft YaHei"),
    ("en",    "English",  "Calibri"),
    ("ja",    "日本語",   "Yu Gothic"),
]

DEFAULT_LANG = "zh_tw"

# 找不到 key 時的最終退路。母語言是其他語言的翻譯來源，所以它一定最完整。
FALLBACK_LANG = "zh_tw"

_LANG_CODES = [code for code, _, _ in LANGUAGES]
_current_lang: str = DEFAULT_LANG
_cache: dict[str, dict[str, str]] = {}


def _strings(lang: str) -> dict[str, str]:
    """載入某語言的字串表。載入失敗回空 dict，讓 t() 自己退回 fallback。"""
    if lang in _cache:
        return _cache[lang]
    try:
        mod = importlib.import_module(f"locales.{lang}")
        table = getattr(mod, "STRINGS", {})
    except (ImportError, AttributeError):
        # 語言檔缺失或壞掉不能讓整個程式起不來
        table = {}
    _cache[lang] = table
    return table


def available_languages() -> list[tuple[str, str]]:
    """給選單用：[(代號, 顯示名), ...]，順序即選單順序。"""
    return [(code, name) for code, name, _ in LANGUAGES]


def is_supported(lang: str) -> bool:
    return lang in _LANG_CODES


def set_lang(lang: str | None) -> str:
    """設定目前語言。不認得的代號（含 None、舊 config 的怪值）退回預設。

    回傳實際採用的代號——要顯示「現在是什麼語言」時用回傳值，不要用傳進去
    的參數，兩者在退回時不同。
    """
    global _current_lang
    _current_lang = lang if is_supported(lang or "") else DEFAULT_LANG
    return _current_lang


def get_lang() -> str:
    return _current_lang


def ui_font(lang: str | None = None) -> str:
    """該語言建議的字型。

    ⚠ **本專案刻意不呼叫這個函式。** 現行程式完全沒指定字型（吃 tkinter 在
    Windows 上的預設），指定下去會改變繁體中文既有的外觀，違反「繁中行為
    必須跟改之前完全一樣」。留著是為了日後真的實測出日文假名顯示成豆腐時，
    可以只對 ja 套用而不動其他語言。
    """
    target = lang if is_supported(lang or "") else _current_lang
    for code, _, font in LANGUAGES:
        if code == target:
            return font
    return LANGUAGES[0][2]


def t(key: str, **fmt) -> str:
    """查表。目標語言 → 母語言 → key 本身。

    **fmt 走 str.format，給帶變數的訊息用：
        t("gui.msg.audio_missing", path="C:/x.mp3")

    格式化失敗（譯文的 placeholder 打錯）不 raise，回未格式化的原字串——
    畫面上看到 {path} 殘留，比整個程式當掉好處理。
    """
    s = _strings(_current_lang).get(key)
    if s is None:
        s = _strings(FALLBACK_LANG).get(key)
    if s is None:
        return key
    if not fmt:
        return s
    try:
        return s.format(**fmt)
    except (KeyError, IndexError, ValueError):
        return s
