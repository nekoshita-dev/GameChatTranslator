# -*- coding: utf-8 -*-
"""Windowsのキー操作：キーの押下判定（フック不使用）と、ゲームへのキー入力（SendInput）"""
import ctypes
import re
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)

INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT
user32.VkKeyScanW.argtypes = (wintypes.WCHAR,)
user32.VkKeyScanW.restype = ctypes.c_short
user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
user32.MapVirtualKeyW.restype = wintypes.UINT
user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetParent.argtypes = (wintypes.HWND,)
user32.GetParent.restype = wintypes.HWND
user32.GetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int)
user32.GetWindowLongW.restype = wintypes.LONG
user32.SetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.LONG)
user32.SetWindowLongW.restype = wintypes.LONG

imm32 = ctypes.WinDLL("imm32")
imm32.ImmGetDefaultIMEWnd.argtypes = (wintypes.HWND,)
imm32.ImmGetDefaultIMEWnd.restype = wintypes.HWND
user32.GetForegroundWindow.restype = wintypes.HWND
user32.SendMessageTimeoutW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                                       wintypes.LPARAM, wintypes.UINT, wintypes.UINT,
                                       ctypes.POINTER(ctypes.c_size_t))
user32.SendMessageTimeoutW.restype = wintypes.LPARAM

class GUITHREADINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("hwndActive", wintypes.HWND), ("hwndFocus", wintypes.HWND),
                ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
                ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND),
                ("rcCaret", wintypes.RECT)]


user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetGUIThreadInfo.argtypes = (wintypes.DWORD, ctypes.POINTER(GUITHREADINFO))
user32.GetGUIThreadInfo.restype = wintypes.BOOL
user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
user32.GetWindowTextW.restype = ctypes.c_int

VK_SHIFT, VK_CONTROL, VK_MENU = 0x10, 0x11, 0x12
KEYEVENTF_UNICODE = 0x0004

# 拡張キー（送るときに専用のフラグが必要なもの）
_EXTENDED = {0xA3, 0xA5, 0x2D, 0x2E, 0x24, 0x23, 0x21, 0x22, 0x25, 0x26, 0x27, 0x28, 0x6F, 0x90}

_NAMED_VK = {
    "enter": 0x0D, "return": 0x0D, "esc": 0x1B, "escape": 0x1B, "backspace": 0x08,
    "caps lock": 0x14, "capslock": 0x14, "tab": 0x09, "space": 0x20,
    "mouse4": 0x05, "mouse5": 0x06, "xbutton1": 0x05, "xbutton2": 0x06,
    "alt": 0x12, "left alt": 0xA4, "right alt": 0xA5, "win": 0x5B,
    "ctrl": 0x11, "left ctrl": 0xA2, "right ctrl": 0xA3,
    "shift": 0x10, "left shift": 0xA0, "right shift": 0xA1,
    "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23,
    "page up": 0x21, "page down": 0x22, "pause": 0x13,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "scroll lock": 0x91, "num lock": 0x90,
    "`": 0xC0, "/": 0xBF, ";": 0xBA, "'": 0xDE, ",": 0xBC, ".": 0xBE,
    "[": 0xDB, "]": 0xDD, "\\": 0xDC, "-": 0xBD, "=": 0xBB,
}
_MOUSE_VK = {0x05, 0x06}


def vk_of(name):
    """キーの名前（"f8", "enter", "mouse4", "y" など）を仮想キーコードにする"""
    n = name.lower().strip()
    if n in _NAMED_VK:
        return _NAMED_VK[n]
    m = re.fullmatch(r"f(\d{1,2})", n)
    if m and 1 <= int(m.group(1)) <= 24:
        return 0x6F + int(m.group(1))
    m = re.fullmatch(r"num ?(\d)", n)
    if m:
        return 0x60 + int(m.group(1))
    if len(n) == 1 and n.isalnum():
        return ord(n.upper())
    raise ValueError(f"キーの名前が分かりません: '{name}'")


def parse_combo(combo):
    """"shift+enter" → [VK_SHIFT, VK_ENTER]"""
    return [vk_of(p) for p in combo.split("+") if p.strip()]


# 他のアプリのショートカットでよく使われる修飾キー（Alt・Windows キー）
_BLOCKING_MODS = {"alt": (0x12, 0xA4, 0xA5), "win": (0x5B, 0x5C)}
_MOD_GROUP = {0x12: "alt", 0xA4: "alt", 0xA5: "alt", 0x11: "ctrl", 0xA2: "ctrl", 0xA3: "ctrl",
              0x10: "shift", 0xA0: "shift", 0xA1: "shift", 0x5B: "win", 0x5C: "win"}


def combo_pressed(combo_vks, down):
    """組み合わせキーが押されているか。down(vk) は押下判定の関数

    - 組み合わせの全キーが押されていること
    - 組み合わせに含まれない Alt・Windows キーが押されていたら反応しない
      （NVIDIA の Alt+F10、Xbox Game Bar の Win+Alt+R などと重ならないように）
    """
    if not combo_vks or not all(down(vk) for vk in combo_vks):
        return False
    used = {_MOD_GROUP.get(vk) for vk in combo_vks}
    for group, vks in _BLOCKING_MODS.items():
        if group not in used and any(down(vk) for vk in vks):
            return False
    return True


def is_down(vk):
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


# ---------- キー入力 ----------
def _send(vk, up=False):
    scan = user32.MapVirtualKeyW(vk, 0)
    flags = KEYEVENTF_SCANCODE
    if up:
        flags |= KEYEVENTF_KEYUP
    if vk in _EXTENDED:
        flags |= KEYEVENTF_EXTENDEDKEY
    inp = INPUT(type=INPUT_KEYBOARD)
    inp.u.ki = KEYBDINPUT(0, scan, flags, 0, 0)
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def tap_combo(combo, delay=0.012):
    vks = parse_combo(combo)
    if not vks or any(v in _MOUSE_VK for v in vks):
        raise ValueError(f"このキーは入力に使えません: '{combo}'")
    *mods, key = vks
    for m in mods:
        _send(m)
        time.sleep(delay)
    _send(key)
    time.sleep(delay)
    _send(key, up=True)
    for m in reversed(mods):
        _send(m, up=True)
    time.sleep(delay)


def type_char_unicode(ch, delay=0.012):
    """文字そのものを送る（日本語入力のオン/オフに左右されない。全角・ローマ字変換が起きない）"""
    for up in (False, True):
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.u.ki = KEYBDINPUT(0, ord(ch), KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if up else 0), 0, 0)
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        if not up:
            time.sleep(delay)
    time.sleep(delay)


def type_char(ch, delay=0.012):
    """キーを押したことにして送る（scancode 方式。unicode 方式が効かないゲーム用）"""
    r = user32.VkKeyScanW(ch)
    if r == -1:
        return  # キーボードで打てない文字は飛ばす
    vk = r & 0xFF
    mods_bits = (r >> 8) & 0xFF
    pressed = []
    for bit, mvk in ((1, VK_SHIFT), (2, VK_CONTROL), (4, VK_MENU)):
        if mods_bits & bit:
            _send(mvk)
            pressed.append(mvk)
    _send(vk)
    time.sleep(delay)
    _send(vk, up=True)
    for mvk in reversed(pressed):
        _send(mvk, up=True)
    time.sleep(delay)


# ---------- 日本語入力（IME）のオン/オフ ----------
_WM_IME_CONTROL = 0x0283
_IMC_GETCONVERSIONMODE = 0x0001
_IMC_SETCONVERSIONMODE = 0x0002
_IMC_GETOPENSTATUS = 0x0005
_IMC_SETOPENSTATUS = 0x0006


def _ime_msg(ime_hwnd, cmd, value=0):
    result = ctypes.c_size_t(0)
    ok = user32.SendMessageTimeoutW(ime_hwnd, _WM_IME_CONTROL, cmd, value,
                                    0x0002, 200, ctypes.byref(result))  # SMTO_ABORTIFHUNG
    return result.value if ok else None


_IMC_GETCONVERSIONMODE = 0x0001
_IMC_SETCONVERSIONMODE = 0x0002


def _focus_hwnd():
    fg = user32.GetForegroundWindow()
    if not fg:
        return None
    tid = user32.GetWindowThreadProcessId(fg, None)
    gti = GUITHREADINFO(cbSize=ctypes.sizeof(GUITHREADINFO))
    if user32.GetGUIThreadInfo(tid, ctypes.byref(gti)) and gti.hwndFocus:
        return gti.hwndFocus
    return fg


def ime_off():
    """入力中のウィンドウの日本語入力をオフ（英数モード）にする。元の状態を返す（戻すときに使う）"""
    try:
        ime = imm32.ImmGetDefaultIMEWnd(_focus_hwnd())
        if not ime:
            return None
        prev_open = _ime_msg(ime, _IMC_GETOPENSTATUS)
        prev_conv = _ime_msg(ime, _IMC_GETCONVERSIONMODE)
        if prev_open:
            _ime_msg(ime, _IMC_SETOPENSTATUS, 0)
        if prev_conv:
            _ime_msg(ime, _IMC_SETCONVERSIONMODE, 0)  # 0 = 英数
        if prev_open or prev_conv:
            time.sleep(0.03)
        return (ime, prev_open, prev_conv)
    except Exception:
        return None


def ime_restore(saved):
    if not saved:
        return
    ime, prev_open, prev_conv = saved
    try:
        if prev_conv:
            _ime_msg(ime, _IMC_SETCONVERSIONMODE, prev_conv)
        if prev_open:
            _ime_msg(ime, _IMC_SETOPENSTATUS, prev_open)
    except Exception:
        pass


def type_char_unicode(ch, delay=0.012):
    """文字そのものを送る（日本語入力のオン/オフに左右されない。全角・ローマ字変換が起きない）"""
    for up in (False, True):
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.u.ki = KEYBDINPUT(0, ord(ch), KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if up else 0), 0, 0)
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        if not up:
            time.sleep(delay)
    time.sleep(delay)


def type_char(ch, delay=0.012):
    """キーを押したことにして送る（scancode 方式。unicode 方式が効かないゲーム用）"""
    r = user32.VkKeyScanW(ch)
    if r == -1:
        return  # キーボードで打てない文字は飛ばす
    vk = r & 0xFF
    mods_bits = (r >> 8) & 0xFF
    pressed = []
    for bit, mvk in ((1, VK_SHIFT), (2, VK_CONTROL), (4, VK_MENU)):
        if mods_bits & bit:
            _send(mvk)
            pressed.append(mvk)
    _send(vk)
    time.sleep(delay)
    _send(vk, up=True)
    for mvk in reversed(pressed):
        _send(mvk, up=True)
    time.sleep(delay)


# ---------- 日本語入力（IME）のオン/オフ ----------
_WM_IME_CONTROL = 0x0283
_IMC_GETCONVERSIONMODE = 0x0001
_IMC_SETCONVERSIONMODE = 0x0002
_IMC_GETOPENSTATUS = 0x0005
_IMC_SETOPENSTATUS = 0x0006


def _ime_msg(ime_hwnd, cmd, value=0):
    result = ctypes.c_size_t(0)
    ok = user32.SendMessageTimeoutW(ime_hwnd, _WM_IME_CONTROL, cmd, value,
                                    0x0002, 200, ctypes.byref(result))  # SMTO_ABORTIFHUNG
    return result.value if ok else None


def ime_off():
    """手前のウィンドウ（ゲーム）の日本語入力をオフ・英数モードにする。元の状態を返す（戻すときに使う）"""
    try:
        ime = imm32.ImmGetDefaultIMEWnd(user32.GetForegroundWindow())
        if not ime:
            return None
        opened = _ime_msg(ime, _IMC_GETOPENSTATUS)
        mode = _ime_msg(ime, _IMC_GETCONVERSIONMODE)
        if mode:
            _ime_msg(ime, _IMC_SETCONVERSIONMODE, 0)  # 0 = 英数（半角）
        if opened:
            _ime_msg(ime, _IMC_SETOPENSTATUS, 0)
        if mode or opened:
            time.sleep(0.03)
        return (ime, opened, mode)
    except Exception:
        return None


def ime_restore(saved):
    if not saved:
        return
    ime, opened, mode = saved
    try:
        if opened:
            _ime_msg(ime, _IMC_SETOPENSTATUS, opened)
        if mode:
            _ime_msg(ime, _IMC_SETCONVERSIONMODE, mode)
    except Exception:
        pass


def type_char_unicode(ch, delay=0.012):
    """文字コードで直接入力する（日本語入力の影響を受けない。ゲームによっては受け付けない）"""
    for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.u.ki = KEYBDINPUT(0, ord(ch), flags, 0, 0)
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        time.sleep(delay)


user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
user32.GetWindowRect.restype = wintypes.BOOL


def foreground_rect():
    """一番手前のウィンドウの位置 (left, top, right, bottom)。取れなければ None"""
    try:
        hwnd = user32.GetForegroundWindow()
        rc = wintypes.RECT()
        if hwnd and user32.GetWindowRect(hwnd, ctypes.byref(rc)):
            return (rc.left, rc.top, rc.right, rc.bottom)
    except Exception:
        pass
    return None


def foreground_title():
    """一番手前のウィンドウのタイトル（ゲームが前にあるかの判定に使う。ゲームのプロセスには触れない）"""
    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        return buf.value
    except Exception:
        return ""


def send_chat(text, chat, open_key, auto_send=True):
    """チャット欄を開く → 文字を入力 → 送信（chat はプロファイルの [chat] 設定）"""
    delay = chat["key_delay"]
    use_ime_off = chat.get("ime_off", True)
    unicode_mode = chat.get("type_mode", "scancode") == "unicode"
    before = ime_off() if use_ime_off else None
    try:
        tap_combo(open_key, delay)
        time.sleep(chat["open_delay"])
        if use_ime_off:
            # ゲームはチャット欄を開いたときに日本語入力をオンに戻すことがあるので、開いた後にも切る
            ime_off()
        for ch in text:
            if unicode_mode:
                type_char_unicode(ch, delay)
            else:
                type_char(ch, delay)
        if auto_send:
            time.sleep(0.05)
            tap_combo(chat["send_key"], delay)
    finally:
        ime_restore(before)  # 送信前に日本語入力がオンだった場合だけ、元に戻す


_WS_EX_LAYERED = 0x80000
_WS_EX_TRANSPARENT = 0x20
_WS_EX_TOOLWINDOW = 0x80
_WS_EX_NOACTIVATE = 0x08000000


def set_click_through(tk_window, enabled=True):
    """enabled=True: クリックが下のゲームに届き、フォーカスも奪わない / False: マウスで掴める（移動モード）"""
    hwnd = user32.GetParent(tk_window.winfo_id())
    style = user32.GetWindowLongW(hwnd, -20) | _WS_EX_LAYERED | _WS_EX_TOOLWINDOW
    if enabled:
        style |= _WS_EX_TRANSPARENT | _WS_EX_NOACTIVATE
    else:
        style &= ~(_WS_EX_TRANSPARENT | _WS_EX_NOACTIVATE)
    user32.SetWindowLongW(hwnd, -20, ctypes.c_long(style).value)


def make_click_through(tk_window):
    set_click_through(tk_window, True)


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.SetConsoleTitleW.argtypes = (wintypes.LPCWSTR,)

_instance_mutex = None


kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
kernel32.GetConsoleWindow.restype = wintypes.HWND
user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)


def acquire_single_instance(name="Local\\GameChatTranslator", wait=0.0):
    """2つ同時に起動していないか確認する（同時に動くと二重に送信してしまう）。起動中なら False
    wait 秒までは、前のアプリが終わるのを待つ（再起動のとき）"""
    global _instance_mutex
    deadline = time.time() + wait
    while True:
        ctypes.set_last_error(0)
        handle = kernel32.CreateMutexW(None, False, name)
        if ctypes.get_last_error() != 183:  # ERROR_ALREADY_EXISTS
            _instance_mutex = handle  # 終了するまで持ち続ける
            return True
        kernel32.CloseHandle(handle)
        if time.time() >= deadline:
            return False
        time.sleep(0.3)


def show_console(show=True):
    """黒い画面（コンソール）を表示する・隠す"""
    try:
        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            user32.ShowWindow(hwnd, 5 if show else 0)
    except Exception:
        pass


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def set_console_title(text):
    try:
        kernel32.SetConsoleTitleW(text)
    except Exception:
        pass


def set_dpi_aware():
    """画面の拡大率（125%など）に左右されず、実際の画面の座標で扱う"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass
