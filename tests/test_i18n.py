"""多語言的防退化測試（unittest + subTest）。

專案的 111 條既有測試全部是 unittest，這裡刻意不引入 pytest——混兩套框架
比多寫幾行 subTest 麻煩得多。

七道防線：

1. 四語 key 集合完全一致
2. 四語 placeholder 逐條一致
3. **主程式不得再出現寫死的中日文**（這條是永久的，擋的不是這次遷移是下一次）
4. 第 3 條的掃描範圍真的涵蓋主程式（豁免清單一寫寬就靜默失效）
5. 沒有任何區域名稱遮蔽翻譯函式 `t`
6. 四語各建置一次 GUI：殘留 key 0 條，且四語真的長得不一樣
7. 送給 Gemini 的 PROMPT 四語逐字相同（轉錄語言跟音訊走，不是介面語言）

外加：首次啟動的語言視窗開得起來、點下去有存檔、第二次不再跳。
"""

import ast
import os
import re
import sys
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import i18n
import main as main_mod
import transcriber
from ui import SnapTranscriptApp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CJK = re.compile(r"[一-鿿぀-ヿ]")
PLACEHOLDER = re.compile(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}")
LANGS = [code for code, _, _ in i18n.LANGUAGES]

# ---- 第 3 條的掃描範圍 ----
#
# ⚠ 不可以照抄 pattern_i18n.py 的 `SRC = .../"src"`：本專案的 .py 在**根目錄**，
# 那樣寫會收集到 0 個檔案、測試照樣綠燈（靜默零覆蓋）。所以掃 ROOT + 排除清單，
# 而且下面第 4 條會 assert 主程式真的在名單裡。
SKIP_DIRS = {"venv", "__pycache__", ".git", ".superpowers", "locales", "tests",
             "docs", "logs", "cache",
             # scripts/ 是給維護者的驗收工具，不是產品 UI；transcript_golden.py
             # 的假逐字稿內容本來就該是中日文（要驗編碼）
             "scripts"}

# 整檔豁免只有一個：語言自稱（「繁體中文」「日本語」）本來就該用各語言自己的
# 說法，而且它們住在 i18n.py 自己身上，沒有更上層可以查。
SKIP_FILES = {"i18n.py"}


# ---- 精確字串豁免集合 ----
#
# **刻意不整檔豁免 ui.py / job.py** —— 那兩個檔是這個工具的主體，整檔放行
# 等於把第 3 條測試關掉。改用「一條一條列、每條附理由」的精確集合：日後有人
# 在 ui.py 加一個寫死的中文按鈕，測試照樣會紅。

# (a) 落進 logs/app.log 的字面。log 是給維護者除錯用的，跟著使用者語言變
#     等於自廢（windows-tool.md 硬性規則）。
LOG_LITERALS = {
    # ui.py — write_log_header 的任務起始行
    "轉錄 ", "補跑 ", "下載 ", "段", "段 | 自動重試:", "開", "關",
    # ui.py — _finalize_log_file 的任務結果行
    "成功", "失敗", "，耗時 ", "分", "秒",
    # ui.py — _abort 的 log_label
    "轉錄中止", "補跑中止",
    # job.py — 錯誤行
    "轉錄中止 -> ", " | HTTP 429 配額用盡",
    "第", "段 上傳Gemini -> ", "段 最終失敗 -> ",
    "重試 ", "手動重試 ",
    # job.py — _mark_failed 的 status（只進 log，不進畫面）
    "切割失敗",
}

# (b) 會被寫進 `<音訊名>_transcript.txt`、或拿去跟檔案裡的值比對的字面。
#     **是資料不是介面文字**（general.md「資料與顯示文字必須分離」）。
DATA_LITERALS = {
    # job.py — _write_output 的段落標頭與失敗佔位符。翻了的話同一個使用者
    # 切過語言前後兩份逐字稿對不起來，他自己的下游腳本也會斷。
    "=== 第 ", " 段（", "[此段轉錄失敗：", "，可於程式內重試]",
    "任務中止，此段尚未處理",
    # job.py — 存進 r.error 的三種內容，同樣會流進上面那個佔位符
    "第 ", " 段切割失敗，請確認 ffmpeg 是否正常運作",
    "，已自動重試 ", " 次仍失敗", "（使用者取消重試）",
    # transcriber.py — 送給 Gemini 的指令。轉錄語言跟著**音訊**走，
    # 接上介面語言的話使用者換個語言就把轉錄結果整個換掉（見第 7 條測試）。
    transcriber.PROMPT,
    # transcriber.py — classify_error() 拿去 `in err_str` 比對的分類鍵。
    # 同時是例外訊息又是查表鍵：一翻就自己把自己查斷，而且不會報錯。
    "Gemini 回傳空白結果（finish_reason: ",
    "），可能因內容審查攔截或無法辨識音訊，請重試",
    "Gemini 伺服器回傳 503", "Gemini 回傳空白結果", "空白結果",
}

EXEMPT_LITERALS = LOG_LITERALS | DATA_LITERALS


def _scannable():
    """要檢查「不得寫死中日文」的檔案清單。"""
    found = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in sorted(filenames):
            if name.endswith(".py") and name not in SKIP_FILES:
                found.append(os.path.join(dirpath, name))
    return sorted(found)


def _hardcoded_cjk(path):
    """回傳 [(行號, 字串)]。docstring 與註解不算——那些是寫給人看的說明。"""
    with open(path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                docs.add(id(body[0].value))
    hits = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and CJK.search(node.value) and id(node) not in docs
                and node.value not in EXEMPT_LITERALS):
            hits.append((node.lineno, node.value))
    return sorted(hits)


# ═══════════════════════════════════════════════════════════════════════
# 1 & 2. 語言檔一致性
# ═══════════════════════════════════════════════════════════════════════

class TestLocaleTables(unittest.TestCase):
    def test_every_language_has_the_same_keys(self):
        """任一語言少一條就紅燈。

        新增語言時漏翻幾條是必然，靠人眼比對 115 條不可能可靠——這條測試就是
        那個「不可能可靠」的替代品。
        """
        base = set(i18n._strings(i18n.FALLBACK_LANG))
        self.assertTrue(base, "母表是空的，locale 載入壞了")
        for lang in LANGS:
            with self.subTest(lang=lang):
                keys = set(i18n._strings(lang))
                self.assertFalse(sorted(base - keys),
                                 f"{lang} 少了：{sorted(base - keys)[:10]}")
                self.assertFalse(sorted(keys - base),
                                 f"{lang} 多了：{sorted(keys - base)[:10]}")

    def test_placeholders_match_across_languages(self):
        """譯文的 {path} 打錯或漏掉時，t() 會 format 失敗並吐出未格式化的原字串——
        畫面上看到 {path} 殘留，不會 crash 所以特別容易漏掉。"""
        base = i18n._strings(i18n.FALLBACK_LANG)
        for lang in LANGS:
            table = i18n._strings(lang)
            for key, src in base.items():
                with self.subTest(lang=lang, key=key):
                    self.assertEqual(
                        set(PLACEHOLDER.findall(src)),
                        set(PLACEHOLDER.findall(table[key])),
                        f"{lang} / {key} 的 placeholder 不一致",
                    )

    def test_t_never_raises_and_never_returns_empty(self):
        """查不到回 key 本身，不回空字串——空白按鈕看不見，gui.btn.x 看得見。"""
        self.assertEqual(i18n.t("no.such.key.at.all"), "no.such.key.at.all")
        # 格式化失敗不可以炸掉整個程式
        self.assertIsInstance(i18n.t("gui.lbl.output", wrong_name="x"), str)

    def test_set_lang_falls_back_for_unknown_codes(self):
        try:
            for bogus in (None, "", "klingon", "zh", "EN"):
                with self.subTest(value=bogus):
                    self.assertEqual(i18n.set_lang(bogus), i18n.DEFAULT_LANG)
        finally:
            i18n.set_lang(i18n.DEFAULT_LANG)


# ═══════════════════════════════════════════════════════════════════════
# 3 & 4. 主程式不得寫死中日文
# ═══════════════════════════════════════════════════════════════════════

class TestNoHardcodedCJK(unittest.TestCase):
    def test_no_hardcoded_cjk(self):
        """介面文字一律走 t()。

        真的需要豁免就加進 LOG_LITERALS / DATA_LITERALS，**但要寫清楚理由**——
        沒理由的豁免等於把這條測試關掉。
        """
        files = _scannable()
        self.assertTrue(files, "掃描範圍是空的，這條測試等於沒跑")
        for path in files:
            with self.subTest(file=os.path.relpath(path, ROOT)):
                hits = _hardcoded_cjk(path)
                self.assertFalse(
                    hits,
                    f"{os.path.basename(path)} 有 {len(hits)} 條寫死的中日文："
                    + "; ".join(f"行 {ln}: {v[:40]!r}" for ln, v in hits[:5]),
                )

    def test_scannable_actually_covers_the_main_program(self):
        """釘住掃描範圍。

        豁免清單一寫寬、或哪天有人把 .py 搬進某個被排除的目錄，第 3 條就會
        靜默失效——測試還是綠的，但什麼都沒檢查。
        """
        names = {os.path.basename(p) for p in _scannable()}
        for must in ("ui.py", "job.py", "main.py", "audio.py", "segments.py",
                     "transcriber.py", "config.py", "logger.py"):
            with self.subTest(file=must):
                self.assertIn(must, names, f"{must} 不在掃描範圍內")


# ═══════════════════════════════════════════════════════════════════════
# 5. 沒有東西遮蔽 t
# ═══════════════════════════════════════════════════════════════════════

class TestNothingShadowsT(unittest.TestCase):
    def test_nothing_shadows_the_translation_function(self):
        """`from i18n import t` 之後，任何叫 `t` 的區域變數／參數／函式都會
        遮蔽翻譯函式，而遮蔽是**靜默**的：後面的 `t("gui.x")` 變成呼叫那個
        物件，不 crash、不報錯，畫面整片變空白或整條功能路徑掛掉。

        本專案 2026-08-16 就有兩處 `t = threading.Thread(...)`（已改名
        worker_thread）。這條測試釘住它不會再長回來。
        """
        for path in _scannable():
            with open(path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())
            offenders = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                     ast.ClassDef)) and node.name == "t":
                    offenders.append((node.lineno, f"def/class t"))
                elif isinstance(node, ast.arg) and node.arg == "t":
                    offenders.append((node.lineno, "參數 t"))
                elif (isinstance(node, ast.Name) and node.id == "t"
                        and isinstance(node.ctx, (ast.Store, ast.Del))):
                    offenders.append((node.lineno, "指派給 t"))
                elif isinstance(node, ast.ExceptHandler) and node.name == "t":
                    offenders.append((node.lineno, "except as t"))
            with self.subTest(file=os.path.relpath(path, ROOT)):
                self.assertFalse(
                    offenders,
                    f"{os.path.basename(path)} 有東西遮蔽翻譯函式 t：{offenders}",
                )


# ═══════════════════════════════════════════════════════════════════════
# 6. 四語 GUI 建置
# ═══════════════════════════════════════════════════════════════════════
#
# ⚠ 不可以每個 test 各建一個 tk.Tk()：Microsoft Store 版 Python 短時間反覆
# 建立／銷毀 Tcl 直譯器會**間歇性**丟 TclError，每次紅的測試都不一樣，看起來
# 完全像被測程式的隨機 bug。整個 module 共用一個隱藏 root，各測試開 Toplevel。
#
# （`SnapTranscriptApp` 收 root 參數、不是 `class App(tk.Tk)`，所以收得下
#   Toplevel，不需要一語言一子行程的解法。）

_ROOT = None
_TK_AVAILABLE = True


def setUpModule():
    global _ROOT, _TK_AVAILABLE
    try:
        _ROOT = tk.Tk()
        _ROOT.withdraw()
    except tk.TclError:
        _TK_AVAILABLE = False


def tearDownModule():
    if _ROOT is not None:
        try:
            _ROOT.destroy()
        except tk.TclError:
            pass


KEY_LIKE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")
PY_VAR = re.compile(r"^PY_VAR\d+$")


def _collect_texts(widget, out):
    """走訪整棵 widget 樹收集顯示文字。

    `cget("text")` 拿不到 Combobox 的 values 與 tk.Text 的內容，兩者都要另外撈
    ——說明視窗的內容常常整片在 Text 裡。
    """
    try:
        txt = widget.cget("text")
        if isinstance(txt, str) and txt.strip():
            out.append(txt)
    except (tk.TclError, TypeError):
        pass
    if isinstance(widget, tk.Text):
        try:
            out.append(widget.get("1.0", "end"))
        except tk.TclError:
            pass
    try:
        values = widget.cget("values")
        if values:
            out.extend(str(v) for v in values)
    except (tk.TclError, TypeError):
        pass
    for child in widget.winfo_children():
        _collect_texts(child, out)


def _build_and_collect(lang):
    """用指定語言建一次主視窗，回傳收集到的顯示文字。"""
    top = tk.Toplevel(_ROOT)
    top.withdraw()
    try:
        with patch("ui.load_config", return_value={"language": lang}):
            SnapTranscriptApp(top)
        texts = []
        _collect_texts(top, texts)
        # Entry / Spinbox 的 cget("text") 會回 PY_VAR0 這種變數名，是雜訊不是漏翻
        return [x for x in texts if not PY_VAR.match(x.strip())]
    finally:
        try:
            top.destroy()
        except tk.TclError:
            pass


@unittest.skipUnless(_TK_AVAILABLE, "沒有可用的 Tcl/Tk")
class TestGuiBuildsInEveryLanguage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not _TK_AVAILABLE:
            return
        cls.texts = {lang: _build_and_collect(lang) for lang in LANGS}

    @classmethod
    def tearDownClass(cls):
        i18n.set_lang(i18n.DEFAULT_LANG)

    def test_no_leftover_keys_in_any_language(self):
        """畫面上出現 `gui.btn.start_transcribe` 這種字串＝漏翻或 key 打錯。"""
        for lang in LANGS:
            with self.subTest(lang=lang):
                leftover = [x for x in self.texts[lang] if KEY_LIKE.match(x.strip())]
                self.assertFalse(leftover, f"{lang} 有殘留的 key：{leftover[:5]}")

    def test_every_language_renders_some_text(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                self.assertGreater(len(self.texts[lang]), 20,
                                   f"{lang} 只收集到 {len(self.texts[lang])} 條，建置可能失敗")

    def test_languages_actually_differ(self):
        """語言真的有切換到。

        ⚠ 門檻不可以寫死絕對值（`assert diff > 10`）：繁中／简中之間天生就有
        好幾條一樣，再加上刻意四語相同的條目（"Language:"、四個語言自稱、
        `▶` 之類），寫死的門檻會誤殺。改用「扣掉四語本來就相同的條目之後，
        差異數至少要有該變條目的一半」動態算。語言完全沒切換時差異是 0，
        照樣抓得到。
        """
        base = self.texts[i18n.FALLBACK_LANG]
        common = set(base)
        for lang in LANGS:
            common &= set(self.texts[lang])       # 四語都一樣的條目
        should_change = [x for x in base if x not in common]
        self.assertTrue(should_change, "四語顯示文字完全相同，語言根本沒切換")
        for lang in LANGS:
            if lang == i18n.FALLBACK_LANG:
                continue
            with self.subTest(lang=lang):
                diff = sum(1 for x in should_change if x not in set(self.texts[lang]))
                self.assertGreaterEqual(
                    diff, len(should_change) // 2,
                    f"{lang} 只有 {diff}/{len(should_change)} 條與繁中不同，"
                    f"語言可能沒有真的切過去",
                )


# ═══════════════════════════════════════════════════════════════════════
# 7. 送給 Gemini 的 PROMPT 不跟介面語言走
# ═══════════════════════════════════════════════════════════════════════

class TestPromptIsDataNotUiText(unittest.TestCase):
    def test_prompt_is_identical_in_every_language(self):
        """轉錄的**內容語言**跟著音訊走，不是介面語言。

        這兩個最容易被順手接在一起（`language=i18n.get_lang()` 看起來太自然
        了），接上去的後果是使用者換個介面語言就把逐字稿整個換掉，而且畫面上
        完全看不出來——要打開逐字稿才知道。
        """
        prompts = {}
        try:
            for lang in LANGS:
                i18n.set_lang(lang)
                prompts[lang] = transcriber.PROMPT
        finally:
            i18n.set_lang(i18n.DEFAULT_LANG)
        for lang in LANGS:
            with self.subTest(lang=lang):
                self.assertEqual(prompts[lang], prompts[i18n.FALLBACK_LANG])

    def test_prompt_is_not_in_any_locale_table(self):
        """PROMPT 不可以哪天被搬進語言檔。"""
        for lang in LANGS:
            with self.subTest(lang=lang):
                self.assertNotIn(transcriber.PROMPT,
                                 set(i18n._strings(lang).values()))


# ═══════════════════════════════════════════════════════════════════════
# 首次啟動的語言視窗
# ═══════════════════════════════════════════════════════════════════════

@unittest.skipUnless(_TK_AVAILABLE, "沒有可用的 Tcl/Tk")
class TestFirstRunLanguageDialog(unittest.TestCase):
    """語言視窗開得起來、點下去有存檔、第二次不再跳。

    ⚠ 用 `after()` 排一個模擬點擊，不要讓 `wait_window` 卡住——沒有人按的話
    測試會掛到 timeout 才失敗，而且看不出原因。
    """

    def setUp(self):
        fd, self.cfg_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.remove(self.cfg_path)          # 讓它「不存在」＝首次啟動

    def tearDown(self):
        if os.path.exists(self.cfg_path):
            os.remove(self.cfg_path)

    def _click_first_language_button(self):
        for child in _ROOT.winfo_children():
            if isinstance(child, tk.Toplevel) and child.title() == "Language":
                for w in child.winfo_children():
                    if w.winfo_class() == "TButton":
                        w.invoke()
                        return
        self.fail("找不到語言視窗，或視窗裡沒有按鈕")

    def test_dialog_shows_saves_and_does_not_show_again(self):
        with patch("main.CONFIG_PATH", self.cfg_path), \
                patch("config.CONFIG_PATH", self.cfg_path):
            _ROOT.after(80, self._click_first_language_button)
            main_mod.pick_language_on_first_run(_ROOT)

            from config import load_config
            cfg = load_config(self.cfg_path)
            self.assertTrue(i18n.is_supported(cfg["language"]),
                            f"沒有存下有效的語言代號：{cfg!r}")
            first_choice = cfg["language"]

            # 第二次：不該再開視窗。沒有排任何點擊，若視窗跳出來就會卡住，
            # 所以排一個「有視窗就 fail」的檢查當保險。
            opened = []

            def _fail_if_dialog():
                for child in _ROOT.winfo_children():
                    if isinstance(child, tk.Toplevel) and child.title() == "Language":
                        opened.append(child)
                        child.destroy()

            _ROOT.after(80, _fail_if_dialog)
            main_mod.pick_language_on_first_run(_ROOT)
            _ROOT.update()
            self.assertFalse(opened, "選過語言之後還是跳出語言視窗")
            self.assertEqual(load_config(self.cfg_path)["language"], first_choice)


if __name__ == "__main__":
    unittest.main()
