# -*- coding: utf-8 -*-
"""画面に重ねる翻訳表示と、チャット欄の範囲選択"""
import time
import tkinter as tk

from .winkeys import set_click_through

BG = "#101418"
TEXT_COLOR = "#ffffff"
NAME_COLOR = "#ffd75e"
ORIG_COLOR = "#9aa4ad"


MOVE_BORDER = "#ffd75e"


class Overlay:
    """翻訳の表示枠。移動モード（F7）ではマウスで動かせる

    移動モード中:
      ドラッグ       … 場所を動かす
      ホイール       … 文字の大きさ
      Shift+ホイール … 枠の幅
      右クリック     … 自動の位置（チャット欄の近く）に戻す
    """

    def __init__(self, root, state, cfg, game="", on_save=None, saved=None):
        self.state = state
        self.cfg = cfg  # settings の [overlay]
        self.game = game
        self.on_save = on_save  # 位置を保存する関数 (dict or None)
        saved = saved or {}
        self.custom_xy = (saved["x"], saved["y"]) if "x" in saved and "y" in saved else None
        self.font_size = int(saved.get("font_size") or cfg["font_size"])
        self.width = int(saved.get("width") or cfg.get("width") or 0)
        self.moving = False
        self._drag = None

        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.0)
        self.win.configure(bg=BG, highlightthickness=0, highlightbackground=MOVE_BORDER)
        self.frame = tk.Frame(self.win, bg=BG, padx=10, pady=6)
        self.frame.pack(fill="both", expand=True)
        self.hint = None
        self.items = []  # (消える時刻, 部品, 名前, 訳, 元の文)
        self.win.geometry("10x10+0+0")
        self.win.update_idletasks()
        set_click_through(self.win, True)

        for w in (self.win, self.frame):
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)
            w.bind("<ButtonRelease-1>", self._drag_end)
            w.bind("<MouseWheel>", self._wheel)
            w.bind("<Button-3>", self._reset)

    # ---------- 表示 ----------
    def _width(self):
        if self.width:
            return self.width
        r = self.state.region
        w = r["width"] if r else 600
        return max(360, min(w, 900))

    def _make_box(self, name, text, orig):
        c = self.cfg
        w = self._width()
        font, size = c["font"], self.font_size
        box = tk.Frame(self.frame, bg=BG)
        line = tk.Frame(box, bg=BG)
        if name:
            tk.Label(line, text=f"{name}:", fg=NAME_COLOR, bg=BG,
                     font=(font, size, "bold")).pack(side="left", anchor="n")
        tk.Label(line, text=text, fg=TEXT_COLOR, bg=BG, font=(font, size),
                 wraplength=w - (160 if name else 30), justify="left",
                 anchor="w").pack(side="left", fill="x")
        line.pack(fill="x", anchor="w")
        if c["show_original"] and orig and orig != text:
            tk.Label(box, text=orig, fg=ORIG_COLOR, bg=BG, font=(font, max(9, size - 4)),
                     wraplength=w - 30, justify="left", anchor="w").pack(fill="x")
        # 文字の上でもドラッグ・ホイールが効くように
        for wdg in [box, line] + list(line.winfo_children()) + list(box.winfo_children()):
            wdg.bind("<ButtonPress-1>", self._drag_start)
            wdg.bind("<B1-Motion>", self._drag_move)
            wdg.bind("<ButtonRelease-1>", self._drag_end)
            wdg.bind("<MouseWheel>", self._wheel)
            wdg.bind("<Button-3>", self._reset)
        box.pack(fill="x", anchor="w", pady=1)
        return box

    def add(self, name, text, orig):
        box = self._make_box(name, text, orig)
        self.items.append([time.time() + self.cfg["seconds"], box, name, text, orig])
        while len(self.items) > self.cfg["max_lines"]:
            self.items.pop(0)[1].destroy()
        self._layout()

    def _rebuild(self):
        """文字の大きさ・幅を変えたときに作り直す"""
        for it in self.items:
            it[1].destroy()
            it[1] = self._make_box(it[2], it[3], it[4])
        if self.hint is not None:
            self.hint.destroy()
            self.hint = None
            self._show_hint()
        self._layout()

    def tick(self):
        if self.moving:
            return  # 移動中は消さない
        now = time.time()
        changed = False
        while self.items and self.items[0][0] < now:
            self.items.pop(0)[1].destroy()
            changed = True
        if changed:
            self._layout()

    def _auto_xy(self, h):
        r = self.state.region
        pos = self.cfg["position"]
        if not r:
            return 40, 40
        if pos == "right":
            return r["left"] + r["width"] + 10, r["top"]
        if pos == "below":
            return r["left"], r["top"] + r["height"] + 8
        y = r["top"] - h - 8
        if y < 0:
            y = r["top"] + r["height"] + 8
        return r["left"], y

    def _layout(self):
        if not self.items and not self.moving:
            self.win.attributes("-alpha", 0.0)
            return
        w = self._width()
        self.win.update_idletasks()
        h = self.frame.winfo_reqheight() + (6 if self.moving else 0)
        x, y = self.custom_xy if self.custom_xy else self._auto_xy(h)
        self.win.geometry(f"{w}x{h}+{int(x)}+{int(y)}")
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", max(self.cfg["alpha"], 0.9) if self.moving else self.cfg["alpha"])

    # ---------- 移動モード ----------
    def _show_hint(self):
        self.hint = tk.Label(
            self.frame, bg=BG, fg=MOVE_BORDER, justify="left", anchor="w",
            font=(self.cfg["font"], max(10, self.font_size - 2), "bold"),
            text="【移動モード】ドラッグで移動 ／ ホイールで文字の大きさ ／ Shift+ホイールで幅\n"
                 "右クリックで自動の位置に戻す ／ もう一度キーを押すと確定")
        self.hint.pack(fill="x", anchor="w", before=self.frame.winfo_children()[0]
                       if self.frame.winfo_children() else None)
        for ev, fn in (("<ButtonPress-1>", self._drag_start), ("<B1-Motion>", self._drag_move),
                       ("<ButtonRelease-1>", self._drag_end), ("<MouseWheel>", self._wheel),
                       ("<Button-3>", self._reset)):
            self.hint.bind(ev, fn)

    def toggle_move(self):
        self.moving = not self.moving
        if self.moving:
            if not self.items:
                self.add("Player", "（翻訳はここに表示されます）", "")
                self.items[-1][0] = time.time() + 1  # 確定後すぐ消える見本
            self._show_hint()
            self.win.configure(highlightthickness=3)
            set_click_through(self.win, False)
            self._layout()
        else:
            if self.hint is not None:
                self.hint.destroy()
                self.hint = None
            self.win.configure(highlightthickness=0)
            set_click_through(self.win, True)
            self._save()
            self._layout()
        return self.moving

    def _save(self):
        if not self.on_save:
            return
        if self.custom_xy or self.width or self.font_size != self.cfg["font_size"]:
            pos = {"font_size": self.font_size}
            if self.custom_xy:
                pos["x"], pos["y"] = int(self.custom_xy[0]), int(self.custom_xy[1])
            if self.width:
                pos["width"] = self.width
            self.on_save(pos)
        else:
            self.on_save(None)

    def _drag_start(self, e):
        if self.moving:
            self._drag = (e.x_root - self.win.winfo_x(), e.y_root - self.win.winfo_y())

    def _drag_move(self, e):
        if self.moving and self._drag:
            self.custom_xy = (e.x_root - self._drag[0], e.y_root - self._drag[1])
            self.win.geometry(f"+{int(self.custom_xy[0])}+{int(self.custom_xy[1])}")

    def _drag_end(self, e):
        self._drag = None

    def _wheel(self, e):
        if not self.moving:
            return
        step = 1 if e.delta > 0 else -1
        if e.state & 0x0001:  # Shift: 幅
            self.width = max(240, min(1600, self._width() + step * 40))
        else:
            self.font_size = max(8, min(40, self.font_size + step))
        self._rebuild()

    def _reset(self, e=None):
        if self.moving:
            self.custom_xy = None
            self.width = 0
            self.font_size = self.cfg["font_size"]
            self._rebuild()


def select_region(root, img_bgr, mon, font, on_done):
    """撮っておいた画面（img_bgr）を暗くして表示し、ドラッグで囲んだ範囲を on_done に渡す"""
    from PIL import Image, ImageEnhance, ImageTk

    img = Image.fromarray(img_bgr[:, :, ::-1].copy())
    if img.size != (mon["width"], mon["height"]):
        img = img.resize((mon["width"], mon["height"]))
    img = ImageEnhance.Brightness(img).enhance(0.55)

    top = tk.Toplevel(root)
    top.overrideredirect(True)
    top.attributes("-topmost", True)
    top.geometry(f"{mon['width']}x{mon['height']}+{mon['left']}+{mon['top']}")
    canvas = tk.Canvas(top, highlightthickness=0, cursor="crosshair")
    canvas.pack(fill="both", expand=True)
    photo = ImageTk.PhotoImage(img)
    canvas.create_image(0, 0, image=photo, anchor="nw")
    canvas.image = photo
    canvas.create_text(mon["width"] // 2, 40, fill="white", font=(font, 20, "bold"),
                       text="チャット欄（相手の発言が表示される所）をドラッグで囲んでください　"
                            "Esc / 右クリック = キャンセル")
    rect = {"id": None, "x": 0, "y": 0}

    def press(e):
        rect["x"], rect["y"] = e.x, e.y
        if rect["id"]:
            canvas.delete(rect["id"])
        rect["id"] = canvas.create_rectangle(e.x, e.y, e.x, e.y, outline="#ffd75e", width=3)

    def drag(e):
        if rect["id"]:
            canvas.coords(rect["id"], rect["x"], rect["y"], e.x, e.y)

    def release(e):
        x1, x2 = sorted((rect["x"], e.x))
        y1, y2 = sorted((rect["y"], e.y))
        if x2 - x1 < 30 or y2 - y1 < 20:
            return
        top.destroy()
        on_done({"left": mon["left"] + x1, "top": mon["top"] + y1,
                 "width": x2 - x1, "height": y2 - y1})

    def cancel(e=None):
        top.destroy()
        print("範囲の選択をキャンセルしました")

    canvas.bind("<ButtonPress-1>", press)
    canvas.bind("<B1-Motion>", drag)
    canvas.bind("<ButtonRelease-1>", release)
    canvas.bind("<Button-3>", cancel)
    top.bind("<Escape>", cancel)
    top.focus_force()
