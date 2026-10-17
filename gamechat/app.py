# -*- coding: utf-8 -*-
"""GameChat Translator 本体"""
import argparse
import os
import queue
import sys
import threading
import time
from collections import deque

from . import __version__
from . import config
from .textproc import SlangDict, SpeechDict, clean_ascii


class AppState:
    def __init__(self):
        self.region = None          # チャット欄の範囲 {"left", "top", "width", "height"}
        self.enabled = True         # 相手のチャットを翻訳するか
        self.voice_enabled = True   # 自分の発言（F8）を使うか
        self.sending = False        # 自分がチャットに入力している間は読み取らない
        self.recent_sent = deque(maxlen=10)
        self.snap_request = None     # 範囲選択用の撮影の依頼 (モニター, ウィンドウ名, ウィンドウ位置)


class Dictionaries:
    """辞書の入れ物。F11 で読み込み直せる"""

    def __init__(self, profile):
        self.profile = profile
        self.slang = SlangDict()
        self.speech = SpeechDict()
        self.ignore = []   # user/ignore.txt

    def reload(self):
        try:
            slang = SlangDict.load(config.dictionary_paths(self.profile, "slang"))
            speech = SpeechDict.load(config.dictionary_paths(self.profile, "speech"))
            ignore = config.user_ignore()
        except Exception as e:
            print(f"辞書を読み込めませんでした（前の辞書を使い続けます）: {e}")
            return
        self.slang, self.speech, self.ignore = slang, speech, ignore
        print(f"辞書を読み込みました: スラング {len(slang)} 語 / 音声用語 {len(speech)} 語 / 無視 {len(ignore)} 件")


def beep(enabled, freq, ms=70):
    if enabled:
        import winsound
        threading.Thread(target=winsound.Beep, args=(freq, ms), daemon=True).start()


# ---------- 自分の発言 ----------
def voice_loop(vt, mic, settings, profile, state, ui_q=None):
    def post(*item):
        if ui_q is not None:
            ui_q.put(item)

    from .winkeys import is_down, vk_of, send_chat
    v = settings["voice"]
    chat = profile["chat"]
    snd = v["beep"]
    keys = [(vk_of(v["hotkey"]), chat["open_key"])]
    if v["alt_hotkey"] and chat["alt_open_key"]:
        keys.append((vk_of(v["alt_hotkey"]), chat["alt_open_key"]))
    try:
        mic.ensure_open()
    except Exception as e:
        print(f"  {e}")

    while True:
        try:
            held = next(((vk, ok) for vk, ok in keys if is_down(vk)), None)
            if held and not state.voice_enabled:
                while is_down(held[0]):
                    time.sleep(0.05)
                continue
            if not held:
                time.sleep(0.01)
                continue
            vk, open_key = held
            try:
                mic.start()
            except Exception as e:
                print(f"  {e}")
                beep(snd, 300, 200)
                while is_down(vk):
                    time.sleep(0.05)
                time.sleep(1)
                continue
            beep(snd, 1200)
            post("rec", True)
            t_start = time.time()
            while is_down(vk) and time.time() - t_start < v["max_seconds"]:
                time.sleep(0.01)
            audio = mic.stop()
            post("rec", False)
            beep(snd, 800)
            if audio is None or time.time() - t_start < v["min_seconds"]:
                continue

            from .voice import prepare_audio
            audio = prepare_audio(audio, v["auto_gain"], v["show_level"])
            t0 = time.time()
            english = clean_ascii(vt.to_english(audio), chat["max_chars"])
            if not english:
                print("  （聞き取れませんでした）")
                beep(snd, 300, 200)
                continue
            print(f"  [送信] {english}  ({time.time() - t0:.1f}秒)")
            state.recent_sent.append(english)
            post("sent", vt.last_ja, english)
            state.sending = True
            try:
                send_chat(english, chat, open_key, v["auto_send"])
            finally:
                time.sleep(0.5)
                state.sending = False
            beep(snd, 1500, 50)
        except Exception as e:
            # 何が起きてもこのループは止めない（キーが効かなくなるのを防ぐ）
            print(f"  エラー: {e}")
            post("rec", False)
            state.sending = False
            beep(snd, 300, 200)
            mic.close()
            time.sleep(0.5)


# ---------- F7 / F9 / F10 / F11 ----------
def hotkey_loop(ui_q, actions):
    """actions: {"f9": "select", "ctrl+f10": "toggle", ...}"""
    from .winkeys import combo_pressed, foreground_rect, foreground_title, is_down, parse_combo
    combos = {key: parse_combo(key) for key in actions}
    prev = {key: False for key in actions}
    while True:
        for key, action in actions.items():
            now = combo_pressed(combos[key], is_down)
            if now and not prev[key]:
                # 範囲選択は「キーを押したときに手前にあったウィンドウ（ゲーム）」も覚えておく
                if action == "select":
                    ui_q.put((action, foreground_title(), foreground_rect()))
                else:
                    ui_q.put((action,))
            prev[key] = now
        time.sleep(0.03)


def check_keys(settings):
    """キー設定を確かめる。録音キーは1つのキー、それ以外は "ctrl+f10" のような組み合わせも可"""
    from .winkeys import parse_combo, vk_of
    v, ct = settings["voice"], settings["chat_translate"]
    ov, dc = settings["overlay"], settings["dictionary"]
    for k in (v["hotkey"], v["alt_hotkey"]):
        if k:
            vk_of(k)
    seen = {}
    for label, k in (("region_key", ct["region_key"]), ("toggle_key", ct["toggle_key"]),
                     ("move_key", ov["move_key"]), ("reload_key", dc["reload_key"])):
        if not k:
            continue
        parse_combo(k)
        key = k.lower().replace(" ", "")
        if key in seen:
            raise ValueError(f"{seen[key]} と {label} が同じキー（{k}）です")
        seen[key] = label


REQUIRED_MODULES = [
    ("numpy", "numpy"), ("sounddevice", "sounddevice"), ("faster_whisper", "faster-whisper"),
    ("rapidocr_onnxruntime", "rapidocr_onnxruntime"), ("mss", "mss"),
    ("deep_translator", "deep-translator"), ("PIL", "Pillow"), ("cv2", "opencv-python"),
]


def missing_modules(modules=REQUIRED_MODULES):
    import importlib.util
    return [pip for mod, pip in modules if importlib.util.find_spec(mod) is None]


def parse_args(argv):
    ap = argparse.ArgumentParser(prog="gamechat", description="GameChat Translator")
    ap.add_argument("--game", help="使うゲームプロファイル（settings.toml の game より優先）")
    ap.add_argument("--list", action="store_true", help="使えるゲームプロファイルを表示して終了")
    ap.add_argument("--devices", action="store_true", help="使えるマイクの一覧を表示して終了")
    ap.add_argument("--check", action="store_true", help="動作チェックをして終了（結果は data/logs/check.txt）")
    ap.add_argument("--quick", action="store_true", help="--check で音声認識モデルの確認を省く")
    ap.add_argument("--restart", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--version", action="version", version=f"GameChat Translator {__version__}")
    return ap.parse_args(argv)


def print_devices():
    from .voice import input_devices
    print("使えるマイク（settings.toml の input_device に番号か名前の一部を書きます）")
    for i, name, default in input_devices():
        print(f"  {i:>3}  {name}{'  ← 既定' if default else ''}")


def fail(msg):
    """起動できないときに、画面（ダイアログ）とログの両方で知らせて終わる"""
    print(msg)
    try:
        from .winkeys import show_console
        show_console(True)
    except Exception:
        pass
    try:
        import tkinter as tk
        from tkinter import messagebox
        r = tk.Tk()
        r.withdraw()
        messagebox.showerror("GameChat Translator", msg)
        r.destroy()
    except Exception:
        pass
    sys.exit(1)


class App:
    """画面と各処理（音声・チャット読み取り・キー）をつなぐ"""

    def __init__(self, args, settings, profile):
        self.args = args
        self.settings = settings
        self.profile = profile
        self.state = AppState()
        self.state.enabled = settings["chat_translate"]["enabled"]
        self.state.voice_enabled = settings["voice"]["enabled"]
        self.state.region = config.load_region(profile["id"])
        self.dicts = Dictionaries(profile)
        self.ui_q = queue.Queue()
        self.mic = None
        self.mic_name = "準備中"
        self.voice_info = "準備中" if settings["voice"]["enabled"] else "オフ"
        self.capture_method = None if settings["chat_translate"]["enabled"] else "off"
        self.ready = False
        self.error = False
        self.root = None
        self.gui = None
        self.overlay = None
        self._pending_window = ""
        self._pending_select = {}
        self._quitting = False

    # ---------- 起動 ----------
    def run(self):
        import tkinter as tk
        from .gui import MainWindow
        from .overlay import Overlay
        s = self.settings
        ov = s["overlay"]
        self.root = tk.Tk()
        self.gui = MainWindow(self.root, self)
        self.overlay = Overlay(self.root, self.state, ov, self.profile["id"], self._save_overlay,
                               config.load_overlay_pos(self.profile["id"]))
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

        from .logutil import add_listener
        add_listener(lambda line: self.ui_q.put(("notice", line)))

        self.dicts.reload()
        threading.Thread(target=self._start_workers, daemon=True).start()

        if not s["debug"]:
            from .winkeys import show_console
            self.root.after(800, lambda: show_console(False))  # 黒い画面は隠す（ログはファイルに残る）

        import signal
        signal.signal(signal.SIGINT, lambda *a: self.root.after(0, self.quit))
        self.root.after(100, self._pump)
        self.root.mainloop()
        if self.mic:
            self.mic.close()
        print("終了しました")

    def _start_workers(self):
        """時間のかかる準備（音声認識モデルの読み込みなど）は画面を出した後に行う"""
        s, profile, state = self.settings, self.profile, self.state
        v, ct, ov, dc = s["voice"], s["chat_translate"], s["overlay"], s["dictionary"]
        from .translate import Translator
        deepl_key = s["api"]["deepl_key"]

        actions = {}
        if ct["enabled"]:
            from .chatreader import chat_loop
            in_tr = Translator(ct["translator"], deepl_key, label="相手のチャットの翻訳")
            threading.Thread(target=chat_loop, args=(state, self.ui_q, s, self.dicts, in_tr),
                             daemon=True).start()
            actions[ct["region_key"].lower()] = "select"
            actions[ct["toggle_key"].lower()] = "toggle"
        if dc["reload_key"]:
            actions[dc["reload_key"].lower()] = "reload"
        if ov["move_key"]:
            actions[ov["move_key"].lower()] = "move"
        threading.Thread(target=hotkey_loop, args=(self.ui_q, actions), daemon=True).start()

        if ct["enabled"] and not state.region:
            print(f"※ 相手のチャットを翻訳するには、ゲーム画面で [{ct['region_key'].upper()}] を押して範囲を選んでください")

        if v["enabled"]:
            try:
                from .voice import MODEL_INFO, Mic, VoiceTranslator, input_devices, load_model, pick_device
                devices = input_devices()
                try:
                    device = pick_device(v["input_device"], devices)
                except ValueError as e:
                    print(f"※ {e}。既定のマイクを使います。")
                    device = None
                self.mic_name = next((n for i, n, d in devices if (i == device if device is not None else d)),
                                     "既定のマイク")
                mic = Mic(device, v["preroll"], v["postroll"])
                try:
                    mic.ensure_open()  # 音量メーターをすぐ動かすため
                except Exception as e:
                    print(f"※ {e}")
                self.mic = mic
                model = load_model(v["model"])
                self.voice_info = MODEL_INFO["text"]
                out_tr = None
                if v["translator"] != "whisper":
                    out_tr = Translator(v["translator"], deepl_key, label="自分の発言の翻訳")
                vt = VoiceTranslator(model, v["translator"], out_tr, self.dicts, v["vad_threshold"])
                threading.Thread(target=voice_loop, args=(vt, mic, s, profile, state, self.ui_q),
                                 daemon=True).start()
            except Exception as e:
                self.error = True
                self.voice_info = "使えません"
                print(f"エラー: 自分の発言の機能を開始できませんでした: {e}")
        self.ready = True
        print("準備ができました" + (f"。{v['hotkey'].upper()} を押しながら話すと英語で送信します" if v["enabled"] else ""))

    # ---------- 画面からの操作 ----------
    def set_voice_enabled(self, on):
        self.state.voice_enabled = on
        print(f"自分の発言: {'オン' if on else 'オフ'}")

    def set_chat_enabled(self, on):
        if on and not self.settings["chat_translate"]["enabled"]:
            print("※ 相手のチャットの翻訳は設定でオフになっています。設定画面でオンにして再起動してください")
            self.state.enabled = False
            return
        self.state.enabled = on
        print(f"相手のチャットの翻訳: {'オン' if on else 'オフ'}")

    def request_select(self, delay=0):
        """範囲の選び直し。画面のボタンからは、ゲームに切り替える時間を置いてから撮る"""
        if not self.settings["chat_translate"]["enabled"]:
            print("※ 相手のチャットの翻訳がオフです")
            return
        print(f"{delay}秒後にゲーム画面を撮ります。ゲームに切り替えてください")
        self.root.after(int(delay * 1000), self._delayed_select)

    def _delayed_select(self):
        from .winkeys import foreground_rect, foreground_title
        title = foreground_title()
        if not title or title.startswith(("GameChat Translator", "設定 - GameChat")):
            print("※ ゲームに切り替わっていませんでした。ゲーム画面で F9 を押しても選べます")
            return
        self.ui_q.put(("select", title, foreground_rect()))

    def toggle_move(self):
        self.ui_q.put(("move",))

    def change_game(self, gid):
        err = self.save_settings({(None, "game"): gid})
        if err:
            print(f"エラー: {err}")
            return
        self.restart()

    def save_settings(self, changes):
        """設定を保存する。問題があればその説明を返す"""
        try:
            config.update_settings_file(changes, validate=check_keys)
        except Exception as e:
            return f"設定を保存できませんでした: {e}"
        return None

    def reset_overlay_position(self):
        self.overlay.custom_xy = None
        self.overlay.width = 0
        self.overlay.font_size = self.settings["overlay"]["font_size"]
        self._save_overlay(None)

    def list_mics(self):
        try:
            from .voice import input_devices
            return input_devices()
        except Exception:
            return []

    def open_path(self, path):
        try:
            if not os.path.exists(path) and path.endswith((".csv", ".txt")):
                config.ensure_user_files()
            os.startfile(path)
        except Exception as e:
            print(f"エラー: 開けませんでした: {e}")

    def open_log(self):
        self.open_path(os.path.join(config.LOG_DIR, "gamechat.log"))

    def open_check(self):
        self.open_path(os.path.join(config.ROOT, "check.bat"))

    def restart(self):
        """設定を反映するため、アプリを起動し直す"""
        import subprocess
        exe = sys.executable
        if exe.lower().endswith("pythonw.exe"):
            exe = exe[:-len("pythonw.exe")] + "python.exe"
        try:
            # ゲームなどはすべて settings.toml から読み直す
            subprocess.Popen([exe, "-m", "gamechat", "--restart"], cwd=config.ROOT,
                             creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
        except Exception as e:
            print(f"エラー: 再起動できませんでした。手動で起動し直してください: {e}")
            return
        self.quit()

    def quit(self):
        if self._quitting:
            return
        self._quitting = True
        try:
            self.root.quit()
        except Exception:
            pass

    # ---------- 内部 ----------
    def _save_overlay(self, pos):
        try:
            config.save_overlay_pos(self.profile["id"], pos)
        except OSError as e:
            print(f"表示位置を保存できませんでした: {e}")

    def _beep(self, freq, ms=70):
        beep(self.settings["voice"]["beep"], freq, ms)

    def _open_select(self, img, mon, title):
        from .overlay import select_region
        self._pending_window = title
        select_region(self.root, img, mon, self.settings["overlay"]["font"], self._on_region)

    def _on_region(self, r):
        if self._pending_window:
            r["window"] = self._pending_window
        self.state.region = r
        if self.settings["chat_translate"]["enabled"]:
            self.state.enabled = True
        try:
            config.save_region(self.profile["id"], r)
        except OSError as e:
            print(f"範囲を保存できませんでした: {e}")
        where = f"（「{r['window']}」が手前にあるときだけ読み取ります）" if r.get("window") else ""
        print(f"チャット欄の範囲を保存しました{where}")
        self._beep(1500, 50)

    def _pump(self):
        state = self.state
        try:
            while True:
                try:
                    item = self.ui_q.get_nowait()
                except queue.Empty:
                    break
                kind = item[0]
                if kind == "line":
                    _, name, ja, msg = item
                    self.overlay.add(name, ja, msg)
                    self.gui.add_entry("recv", name, msg, ja)
                elif kind == "sent":
                    _, ja, en = item
                    self.gui.add_entry("sent", "", ja or "（Whisper で直接英訳）", en)
                elif kind == "rec":
                    self.gui.set_recording(item[1])
                elif kind == "notice":
                    line = item[1]
                    if line.startswith("画面の撮影方法:"):
                        self.capture_method = line.split(":", 1)[1].strip().split("（")[0]
                    if line.startswith("チャット読み取り機能を開始できませんでした"):
                        self.error = True
                        self.capture_method = "error"
                    self.gui.set_notice(line)
                elif kind == "select":
                    from .capture import monitor_of
                    import mss
                    with mss.mss() as m:
                        mons = m.monitors[1:]
                    title, rect = item[1], item[2]
                    state.snap_request = (monitor_of(rect, mons), title, rect)
                elif kind == "snapshot":
                    from .capture import covers_monitor
                    _, img, mon, title, rect = item
                    if title and covers_monitor(rect, mon):
                        self._pending_select.update(img=img, mon=mon, title=title)
                        print("ゲーム画面を撮りました。ゲームから出たとき（Alt+Tab など）に、"
                              "この画面でチャット欄を囲む画面が出ます")
                        self._beep(1500, 50)
                    else:
                        self._open_select(img, mon, title)
                elif kind == "move":
                    moving = self.overlay.toggle_move()
                    print("翻訳の表示枠: " + ("移動モード（ドラッグで移動・もう一度キーで確定）" if moving
                                          else "位置を保存しました"))
                    self._beep(1300 if moving else 1500, 60)
                elif kind == "toggle":
                    self.set_chat_enabled(not state.enabled)
                    self._beep(1300 if state.enabled else 500, 80)
                elif kind == "reload":
                    self.dicts.reload()
                    self._beep(1500, 50)
            if self._pending_select:
                from .winkeys import foreground_title
                if foreground_title() != self._pending_select["title"]:
                    p = dict(self._pending_select)
                    self._pending_select.clear()
                    self._open_select(p["img"], p["mon"], p["title"])
            self.overlay.tick()
        except Exception as e:
            print(f"  表示エラー: {e}")
        self.root.after(100, self._pump)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.list:
        for gid, name in config.list_profiles():
            print(f"  {gid:<12} {name}")
        return
    if args.devices:
        print_devices()
        return
    if args.check:
        from .selfcheck import main as selfcheck
        sys.exit(selfcheck(args.quick))

    if os.name != "nt":
        print("このツールは Windows 専用です。")
        sys.exit(1)

    from .logutil import start_logging
    start_logging(config.LOG_DIR)

    missing = missing_modules()
    if missing:
        fail("必要な部品が入っていません: " + ", ".join(missing) + "\nsetup.bat をもう一度実行してください。")

    from .winkeys import acquire_single_instance, is_admin, set_dpi_aware
    if not acquire_single_instance(wait=10 if args.restart else 0):
        fail("GameChat Translator はすでに起動しています。\n（2つ同時に動かすと二重に送信されます）")
    set_dpi_aware()

    for p in config.ensure_user_files():
        print(f"設定ファイルを作りました: {os.path.relpath(p, config.ROOT)}")
    try:
        settings = config.load_settings()
        profile = config.load_profile(args.game or settings["game"])
    except Exception as e:
        fail(f"設定の読み込みに失敗しました: {e}\n\n"
             "settings.toml の書き方を確認してください（分からなくなったら settings.toml を消すと初期設定に戻ります）。")
    try:
        check_keys(settings)
    except ValueError as e:
        fail(f"settings.toml のキー設定: {e}")

    print(f"GameChat Translator {__version__}　ゲーム: {profile['name']}")
    if profile["notes"]:
        print(f"※ {profile['notes'].strip()}")
    if not is_admin():
        print("※ 管理者権限で起動していません。キーがゲームに届かないことがあります（run.bat から起動してください）")

    try:
        App(args, settings, profile).run()
    except SystemExit:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        fail(f"エラーが起きたため終了します:\n{e}\n\n詳しくは data\\logs\\gamechat.log を見てください。")
