# -*- coding: utf-8 -*-
"""設定ファイル（settings.toml）とゲームプロファイル（profiles/*.toml）の読み込み"""
import copy
import json
import os
import shutil
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE_DIR = os.path.join(ROOT, "profiles")
DICT_DIR = os.path.join(ROOT, "dict")
DATA_DIR = os.path.join(ROOT, "data")
USER_DIR = os.path.join(ROOT, "user")
SETTINGS_PATH = os.path.join(ROOT, "settings.toml")                 # 利用者の設定（更新で上書きされない）
DEFAULT_SETTINGS_PATH = os.path.join(ROOT, "settings.default.toml")  # 配布する初期設定
REGIONS_PATH = os.path.join(DATA_DIR, "regions.json")
OVERLAY_PATH = os.path.join(DATA_DIR, "overlay.json")
LOG_DIR = os.path.join(DATA_DIR, "logs")

USER_DICT_HEADERS = {
    "ignore.txt": "# 無視リスト：この文字列を含む行は翻訳しません（1行に1つ。ゲームのメニュー表示などを書く）\n"
                  "# アプリを更新しても上書きされません\n",
    "slang.csv": "# 自分用のスラング辞書（全ゲーム共通・最優先）。列の意味は dict/slang_en.csv を参照\n"
                 "# アプリを更新しても上書きされません\nterm,expand,ja\n",
    "speech.csv": "# 自分用の用語辞書（全ゲーム共通・最優先）。列の意味は dict/speech_ja.csv を参照\n"
                  "# アプリを更新しても上書きされません\nja,en\n",
}

# settings.toml に書かれていない項目はこの値になる
DEFAULT_SETTINGS = {
    "game": "generic",
    "debug": False,
    "voice": {
        "enabled": True,
        "hotkey": "f8",
        "alt_hotkey": "",
        "translator": "google",
        "model": "auto",
        "auto_send": True,
        "input_device": -1,
        "beep": True,
        "max_seconds": 15,
        "min_seconds": 0.4,
        "preroll": 0.4,
        "postroll": 0.3,
        "auto_gain": True,
        "vad_threshold": 0.3,
        "show_level": True,
    },
    "chat_translate": {
        "enabled": True,
        "region_key": "f9",
        "toggle_key": "f10",
        "translator": "google",
        "my_name": "",
        "poll_interval": 0.8,
        "monitor": 1,
        "min_score": 0.6,
        "capture": "auto",
        "ignore_patterns": [],
        "strip_patterns": [],
    },
    "overlay": {
        "position": "above",
        "seconds": 20,
        "max_lines": 6,
        "font_size": 14,
        "alpha": 0.85,
        "show_original": False,
        "font": "Yu Gothic UI",
        "move_key": "f7",
        "width": 0,
    },
    "dictionary": {
        "reload_key": "f11",
    },
    "api": {
        "deepl_key": "",
    },
}

# profiles/<ゲーム>.toml に書かれていない項目はこの値になる
DEFAULT_PROFILE = {
    "name": "",
    "notes": "",
    "chat": {
        "open_key": "enter",
        "alt_open_key": "",
        "send_key": "enter",
        "open_delay": 0.15,
        "key_delay": 0.012,
        "max_chars": 120,
        "ime_off": True,
        "type_mode": "unicode",
        "ignore_patterns": [],
        "strip_patterns": [],
    },
    "dictionary": {
        "slang": [],
        "speech": [],
    },
}


def deep_merge(base, override):
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _read_toml(path):
    with open(path, "rb") as f:
        return tomllib.load(f)


def ensure_user_files(settings_path=SETTINGS_PATH, default_path=DEFAULT_SETTINGS_PATH,
                      user_dir=USER_DIR):
    """初回起動時に、利用者が編集するファイル（settings.toml、user/ の辞書）を作る。作ったものを返す"""
    created = []
    if not os.path.exists(settings_path) and os.path.exists(default_path):
        shutil.copyfile(default_path, settings_path)
        created.append(settings_path)
    os.makedirs(user_dir, exist_ok=True)
    for fn, header in USER_DICT_HEADERS.items():
        p = os.path.join(user_dir, fn)
        if not os.path.exists(p):
            with open(p, "w", encoding="utf-8") as f:
                f.write(header)
            created.append(p)
    return created


def load_settings(path=SETTINGS_PATH, default_path=DEFAULT_SETTINGS_PATH):
    if not os.path.exists(path):
        path = default_path
    data = _read_toml(path) if os.path.exists(path) else {}
    s = deep_merge(DEFAULT_SETTINGS, data)
    if not s["api"]["deepl_key"]:
        s["api"]["deepl_key"] = os.environ.get("DEEPL_API_KEY", "")
    return s


def list_profiles(profile_dir=PROFILE_DIR):
    out = []
    for fn in sorted(os.listdir(profile_dir)):
        if fn.endswith(".toml"):
            gid = fn[:-5]
            try:
                name = _read_toml(os.path.join(profile_dir, fn)).get("name", gid)
            except Exception:
                name = gid
            out.append((gid, name))
    return out


def load_profile(game, profile_dir=PROFILE_DIR):
    path = os.path.join(profile_dir, f"{game}.toml")
    if not os.path.exists(path):
        ids = ", ".join(g for g, _ in list_profiles(profile_dir))
        raise FileNotFoundError(f"ゲームプロファイル '{game}' がありません（使えるもの: {ids}）")
    p = deep_merge(DEFAULT_PROFILE, _read_toml(path))
    p["id"] = game
    p["name"] = p["name"] or game
    return p


def user_ignore(user_dir=USER_DIR):
    """user/ignore.txt の無視リスト（この文字列を含む行は翻訳しない。正規表現ではなくそのままの文字列）"""
    from .textproc import read_ignore
    p = os.path.join(user_dir, "ignore.txt")
    return read_ignore([p]) if os.path.exists(p) else []


def dictionary_paths(profile, kind, profile_dir=PROFILE_DIR, dict_dir=DICT_DIR, user_dir=USER_DIR):
    """共通辞書 → ゲーム専用辞書 → 自分用辞書（user/）の順（後のものが優先）でファイルの場所を返す"""
    common = {
        "slang": ["slang_en.csv", "slang_zh.csv"],
        "speech": ["speech_ja.csv"],
    }[kind]
    paths = [os.path.join(dict_dir, fn) for fn in common]
    for fn in profile["dictionary"].get(kind, []):
        paths.append(os.path.join(profile_dir, fn))
    paths.append(os.path.join(user_dir, f"{kind}.csv"))
    return [p for p in paths if os.path.exists(p)]


# ---------- チャット欄の範囲（ゲームごとに保存） ----------
def load_region(game, path=REGIONS_PATH):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get(game)
    except (OSError, ValueError):
        return None


def save_region(game, region, path=REGIONS_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        pass
    data[game] = region
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------- 翻訳の表示位置（ゲームごとに保存） ----------
def _load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def load_overlay_pos(game, path=OVERLAY_PATH):
    """{"x", "y", "font_size", "width"} の一部、無ければ None"""
    return _load_json(path).get(game)


def save_overlay_pos(game, pos, path=OVERLAY_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = _load_json(path)
    if pos:
        data[game] = pos
    else:
        data.pop(game, None)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------- settings.toml の書き換え（コメントを残したまま値だけ変える） ----------
def toml_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    s = str(v).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def update_settings_text(text, changes):
    """changes: {(セクション or None, キー): 値}。書き換えた文字列を返す"""
    import re
    lines = text.splitlines()
    pending = dict(changes)
    section = None
    section_end = {}      # セクション → そのセクションの最後の行番号
    section_end[None] = -1
    value_re = r'("(?:[^"\\]|\\.)*"|\'[^\']*\'|[^#]*?)'
    for i, line in enumerate(lines):
        m = re.match(r"^\s*\[([^\[\]]+)\]\s*(#.*)?$", line)
        if m:
            section = m.group(1).strip()
            section_end[section] = i
            continue
        section_end[section] = i
        for (sec, key), val in list(pending.items()):
            if sec != section:
                continue
            m = re.match(r"^(\s*" + re.escape(key) + r"\s*=\s*)" + value_re + r"(\s*(#.*)?)$", line)
            if m:
                lines[i] = m.group(1) + toml_value(val) + m.group(3)
                del pending[(sec, key)]
    # 見つからなかったキーは、そのセクションの最後（無ければセクションごと末尾）に足す
    inserts = {}
    for (sec, key), val in pending.items():
        if sec in section_end:
            inserts.setdefault(section_end[sec], []).append(f"{key} = {toml_value(val)}")
        else:
            inserts.setdefault("end:" + sec, []).append(f"{key} = {toml_value(val)}")
    out = []
    if -1 in inserts:
        out.extend(inserts.pop(-1))
    for i, line in enumerate(lines):
        out.append(line)
        if i in inserts:
            out.extend(inserts[i])
    for k, rows in inserts.items():
        if isinstance(k, str):
            out.append("")
            out.append(f"[{k[4:]}]")
            out.extend(rows)
    return "\n".join(out) + "\n"


def update_settings_file(changes, path=SETTINGS_PATH, default_path=DEFAULT_SETTINGS_PATH, validate=None):
    """settings.toml の値を書き換える。書き換え後の内容を確かめてから保存する（問題があれば何も変えない）

    validate: 書き換え後の設定（初期値と合わせたもの）を受け取り、問題があれば例外を出す関数"""
    src = path if os.path.exists(path) else default_path
    with open(src, encoding="utf-8") as f:
        text = f.read()
    new = update_settings_text(text, changes)
    data = tomllib.loads(new)  # 壊れた内容は保存しない
    if validate:
        merged = deep_merge(DEFAULT_SETTINGS, data)
        validate(merged)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(new)
    os.replace(tmp, path)
