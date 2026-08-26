"""
SnapTranscript — 會議音訊逐字稿工具
將音訊檔案分段切割，透過 Gemini AI 生成逐字稿，合併輸出為單一 TXT 檔案。
"""

import tkinter as tk
from tkinter import ttk

import i18n
from config import CONFIG_PATH, load_config, save_config
from ui import SnapTranscriptApp


def show_cth_banner():
    b = "\033[90m"   # 邊框：深灰
    c = "\033[96m"   # CTH 字母：亮青
    y = "\033[93m"   # 署名：金黃
    r = "\033[0m"    # reset

    print(f"{b}/*  ================================  *\\{r}")
    print(f"{b} *                                    *{r}")
    print(f"{b} *    {c}██████╗████████╗██╗  ██╗{b}        *{r}")
    print(f"{b} *   {c}██╔════╝   ██║   ██║  ██║{b}        *{r}")
    print(f"{b} *   {c}██║        ██║   ███████║{b}        *{r}")
    print(f"{b} *   {c}██║        ██║   ██╔══██║{b}        *{r}")
    print(f"{b} *   {c}╚██████╗   ██║   ██║  ██║{b}        *{r}")
    print(f"{b} *    {c}╚═════╝   ╚═╝   ╚═╝  ╚═╝{b}        *{r}")
    print(f"{b} *                                    *{r}")
    print(f"{b} *          {y}created by CTH{b}            *{r}")
    print(f"{b}\\*  ================================  */{r}")
    print()


def pick_language_on_first_run(root: tk.Tk) -> None:
    """首次啟動時問一次語言，選完寫進 config.json，之後不再出現。

    視窗刻意**不翻譯**：這時候還不知道使用者要哪個語言，用任一種當說明都
    在賭。只有一個英文抬頭，其餘全是各語言的自稱，看得懂哪個就點哪個。

    直接關掉視窗＝接受第一個選項並**照樣存檔**——需求是「選完就記住不要再
    跳」，關掉還一直跳才是煩人。選錯了在主視窗右上角的 Language 隨時能改。
    """
    cfg = load_config(CONFIG_PATH)
    if i18n.is_supported(cfg.get("language", "")):
        return                      # 選過了，直接進主畫面

    choices = i18n.available_languages()
    chosen = {"code": choices[0][0]}

    dlg = tk.Toplevel(root)
    dlg.title("Language")
    dlg.resizable(False, False)
    dlg.attributes("-topmost", True)

    ttk.Label(dlg, text="Select your language",
              font=("", 12, "bold")).pack(padx=28, pady=(20, 4))
    ttk.Label(dlg, text="You can change this later in the main window.",
              foreground="#555555").pack(padx=28, pady=(0, 14))

    def _choose(code: str) -> None:
        chosen["code"] = code
        dlg.destroy()

    for code, name in choices:
        ttk.Button(dlg, text=name, width=20,
                   command=lambda c=code: _choose(c)).pack(padx=28, pady=3)
    ttk.Frame(dlg, height=10).pack()

    dlg.update_idletasks()
    x = root.winfo_rootx() + (root.winfo_width() - dlg.winfo_width()) // 2
    y = root.winfo_rooty() + (root.winfo_height() - dlg.winfo_height()) // 3
    dlg.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    dlg.grab_set()
    dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)   # 關掉＝用預設值，照樣存
    root.wait_window(dlg)

    cfg["language"] = chosen["code"]
    save_config(cfg, CONFIG_PATH)


def main():
    show_cth_banner()
    root = tk.Tk()
    # 必須在建 App 之前——App.__init__ 讀 config 決定介面語言
    pick_language_on_first_run(root)
    SnapTranscriptApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
