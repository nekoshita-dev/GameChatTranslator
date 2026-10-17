# -*- coding: utf-8 -*-
"""設定画面でキーを覚えるときの、キー名の変換（画面・Windows に依存しない）"""

KEYSYM_NAMES = {
    "caps_lock": "caps lock", "prior": "page up", "next": "page down", "scroll_lock": "scroll lock",
    "num_lock": "num lock", "grave": "`", "return": "enter", "escape": "esc", "back_space": "backspace",
    "space": "space", "tab": "tab", "insert": "insert", "delete": "delete", "home": "home", "end": "end",
    "pause": "pause", "slash": "/", "semicolon": ";", "apostrophe": "'", "comma": ",", "period": ".",
    "bracketleft": "[", "bracketright": "]", "backslash": "\\", "minus": "-", "equal": "=",
}
MODIFIER_KEYSYMS = {"shift_l", "shift_r", "control_l", "control_r", "alt_l", "alt_r", "win_l", "win_r",
                    "super_l", "super_r", "meta_l", "meta_r"}


def keysym_to_name(keysym):
    """tk のキー名を、設定ファイルで使う名前にする。使えないキーは None"""
    k = keysym.lower()
    if k in MODIFIER_KEYSYMS:
        return None
    if k.startswith("f") and k[1:].isdigit() and 1 <= int(k[1:]) <= 24:
        return k
    if k.startswith("kp_") and k[3:].isdigit():
        return "num" + k[3:]
    if len(k) == 1 and k.isalnum():
        return k
    return KEYSYM_NAMES.get(k)


def combo_name(keysym, state, allow_mods=True):
    """キーと修飾キー（Ctrl・Shift・Alt）から "ctrl+f10" のような名前を作る"""
    name = keysym_to_name(keysym)
    if not name:
        return None
    if not allow_mods:
        return name
    mods = []
    if state & 0x0004:
        mods.append("ctrl")
    if state & 0x0001:
        mods.append("shift")
    if state & 0x20000:  # Windows の Alt（0x0008 は Num Lock なので見ない）
        mods.append("alt")
    return "+".join(mods + [name])
