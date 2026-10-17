# -*- coding: utf-8 -*-
"""アプリの画面（メイン画面・設定画面）

画面の部品だけを受け持ち、実際の処理は app.App のメソッドを呼びます。
"""
import math
import os
import time
import tkinter as tk
from tkinter import messagebox, ttk

from . import __version__, config
from .keynames import combo_name

# ---------- 色と文字 ----------
BG = "#0F1216"
BAR = "#13171C"
PANEL = "#171B21"
CELL = "#1F252D"
FIELD = "#1B2027"
LINE = "#262C35"
EDGE = "#343B46"
TEXT = "#E8EAED"
SUB = "#C9CED4"
MUTED = "#9AA4AD"
ACCENT = "#FFD75E"
ACCENT_TEXT = "#14161A"
RECV = "#7DBBFF"
RECV_BG = "#17283B"
SENT_BG = "#3A3018"
OK = "#8FE3A1"
OK_BG = "#1C2A1F"
WARN = "#FFC79A"
WARN_BG = "#2B1E14"

FONT = "Yu Gothic UI"
MONO = "Consolas"


def f(size=10, weight="normal"):
    return (FONT, size, weight)


def flat_button(parent, text, command, primary=False, **kw):
    b = tk.Button(parent, text=text, command=command, relief="flat", bd=0, cursor="hand2",
                  font=f(10, "bold" if primary else "normal"), padx=14, pady=8,
                  bg=ACCENT if primary else FIELD, fg=ACCENT_TEXT if primary else TEXT,
                  activebackground="#FFE69A" if primary else CELL,
                  activeforeground=ACCENT_TEXT if primary else TEXT,
                  highlightthickness=1, highlightbackground=ACCENT if primary else EDGE, **kw)
    return b


def check(parent, text, var, command=None, bg=PANEL):
    return tk.Checkbutton(parent, text=text, variable=var, command=command, bg=bg, fg=SUB,
                          selectcolor=FIELD, activebackground=bg, activeforeground=TEXT,
                          font=f(10), cursor="hand2", highlightthickness=0, bd=0)


def card(parent):
    fr = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
    inner = tk.Frame(fr, bg=PANEL)
    inner.pack(fill="both", expand=True, padx=18, pady=16)
    return fr, inner


def chip(parent, text, bg=CELL, fg=SUB):
    return tk.Label(parent, text=text, bg=bg, fg=fg, font=f(9), padx=8, pady=3)


def kbd(parent, text, bg=BAR, big=False):
    if big:
        return tk.Label(parent, text=text.upper(), bg=ACCENT, fg=ACCENT_TEXT, font=(MONO, 13, "bold"),
                        padx=12, pady=5)
    return tk.Label(parent, text=text.upper(), bg=bg, fg=TEXT, font=(MONO, 9, "bold"), padx=7, pady=2,
                    highlightthickness=1, highlightbackground=EDGE)


def setup_style(root):
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except tk.TclError:
        pass
    st.configure("TCombobox", fieldbackground=FIELD, background=FIELD, foreground=TEXT,
                 arrowcolor=TEXT, bordercolor=EDGE, lightcolor=FIELD, darkcolor=FIELD, padding=6)
    st.map("TCombobox", fieldbackground=[("readonly", FIELD)], foreground=[("readonly", TEXT)],
           selectbackground=[("readonly", FIELD)], selectforeground=[("readonly", TEXT)])
    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", ACCENT_TEXT)
    root.option_add("*TCombobox*Listbox.font", f(10))
    st.configure("Vertical.TScrollbar", background=CELL, troughcolor=PANEL, bordercolor=PANEL,
                 arrowcolor=MUTED, lightcolor=CELL, darkcolor=CELL)


# =====================================================================
#  メイン画面
# =====================================================================
class MainWindow:
    def __init__(self, root, app):
        self.root = root
        self.app = app
        self.entries = []          # (種類, 時刻, 名前, 元の文, 訳, メモ)
        self.filter = "all"
        root.title(f"GameChat Translator {__version__}")
        root.configure(bg=BG)
        root.geometry("1180x760")
        root.minsize(860, 600)
        setup_style(root)

        self.voice_var = tk.BooleanVar(value=app.state.voice_enabled)
        self.chat_var = tk.BooleanVar(value=app.state.enabled)

        self._header()
        self._footer()   # 先に下へ置く（ウィンドウを小さくしても下の帯が消えないように）
        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", expand=True, padx=24, pady=20)
        left = tk.Frame(body, bg=BG, width=400)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        self._voice_card(left)
        self._chat_card(left)
        self._log_panel(body)
        self.refresh()

    # ---------- 上の帯 ----------
    def _header(self):
        app = self.app
        h = tk.Frame(self.root, bg=BAR, highlightthickness=1, highlightbackground=LINE)
        h.pack(fill="x")
        row = tk.Frame(h, bg=BAR)
        row.pack(fill="x", padx=24, pady=12)
        tk.Label(row, text="GameChat Translator", bg=BAR, fg=TEXT, font=f(14, "bold")).pack(side="left")
        tk.Label(row, text=f"v{__version__}", bg=BAR, fg=MUTED, font=f(9)).pack(side="left", padx=(6, 18))
        tk.Label(row, text="ゲーム", bg=BAR, fg=MUTED, font=f(9)).pack(side="left", padx=(0, 6))
        self.games = config.list_profiles()
        names = [n for _, n in self.games]
        self.game_box = ttk.Combobox(row, values=names, state="readonly", width=24, font=f(10))
        ids = [g for g, _ in self.games]
        if app.profile["id"] in ids:
            self.game_box.current(ids.index(app.profile["id"]))
        self.game_box.bind("<<ComboboxSelected>>", self._on_game)
        self.game_box.pack(side="left")
        self.pill = tk.Label(row, text="準備中", bg=CELL, fg=SUB, font=f(9, "bold"), padx=10, pady=3)
        self.pill.pack(side="left", padx=14)
        flat_button(row, "設定", self.open_settings).pack(side="right")
        flat_button(row, "動作チェック", app.open_check).pack(side="right", padx=8)
        flat_button(row, "ログ", app.open_log).pack(side="right")

    def _on_game(self, e=None):
        i = self.game_box.current()
        gid = self.games[i][0]
        if gid == self.app.profile["id"]:
            return
        if messagebox.askyesno("ゲームの切り替え",
                               f"「{self.games[i][1]}」に切り替えます。\nアプリを再起動しますか？", parent=self.root):
            self.app.change_game(gid)
        else:
            ids = [g for g, _ in self.games]
            self.game_box.current(ids.index(self.app.profile["id"]))

    # ---------- 自分の発言 ----------
    def _voice_card(self, parent):
        app = self.app
        v = app.settings["voice"]
        fr, c = card(parent)
        fr.pack(fill="x", pady=(0, 16))
        top = tk.Frame(c, bg=PANEL)
        top.pack(fill="x")
        tl = tk.Frame(top, bg=PANEL)
        tl.pack(side="left")
        tk.Label(tl, text="自分の発言", bg=PANEL, fg=TEXT, font=f(12, "bold")).pack(anchor="w")
        tk.Label(tl, text="日本語で話す → 英語でチャットに送信", bg=PANEL, fg=MUTED, font=f(9)).pack(anchor="w")
        check(top, "オン", self.voice_var, lambda: app.set_voice_enabled(self.voice_var.get())).pack(side="right")

        keyrow = tk.Frame(c, bg=PANEL)
        keyrow.pack(fill="x", pady=(14, 10))
        kbd(keyrow, v["hotkey"], big=True).pack(side="left")
        self.rec_label = tk.Label(keyrow, text="押している間だけ録音", bg=PANEL, fg=SUB, font=f(10))
        self.rec_label.pack(side="left", padx=12)

        mrow = tk.Frame(c, bg=PANEL)
        mrow.pack(fill="x")
        self.mic_name = tk.Label(mrow, text="マイク：準備中", bg=PANEL, fg=MUTED, font=f(9), anchor="w")
        self.mic_name.pack(side="left")
        self.mic_db = tk.Label(mrow, text="", bg=PANEL, fg=MUTED, font=(MONO, 9))
        self.mic_db.pack(side="right")
        self.meter = tk.Canvas(c, height=8, bg=LINE, highlightthickness=0)
        self.meter.pack(fill="x", pady=(4, 10))
        self.meter_bar = self.meter.create_rectangle(0, 0, 0, 8, fill=ACCENT, width=0)

        chips = tk.Frame(c, bg=PANEL)
        chips.pack(fill="x")
        names = {"google": "Google", "deepl": "DeepL", "mymemory": "MyMemory", "whisper": "Whisper（ネット不要）"}
        chip(chips, f"翻訳：{names.get(v['translator'], v['translator'])}").pack(side="left", padx=(0, 6))
        self.model_chip = chip(chips, "音声認識：準備中")
        self.model_chip.pack(side="left", padx=(0, 6))
        chip(chips, "自動送信 ON" if v["auto_send"] else "自動送信 OFF").pack(side="left")

    # ---------- 相手のチャット ----------
    def _chat_card(self, parent):
        app = self.app
        ct = app.settings["chat_translate"]
        fr, c = card(parent)
        fr.pack(fill="x")
        top = tk.Frame(c, bg=PANEL)
        top.pack(fill="x")
        tl = tk.Frame(top, bg=PANEL)
        tl.pack(side="left")
        tk.Label(tl, text="相手のチャット", bg=PANEL, fg=TEXT, font=f(12, "bold")).pack(anchor="w")
        tk.Label(tl, text="画面のテキストチャットを読み取り → 日本語で表示", bg=PANEL, fg=MUTED,
                 font=f(9)).pack(anchor="w")
        check(top, "オン", self.chat_var, lambda: app.set_chat_enabled(self.chat_var.get())).pack(side="right")

        grid = tk.Frame(c, bg=PANEL)
        grid.pack(fill="x", pady=(14, 12))
        grid.columnconfigure(0, weight=1, uniform="g")
        grid.columnconfigure(1, weight=1, uniform="g")
        self.info = {}
        names = {"google": "Google", "deepl": "DeepL", "mymemory": "MyMemory"}
        cells = [("region", "読み取る範囲", "未設定"), ("capture", "撮影方法", "準備中"),
                 ("langs", "翻訳する言語", "中国語・英語 ⇒ 日本語"),
                 ("engine", "翻訳", names.get(ct["translator"], ct["translator"]))]
        for i, (key, label, val) in enumerate(cells):
            cell = tk.Frame(grid, bg=CELL)
            cell.grid(row=i // 2, column=i % 2, sticky="nsew", padx=(0 if i % 2 == 0 else 5, 5 if i % 2 == 0 else 0),
                      pady=4)
            tk.Label(cell, text=label, bg=CELL, fg=MUTED, font=f(8)).pack(anchor="w", padx=10, pady=(7, 0))
            lb = tk.Label(cell, text=val, bg=CELL, fg=TEXT, font=f(10), anchor="w")
            lb.pack(anchor="w", padx=10, pady=(0, 7))
            self.info[key] = lb

        btns = tk.Frame(c, bg=PANEL)
        btns.pack(fill="x")
        flat_button(btns, f"範囲を選び直す（{ct['region_key'].upper()}）",
                    lambda: app.request_select(delay=3)).pack(side="left", fill="x", expand=True, padx=(0, 5))
        flat_button(btns, f"表示枠を動かす（{app.settings['overlay']['move_key'].upper()}）",
                    app.toggle_move).pack(side="left", fill="x", expand=True, padx=(5, 0))

    # ---------- 会話ログ ----------
    def _log_panel(self, parent):
        fr = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        fr.pack(side="left", fill="both", expand=True, padx=(20, 0))
        top = tk.Frame(fr, bg=PANEL)
        top.pack(fill="x", padx=18, pady=12)
        tk.Label(top, text="会話ログ", bg=PANEL, fg=TEXT, font=f(12, "bold")).pack(side="left")
        self.filter_btns = {}
        for key, label in (("recv", "受信"), ("sent", "送信"), ("all", "すべて")):
            b = tk.Button(top, text=label, relief="flat", bd=0, cursor="hand2", font=f(9), padx=12, pady=4,
                          command=lambda k=key: self.set_filter(k))
            b.pack(side="right", padx=3)
            self.filter_btns[key] = b
        tk.Frame(fr, bg=LINE, height=1).pack(fill="x")

        wrap = tk.Frame(fr, bg=PANEL)
        wrap.pack(fill="both", expand=True)
        self.text = tk.Text(wrap, bg=PANEL, fg=TEXT, relief="flat", bd=0, wrap="word", font=f(11),
                            padx=18, pady=10, cursor="arrow", highlightthickness=0, spacing1=2, spacing3=2)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        t = self.text
        t.tag_configure("sent_badge", background=SENT_BG, foreground=ACCENT, font=f(8, "bold"))
        t.tag_configure("recv_badge", background=RECV_BG, foreground=RECV, font=f(8, "bold"))
        t.tag_configure("time", foreground=MUTED, font=(MONO, 9))
        t.tag_configure("src", foreground=MUTED, font=f(10))
        t.tag_configure("name", foreground=ACCENT, font=f(10, "bold"))
        t.tag_configure("dst", foreground=TEXT, font=f(12))
        t.tag_configure("note", foreground=MUTED, font=f(8))
        t.tag_configure("sep", foreground=LINE, font=f(4))
        t.tag_configure("empty", foreground=MUTED, font=f(10))
        self.set_filter("all")

    def set_filter(self, key):
        self.filter = key
        for k, b in self.filter_btns.items():
            on = k == key
            b.configure(bg=ACCENT if on else PANEL, fg=ACCENT_TEXT if on else SUB,
                        activebackground=ACCENT if on else CELL)
        self._render()

    def add_entry(self, kind, name, src, dst, note=""):
        self.entries.append((kind, time.strftime("%H:%M"), name, src, dst, note))
        if len(self.entries) > 300:
            self.entries = self.entries[-300:]
        if self.filter in ("all", kind):
            self._write(self.entries[-1])
            self.text.see("end")

    def _render(self):
        t = self.text
        t.configure(state="normal")
        t.delete("1.0", "end")
        t.configure(state="disabled")
        shown = [e for e in self.entries if self.filter in ("all", e[0])]
        if not shown:
            t.configure(state="normal")
            t.insert("end", "\nここに送信した発言と、翻訳した相手の発言が並びます。\n"
                            "F8 を押しながら話すか、相手のチャットを待ってください。", "empty")
            t.configure(state="disabled")
            return
        for e in shown:
            self._write(e)
        t.see("end")

    def _write(self, e):
        kind, hhmm, name, src, dst, note = e
        t = self.text
        t.configure(state="normal")
        if t.get("1.0", "end").strip().startswith("ここに送信"):
            t.delete("1.0", "end")
        t.insert("end", " 送信 " if kind == "sent" else " 受信 ", f"{kind}_badge")
        t.insert("end", "  " + hhmm + "\n", "time")
        if name:
            t.insert("end", name + ": ", "name")
        t.insert("end", (src or "") + "\n", "src")
        t.insert("end", dst, "dst")
        if note:
            t.insert("end", "   " + note, "note")
        t.insert("end", "\n" + "─" * 60 + "\n", "sep")
        t.configure(state="disabled")

    # ---------- 下の帯 ----------
    def _footer(self):
        s = self.app.settings
        bar = tk.Frame(self.root, bg=BAR, highlightthickness=1, highlightbackground=LINE)
        bar.pack(fill="x", side="bottom")
        row = tk.Frame(bar, bg=BAR)
        row.pack(fill="x", padx=24, pady=8)
        items = [(s["overlay"]["move_key"], "表示枠を動かす"), (s["voice"]["hotkey"], "押しながら話す"),
                 (s["chat_translate"]["region_key"], "チャット欄の範囲"),
                 (s["chat_translate"]["toggle_key"], "翻訳表示オン/オフ"),
                 (s["dictionary"]["reload_key"], "辞書を読み直す")]
        for key, label in items:
            if not key:
                continue
            kbd(row, key).pack(side="left")
            tk.Label(row, text=label, bg=BAR, fg=SUB, font=f(9)).pack(side="left", padx=(6, 16))
        self.notice = tk.Label(row, text="", bg=BAR, fg=MUTED, font=f(9), anchor="e")
        self.notice.pack(side="right", fill="x", expand=True)

    # ---------- 定期更新 ----------
    def set_notice(self, text):
        text = " ".join(text.split())
        if len(text) > 90:
            text = text[:88] + "…"
        self.notice.configure(text=text, fg=WARN if text.startswith(("※", "エラー", "  エラー")) else MUTED)

    def set_recording(self, on):
        self.rec_label.configure(text="● 録音中…" if on else "押している間だけ録音",
                                 fg="#FF8A3D" if on else SUB, font=f(10, "bold" if on else "normal"))

    def refresh(self):
        app = self.app
        st = app.state
        self.voice_var.set(st.voice_enabled)
        self.chat_var.set(st.enabled)
        # 状態の表示
        if not app.ready:
            self.pill.configure(text="準備中…", bg=CELL, fg=SUB)
        elif app.error:
            self.pill.configure(text="一部が動いていません", bg=WARN_BG, fg=WARN)
        elif not st.voice_enabled and not st.enabled:
            self.pill.configure(text="停止中", bg=CELL, fg=SUB)
        else:
            self.pill.configure(text="● 動作中", bg=OK_BG, fg=OK)
        r = st.region
        self.info["region"].configure(text=f"設定済み（{r['width']}×{r['height']}）" if r else "未設定（F9 で選ぶ）")
        self.info["capture"].configure(text={"dxcam": "dxcam（フルスクリーン可）", "mss": "mss（ウィンドウ向け）",
                                             "off": "オフ", "error": "開始できませんでした"}
                                       .get(app.capture_method, "準備中（範囲を選ぶと開始）" if not st.region
                                            else "準備中"))
        self.model_chip.configure(text=f"音声認識：{app.voice_info}")
        # マイクの音量
        mic = app.mic
        if mic is not None:
            self.mic_name.configure(text=f"マイク：{app.mic_name}")
            lv = getattr(mic, "level", 0.0)
            db = 20 * math.log10(lv) if lv > 0 else -99
            w = self.meter.winfo_width()
            frac = max(0.0, min(1.0, (db + 60) / 60))
            self.meter.coords(self.meter_bar, 0, 0, int(w * frac), 8)
            self.mic_db.configure(text=f"{db:.0f} dB" if db > -99 else "")
        self.root.after(100, self.refresh)

    def open_settings(self):
        SettingsDialog(self.root, self.app)


# =====================================================================
#  設定画面
# =====================================================================
class KeyButton:
    """押すと「キーを押してください」になり、次に押したキーを覚えるボタン"""

    def __init__(self, parent, value, allow_mods=True, allow_mouse=False, bg=CELL):
        self.value = value
        self.allow_mods = allow_mods
        self.allow_mouse = allow_mouse
        self.waiting = False
        self.btn = tk.Button(parent, text=value.upper() or "（なし）", width=12, relief="flat", bd=0,
                             cursor="hand2", font=(MONO, 11, "bold"), bg=FIELD, fg=TEXT,
                             activebackground=CELL, activeforeground=TEXT, highlightthickness=1,
                             highlightbackground=EDGE, command=self.start)

    def start(self):
        self.waiting = True
        self.btn.configure(text="キーを押す…", fg=ACCENT, highlightbackground=ACCENT)
        top = self.btn.winfo_toplevel()
        top.bind("<KeyPress>", self._on_key)
        self.btn.focus_set()
        if self.allow_mouse:
            self._poll_mouse()

    def _poll_mouse(self):
        if not self.waiting:
            return
        try:
            from .winkeys import is_down
            for vk, name in ((0x05, "mouse4"), (0x06, "mouse5")):
                if is_down(vk):
                    self._set(name)
                    return
        except Exception:
            pass
        self.btn.after(50, self._poll_mouse)

    def _on_key(self, e):
        if not self.waiting:
            return
        if e.keysym.lower() == "escape":
            self._set(self.value)
            return "break"
        name = combo_name(e.keysym, e.state, self.allow_mods)
        if name:
            self._set(name)
        return "break"

    def _set(self, name):
        self.waiting = False
        self.value = name
        self.btn.configure(text=name.upper(), fg=TEXT, highlightbackground=EDGE)
        try:
            self.btn.winfo_toplevel().unbind("<KeyPress>")
        except tk.TclError:
            pass


class SettingsDialog:
    ENGINES_VOICE = [("google", "Google（無料・辞書が効く）"), ("deepl", "DeepL（自然な訳・APIキーが必要）"),
                     ("mymemory", "MyMemory（無料・1日の上限あり）"), ("whisper", "Whisper（ネット不要・辞書なし）")]
    ENGINES_CHAT = [("google", "Google（無料）"), ("deepl", "DeepL（APIキーが必要）"),
                    ("mymemory", "MyMemory（無料・1日の上限あり）")]
    MODELS = [("auto", "自動（GPUなら medium、なければ small）"), ("small", "small（軽い）"),
              ("medium", "medium（標準）"), ("large-v3", "large-v3（高精度・重い）")]
    POSITIONS = [("above", "チャット欄の上"), ("below", "チャット欄の下"), ("right", "チャット欄の右")]

    def __init__(self, root, app):
        self.app = app
        s = app.settings
        self.win = tk.Toplevel(root)
        self.win.title("設定 - GameChat Translator")
        self.win.configure(bg=BG)
        self.win.geometry("860x720")
        self.win.transient(root)
        self.win.after(150, self._grab)

        head = tk.Frame(self.win, bg=BAR, highlightthickness=1, highlightbackground=LINE)
        head.pack(fill="x")
        hr = tk.Frame(head, bg=BAR)
        hr.pack(fill="x", padx=22, pady=12)
        tk.Label(hr, text="設定", bg=BAR, fg=TEXT, font=f(14, "bold")).pack(side="left")
        flat_button(hr, "保存して再起動", self.save, primary=True).pack(side="right")
        flat_button(hr, "キャンセル", self.win.destroy).pack(side="right", padx=8)

        # スクロールできる中身
        outer = tk.Frame(self.win, bg=BG)
        outer.pack(fill="both", expand=True)
        cv = tk.Canvas(outer, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=cv.yview)
        self.body = tk.Frame(cv, bg=BG)
        self.body.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        body_id = cv.create_window((0, 0), window=self.body, anchor="nw")
        cv.bind("<Configure>", lambda e: cv.itemconfigure(body_id, width=e.width))
        cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.win.bind("<MouseWheel>", lambda e: cv.yview_scroll(int(-e.delta / 120), "units"))

        v, ct, ov, dc = s["voice"], s["chat_translate"], s["overlay"], s["dictionary"]

        # --- 自分の発言 ---
        c = self._section("自分の発言（音声 → 英語）")
        self.voice_enabled = tk.BooleanVar(value=v["enabled"])
        self._toggle(c, "使う", "オフにすると音声認識を読み込まず、起動が速く軽くなります", self.voice_enabled)
        devices = app.list_mics()
        self.mic_choices = [("-1", "Windows の既定のマイク")] + [(name, name) for _, name, _ in devices]
        cur_mic = str(v["input_device"])
        if cur_mic not in [k for k, _ in self.mic_choices]:
            for i, name, _ in devices:  # 番号で指定されていた場合
                if str(i) == cur_mic:
                    cur_mic = name
        self.mic = self._combo(c, "マイク", self.mic_choices, cur_mic)
        self.voice_engine = self._combo(c, "翻訳方法", self.ENGINES_VOICE, v["translator"])
        self.model = self._combo(c, "音声認識モデル", self.MODELS, v["model"])
        self.auto_send = tk.BooleanVar(value=v["auto_send"])
        self._toggle(c, "自動で送信する", "オフにすると入力だけして、送信は自分で Enter", self.auto_send)
        self.beep = tk.BooleanVar(value=v["beep"])
        self._toggle(c, "効果音", "録音開始・終了・送信のときに鳴らす", self.beep)
        self.vad = self._scale(c, "声を拾う感度（小さいほど小さな声も拾う）", 0.1, 0.9, 0.1, v["vad_threshold"])

        # --- 相手のチャット ---
        c = self._section("相手のチャット（中国語・英語 ⇒ 日本語）")
        self.chat_enabled = tk.BooleanVar(value=ct["enabled"])
        self._toggle(c, "使う", "画面のテキストチャットを読み取って翻訳する", self.chat_enabled)
        self.chat_engine = self._combo(c, "翻訳方法", self.ENGINES_CHAT, ct["translator"])
        self.my_name = self._entry(c, "自分のプレイヤー名（自分の発言は翻訳しない）", ct["my_name"])
        self.deepl = self._entry(c, "DeepL APIキー（DeepL を使うときだけ）", s["api"]["deepl_key"], secret=True)

        # --- 翻訳の表示 ---
        c = self._section("翻訳の表示")
        self.position = self._combo(c, "表示する場所（F7 で動かした場合はそちらが優先）", self.POSITIONS, ov["position"])
        self.font_size = self._scale(c, "文字の大きさ", 8, 40, 1, ov["font_size"])
        self.seconds = self._scale(c, "表示する秒数", 5, 60, 1, ov["seconds"])
        self.alpha = self._scale(c, "不透明度", 0.3, 1.0, 0.05, ov["alpha"])
        self.show_original = tk.BooleanVar(value=ov["show_original"])
        self._toggle(c, "元の文も一緒に表示", "訳の下に、小さく英語・中国語の原文を出す", self.show_original)
        flat_button(c, "表示枠の位置を自動に戻す", self.reset_overlay).pack(anchor="w", pady=(6, 0))

        # --- ショートカット ---
        c = self._section("ショートカット")
        tk.Label(c, text="ボタンを押してから、使いたいキーを押してください（Esc で取り消し）。\n"
                         "F7・F9〜F11 は Alt・Windows キーを押しているときは反応しません（NVIDIA の Alt+F10 などと重ならないように）。",
                 bg=PANEL, fg=MUTED, font=f(9), justify="left").pack(anchor="w", pady=(0, 8))
        self.keys = {}
        for sec, key, label, mods, mouse in (
                ("voice", "hotkey", "押しながら話す（マウスのサイドボタンも可）", False, True),
                ("overlay", "move_key", "表示枠を動かす", True, False),
                ("chat_translate", "region_key", "チャット欄の範囲を選ぶ", True, False),
                ("chat_translate", "toggle_key", "翻訳表示オン/オフ", True, False),
                ("dictionary", "reload_key", "辞書を読み直す", True, False)):
            row = tk.Frame(c, bg=CELL)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=label, bg=CELL, fg=TEXT, font=f(10)).pack(side="left", padx=12, pady=8)
            kb = KeyButton(row, s[sec][key], allow_mods=mods, allow_mouse=mouse)
            kb.btn.pack(side="right", padx=8, pady=6)
            self.keys[(sec, key)] = kb

        # --- 辞書 ---
        c = self._section("辞書")
        tk.Label(c, text="自分用の辞書は Excel やメモ帳で編集できます（UTF-8 で保存）。編集後は F11 で読み直し。",
                 bg=PANEL, fg=MUTED, font=f(9), justify="left").pack(anchor="w", pady=(0, 8))
        row = tk.Frame(c, bg=PANEL)
        row.pack(fill="x")
        for label, path in (("スラング辞書（相手の発言）", os.path.join(config.USER_DIR, "slang.csv")),
                            ("用語辞書（自分の発言）", os.path.join(config.USER_DIR, "speech.csv")),
                            ("無視リスト", os.path.join(config.USER_DIR, "ignore.txt"))):
            flat_button(row, label, lambda p=path: app.open_path(p)).pack(side="left", padx=(0, 8))
        flat_button(c, "辞書フォルダを開く", lambda: app.open_path(config.DICT_DIR)).pack(anchor="w", pady=(8, 0))

        tk.Frame(self.body, bg=BG, height=20).pack()

    def _grab(self):
        try:
            self.win.grab_set()   # 設定画面を開いている間は、メイン画面を操作できないようにする
        except tk.TclError:
            pass

    # ---------- 部品 ----------
    def _section(self, title):
        fr, c = card(self.body)
        fr.pack(fill="x", padx=22, pady=(16, 0))
        tk.Label(c, text=title, bg=PANEL, fg=TEXT, font=f(12, "bold")).pack(anchor="w", pady=(0, 10))
        return c

    def _toggle(self, parent, title, sub, var):
        row = tk.Frame(parent, bg=CELL)
        row.pack(fill="x", pady=3)
        tx = tk.Frame(row, bg=CELL)
        tx.pack(side="left", padx=12, pady=7)
        tk.Label(tx, text=title, bg=CELL, fg=TEXT, font=f(10)).pack(anchor="w")
        tk.Label(tx, text=sub, bg=CELL, fg=MUTED, font=f(8)).pack(anchor="w")
        check(row, "", var, bg=CELL).pack(side="right", padx=12)

    def _combo(self, parent, label, choices, current):
        tk.Label(parent, text=label, bg=PANEL, fg=SUB, font=f(9)).pack(anchor="w", pady=(6, 2))
        box = ttk.Combobox(parent, values=[t for _, t in choices], state="readonly", font=f(10))
        keys = [k for k, _ in choices]
        box.current(keys.index(str(current)) if str(current) in keys else 0)
        box.pack(fill="x")
        box._choices = choices
        return box

    @staticmethod
    def _combo_value(box):
        return box._choices[box.current()][0]

    def _entry(self, parent, label, value, secret=False):
        tk.Label(parent, text=label, bg=PANEL, fg=SUB, font=f(9)).pack(anchor="w", pady=(6, 2))
        e = tk.Entry(parent, bg=FIELD, fg=TEXT, insertbackground=TEXT, relief="flat", font=f(10),
                     highlightthickness=1, highlightbackground=EDGE, highlightcolor=ACCENT,
                     show="●" if secret else "")
        e.insert(0, value or "")
        e.pack(fill="x", ipady=6)
        return e

    def _scale(self, parent, label, lo, hi, step, value):
        tk.Label(parent, text=label, bg=PANEL, fg=SUB, font=f(9)).pack(anchor="w", pady=(8, 0))
        var = tk.DoubleVar(value=value)
        sc = tk.Scale(parent, from_=lo, to=hi, resolution=step, orient="horizontal", variable=var,
                      bg=PANEL, fg=TEXT, troughcolor=LINE, highlightthickness=0, bd=0, sliderrelief="flat",
                      activebackground=ACCENT, font=(MONO, 9), length=400)
        sc.pack(fill="x")
        return var

    def reset_overlay(self):
        self.app.reset_overlay_position()
        messagebox.showinfo("翻訳の表示", "表示枠の位置を自動（チャット欄の近く）に戻しました。", parent=self.win)

    # ---------- 保存 ----------
    def save(self):
        mic = self._combo_value(self.mic)
        changes = {
            ("voice", "enabled"): self.voice_enabled.get(),
            ("voice", "input_device"): -1 if mic == "-1" else mic,
            ("voice", "translator"): self._combo_value(self.voice_engine),
            ("voice", "model"): self._combo_value(self.model),
            ("voice", "auto_send"): self.auto_send.get(),
            ("voice", "beep"): self.beep.get(),
            ("voice", "vad_threshold"): round(self.vad.get(), 2),
            ("chat_translate", "enabled"): self.chat_enabled.get(),
            ("chat_translate", "translator"): self._combo_value(self.chat_engine),
            ("chat_translate", "my_name"): self.my_name.get().strip(),
            ("api", "deepl_key"): self.deepl.get().strip(),
            ("overlay", "position"): self._combo_value(self.position),
            ("overlay", "font_size"): int(self.font_size.get()),
            ("overlay", "seconds"): int(self.seconds.get()),
            ("overlay", "alpha"): round(self.alpha.get(), 2),
            ("overlay", "show_original"): self.show_original.get(),
        }
        for (sec, key), kb in self.keys.items():
            changes[(sec, key)] = kb.value
        if changes[("voice", "translator")] == "deepl" or changes[("chat_translate", "translator")] == "deepl":
            if not changes[("api", "deepl_key")]:
                if not messagebox.askyesno("DeepL", "DeepL の APIキーが空です。このままだと Google翻訳が使われます。\n保存しますか？",
                                           parent=self.win):
                    return
        err = self.app.save_settings(changes)
        if err:
            messagebox.showerror("設定", err, parent=self.win)
            return
        self.win.destroy()
        self.app.restart()
