# -*- coding: utf-8 -*-
"""0.2.0 で追加した機能のテスト。 python -m pytest tests"""
import io
import os
import sys
import tomllib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from gamechat import config  # noqa: E402
from gamechat.app import missing_modules  # noqa: E402
from gamechat.logutil import _Tee  # noqa: E402
from gamechat.textproc import SlangDict, SpeechDict  # noqa: E402
from gamechat.translate import TranslateError, Translator  # noqa: E402
from gamechat.voice import pick_device  # noqa: E402


# ---------- 翻訳の予備エンジン ----------
class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def make_tr(engine="google", key="k:fx", fail=(), logs=None, clock=None):
    calls = []
    fail = set(fail)

    def backend(name):
        def f(text, target, source=None):
            calls.append(name)
            if name in fail:
                raise RuntimeError(f"{name} down")
            return f"{name}:{text}"
        return f

    logs = [] if logs is None else logs
    tr = Translator(engine, key, backends={e: backend(e) for e in ("google", "deepl", "mymemory")},
                    log=logs.append, clock=clock or Clock())
    return tr, calls, logs, fail


def test_translator_uses_primary_and_caches():
    tr, calls, _, _ = make_tr("deepl")
    assert tr.translate("hi", "ja") == "deepl:hi"
    assert tr.translate("hi", "ja") == "deepl:hi"
    assert calls == ["deepl"]
    assert tr.order == ["deepl", "google", "mymemory"]


def test_translator_falls_back_and_warns_once():
    tr, calls, logs, _ = make_tr("google", fail={"google"})
    assert tr.translate("a", "ja") == "deepl:a"
    assert tr.translate("b", "ja") == "deepl:b"
    assert len([m for m in logs if "deepl で翻訳しています" in m]) == 1


def test_failed_engine_rests_then_is_retried():
    clock = Clock()
    tr, calls, logs, fail = make_tr("google", key="", fail={"google"}, clock=clock)
    assert tr.translate("a", "ja") == "mymemory:a"
    calls.clear()
    assert tr.translate("b", "ja") == "mymemory:b"
    assert calls == ["mymemory"]            # 休み中の google は呼ばない（連続で断られない）
    clock.t += 31
    fail.clear()
    assert tr.translate("c", "ja") == "google:c"   # 休みが明けたら google に戻る


def test_rest_time_grows_on_repeated_failures():
    clock = Clock()
    tr, calls, logs, fail = make_tr("google", key="", fail={"google"}, clock=clock)
    tr.translate("a", "ja")
    clock.t += 31
    tr.translate("b", "ja")              # google をもう一度試して失敗 → 次は60秒休む
    clock.t += 31
    calls.clear()
    tr.translate("c", "ja")
    assert "google" not in calls


def test_translator_all_fail_raises_and_recovers():
    clock = Clock()
    tr, calls, logs, fail = make_tr("google", key="", fail={"google", "mymemory"}, clock=clock)
    assert tr.order == ["google", "mymemory"]  # キーが無いので DeepL は使わない
    with pytest.raises(TranslateError):
        tr.translate("a", "ja")
    with pytest.raises(TranslateError):
        tr.translate("b", "ja")
    assert len([m for m in logs if "翻訳できませんでした" in m]) == 1  # 警告は1分に1回
    fail.clear()
    clock.t += 400
    assert tr.translate("c", "ja") == "google:c"
    assert any("再びつながりました" in m for m in logs)


def test_deepl_without_key_uses_google():
    tr, calls, logs, _ = make_tr("deepl", key="")
    assert tr.engine == "google"
    assert any("Google翻訳を使います" in m for m in logs)


def test_unknown_engine():
    with pytest.raises(ValueError):
        Translator("bing")


def test_google_response_parsing(monkeypatch=None):
    from gamechat import translate as t
    orig = t._get_json
    t._get_json = lambda url, **kw: [[["プッシュ", "push", None], ["Bへ", " B now", None]], None, "en"]
    try:
        assert t.google_translate("push B now", "ja") == ("プッシュBへ", "en")
    finally:
        t._get_json = orig


def test_mymemory_parsing_and_errors():
    from gamechat import translate as t
    orig = t._get_json
    try:
        seen = {}

        def ok(url, **kw):
            seen["url"] = url
            return {"responseStatus": 200, "responseData": {"translatedText": "急いでBへ"}}
        t._get_json = ok
        assert t.mymemory_translate("快去B点", "ja") == ("急いでBへ", "zh")
        assert "zh-CN%7Cja" in seen["url"]
        t._get_json = lambda url, **kw: {"responseStatus": 429, "responseData": {"translatedText": ""},
                                         "responseDetails": "limit"}
        with pytest.raises(TranslateError):
            t.mymemory_translate("hello", "ja")
    finally:
        t._get_json = orig


def test_voice_falls_back_to_whisper_when_translation_fails():
    from gamechat.voice import VoiceTranslator

    class Seg:
        def __init__(self, text):
            self.text = text

    class Model:
        def transcribe(self, audio, task, **kw):
            return ([Seg("裏取りして" if task == "transcribe" else "Go around.")], None)

    class Dicts:
        speech = SpeechDict([{"ja": "裏取り", "en": "flank"}])

    class BrokenTr:
        def translate(self, *a):
            raise TranslateError("down")

    class OkTr:
        def translate(self, text, target, source=None):
            return f"<{text}>"

    assert VoiceTranslator(Model(), "google", OkTr(), Dicts()).to_english(None) == "<flank して>"
    assert VoiceTranslator(Model(), "google", BrokenTr(), Dicts()).to_english(None) == "Go around."


# ---------- 自分用の設定・辞書 ----------
def test_ensure_user_files(tmp_path):
    default = tmp_path / "settings.default.toml"
    default.write_text('game = "apex"\n', encoding="utf-8")
    settings = tmp_path / "settings.toml"
    user = tmp_path / "user"
    created = config.ensure_user_files(str(settings), str(default), str(user))
    assert settings.read_text(encoding="utf-8") == 'game = "apex"\n'
    assert (user / "slang.csv").exists() and (user / "speech.csv").exists()
    assert len(created) == 4  # settings.toml・slang.csv・speech.csv・ignore.txt
    # 2回目は何も作らない（自分の設定を上書きしない）
    settings.write_text('game = "r6s"\n', encoding="utf-8")
    assert config.ensure_user_files(str(settings), str(default), str(user)) == []
    assert settings.read_text(encoding="utf-8") == 'game = "r6s"\n'


def test_partial_user_settings_merge_with_defaults(tmp_path):
    p = tmp_path / "settings.toml"
    p.write_text('game = "r6s"\n[voice]\nhotkey = "mouse4"\n', encoding="utf-8")
    s = config.load_settings(str(p))
    assert s["game"] == "r6s"
    assert s["voice"]["hotkey"] == "mouse4"
    assert s["voice"]["preroll"] == 0.4          # 書いていない項目は初期値
    assert s["overlay"]["position"] == "above"


def test_user_dictionary_has_top_priority(tmp_path):
    user = tmp_path / "user"
    config.ensure_user_files(str(tmp_path / "s.toml"), str(tmp_path / "none"), str(user))
    with open(user / "slang.csv", "a", encoding="utf-8") as f:
        f.write("gg,good game,おつ！\n")
    with open(user / "speech.csv", "a", encoding="utf-8") as f:
        f.write("裏取り,go around\n")
    prof = config.load_profile("bf6")
    slang = SlangDict.load(config.dictionary_paths(prof, "slang", user_dir=str(user)))
    speech = SpeechDict.load(config.dictionary_paths(prof, "speech", user_dir=str(user)))
    assert slang.lookup_whole("gg") == "おつ！"
    assert speech.apply("裏取りして") == "go around して"


def test_default_settings_file_matches_code_defaults():
    """settings.default.toml と config.DEFAULT_SETTINGS の項目がずれていないか"""
    with open(config.DEFAULT_SETTINGS_PATH, "rb") as f:
        file_data = tomllib.load(f)

    def keys(d, prefix=""):
        out = set()
        for k, v in d.items():
            out.add(prefix + k)
            if isinstance(v, dict):
                out |= keys(v, prefix + k + ".")
        return out

    assert keys(file_data) == keys(config.DEFAULT_SETTINGS)


# ---------- マイクの選択 ----------
DEVICES = [(0, "Microsoft Sound Mapper - Input", False), (3, "マイク (Blue Yeti)", True),
           (7, "Headset Microphone (HyperX)", False)]


def test_pick_device():
    assert pick_device(-1, DEVICES) is None
    assert pick_device("", DEVICES) is None
    assert pick_device(3, DEVICES) == 3
    assert pick_device("7", DEVICES) == 7
    assert pick_device("yeti", DEVICES) == 3
    assert pick_device("HyperX", DEVICES) == 7
    with pytest.raises(ValueError):
        pick_device(99, DEVICES)
    with pytest.raises(ValueError):
        pick_device("nothing", DEVICES)


# ---------- その他 ----------
def test_log_tee_writes_timestamps():
    console, logfile = io.StringIO(), io.StringIO()
    import threading
    t = _Tee(console, logfile, threading.Lock())
    t.write("hello\nwor")
    t.write("ld\n")
    assert console.getvalue() == "hello\nworld\n"
    lines = logfile.getvalue().splitlines()
    assert len(lines) == 2 and lines[0].endswith("  hello") and lines[1].endswith("  world")


def test_missing_modules():
    assert missing_modules([("os", "os"), ("no_such_module_xyz", "xyz")]) == ["xyz"]


def test_requirements_cover_required_modules():
    from gamechat.app import REQUIRED_MODULES
    with open(os.path.join(config.ROOT, "requirements.txt"), encoding="utf-8") as f:
        reqs = {ln.split(">")[0].split("=")[0].strip().lower() for ln in f if ln.strip()}
    for _, pip_name in REQUIRED_MODULES:
        assert pip_name.lower() in reqs, pip_name


# ---------- 実際のログで出た行（BF6・日本語表示のPC） ----------
def bf6_filter():
    from gamechat.textproc import LineFilter
    chat = config.load_profile("bf6")["chat"]
    return LineFilter(chat["strip_patterns"], chat["ignore_patterns"])


def fake_ja_aware(text):
    """Google の言語判定のまねをする：日本語っぽい行は None（表示しない）"""
    import re
    if re.search(r"[぀-ヿ]", text) or any(w in text for w in ("名前", "今日", "表示")):
        return None
    return f"<訳>{text}"


def test_bf6_ui_text_is_ignored():
    from gamechat.chatreader import process_line
    slang = SlangDict()
    f = bf6_filter()
    for line in ["于 表示切替 E", "于H 表示切替", "于下回表示切替", "于以 表示切替", "上下左右仁移動"]:
        out = process_line(line, slang, fake_ja_aware, line_filter=f)
        assert out is None, (line, out)


def test_bf6_tab_hint_removed_and_tag_kept():
    from gamechat.chatreader import process_line
    out = process_line("[全具] 偽分功。 [TAB]于儿", SlangDict(), fake_ja_aware, line_filter=bf6_filter())
    assert out == ("[全具]", "<訳>偽分功。", "偽分功。")
    out = process_line("[ALL] Sniper77: push B now", SlangDict(), fake_ja_aware, line_filter=bf6_filter())
    assert out == ("[ALL] Sniper77", "<訳>push B now", "push B now")


def test_own_message_echo_is_skipped():
    from gamechat.chatreader import process_line
    out = process_line("[全員] nice game.", SlangDict(), fake_ja_aware,
                       recent_sent=["nice game."], line_filter=bf6_filter())
    assert out is None


def test_translator_reports_source_language():
    tr, calls, logs, _ = make_tr("google")
    tr._backends["google"] = lambda text, target, source=None: ("名前", "ja")
    assert tr.translate("名前", "ja") == "名前" and tr.last_lang == "ja"
    tr._backends["google"] = lambda text, target, source=None: ("やあ", "en")
    assert tr.translate("hi", "ja") == "やあ" and tr.last_lang == "en"
    assert tr.translate("名前", "ja") == "名前" and tr.last_lang == "ja"   # キャッシュでも言語を覚えている


def test_unicode_typing_is_default():
    assert config.load_profile("bf6")["chat"]["type_mode"] == "unicode"
    assert config.load_profile("generic")["chat"]["type_mode"] == "unicode"


# ---------- 0.2.0 実機テストで見つかった問題 ----------
def test_single_cjk_char_garbage_is_not_translated():
    from gamechat.textproc import worth_translating
    assert not worth_translating("占")
    assert not worth_translating("一3")
    assert worth_translating("快去B点")
    # 1文字のスラングは辞書で拾う
    from gamechat.chatreader import process_line
    slang = SlangDict([{"term": "冲", "expand": "", "ja": "突撃！"}])
    assert process_line("A: 冲", slang, lambda t: t)[1] == "突撃！"
    assert process_line("占", slang, lambda t: "X") is None


def test_user_ignore_list_is_literal_and_combined(tmp_path):
    from gamechat.chatreader import build_filter, process_line
    user = tmp_path / "user"
    config.ensure_user_files(str(tmp_path / "s.toml"), str(tmp_path / "none"), str(user))
    with open(user / "ignore.txt", "a", encoding="utf-8") as f:
        f.write("[MAP]\nPress F\n")
    ig = config.user_ignore(str(user))
    assert ig == ["[MAP]", "Press F"]
    f = build_filter(config.load_profile("bf6")["chat"], {"ignore_patterns": [], "strip_patterns": []}, ig)
    tr = lambda t: f"<{t}>"  # noqa: E731
    assert process_line("[MAP] open map", SlangDict(), tr, line_filter=f) is None   # [ ] は文字としてそのまま
    assert process_line("Press F to revive", SlangDict(), tr, line_filter=f) is None
    assert process_line("Bob: push B", SlangDict(), tr, line_filter=f)[1] == "<push B>"


# ---------- フルスクリーン対応・表示位置 ----------
MONS = [{"left": 0, "top": 0, "width": 1920, "height": 1080},
        {"left": 1920, "top": 0, "width": 2560, "height": 1440}]


def test_monitor_of_and_fullscreen_detection():
    from gamechat.capture import covers_monitor, monitor_of
    assert monitor_of((0, 0, 1920, 1080), MONS) is MONS[0]
    assert monitor_of((1920, 0, 4480, 1440), MONS) is MONS[1]       # 2台目でフルスクリーン
    assert monitor_of(None, MONS) is MONS[0]
    assert covers_monitor((1920, 0, 4480, 1440), MONS[1])
    assert covers_monitor((-8, -8, 1928, 1088), MONS[0])             # 枠の分はみ出していても全体扱い
    assert not covers_monitor((100, 100, 1300, 800), MONS[0])        # 小さいウィンドウ
    assert not covers_monitor(None, MONS[0])


def test_dxcam_region_is_mapped_to_the_right_monitor():
    import numpy as np
    from gamechat.capture import Grabber

    class Cam:
        def __init__(self, name):
            self.name, self.calls = name, []

        def grab(self, region):
            self.calls.append(region)
            l, t, r, b = region
            return np.zeros((b - t, r - l, 3), np.uint8)

    g = Grabber("mss")
    g._dx_ok = True
    a, b = Cam("main"), Cam("second")
    g._dx = {0: (a, (0, 0, 1920, 1080)), 1: (b, (1920, 0, 4480, 1440))}
    img = g.grab({"left": 1950, "top": 60, "width": 400, "height": 250})
    assert b.calls == [(30, 60, 430, 310)] and a.calls == []
    assert img.shape == (250, 400, 3) and g.last_method == "dxcam"


def test_dxcam_unchanged_frame_and_fallback():
    from gamechat.capture import Grabber

    class Same:
        def grab(self, region):
            return None

    logs = []
    g = Grabber("mss", log=logs.append)
    g._dx_ok = True
    g._dx = {0: (Same(), (0, 0, 1920, 1080))}
    assert g.grab({"left": 10, "top": 10, "width": 50, "height": 50}) == "same"

    class Broken:
        def grab(self, region):
            raise OSError("device lost")

    g._dx = {0: (Broken(), (0, 0, 1920, 1080))}
    g._mss_grab = lambda region: "mss-image"
    assert g.grab({"left": 10, "top": 10, "width": 50, "height": 50}) == "mss-image"
    assert g.last_method == "mss" and any("mss を使います" in m for m in logs)


def test_overlay_position_is_saved_per_game(tmp_path):
    p = str(tmp_path / "overlay.json")
    assert config.load_overlay_pos("bf6", p) is None
    config.save_overlay_pos("bf6", {"x": 2000, "y": 50, "font_size": 18}, p)
    config.save_overlay_pos("apex", {"x": 10, "y": 10}, p)
    assert config.load_overlay_pos("bf6", p) == {"x": 2000, "y": 50, "font_size": 18}
    config.save_overlay_pos("bf6", None, p)        # 自動の位置に戻す
    assert config.load_overlay_pos("bf6", p) is None
    assert config.load_overlay_pos("apex", p) == {"x": 10, "y": 10}


# ---------- ショートカットキー ----------
def _combo_vks(text):
    # winkeys は Windows 専用なので、同じ表を使って組み合わせを作る
    table = {"alt": 0x12, "ctrl": 0x11, "shift": 0x10, "win": 0x5B, "f10": 0x79, "f9": 0x78}
    return [table[p] for p in text.split("+")]


def _combo_pressed():
    import importlib.util
    import pathlib
    import types
    # winkeys を Windows 以外でも読み込めるよう、ctypes の Windows 部分をまねる
    import ctypes
    if not hasattr(ctypes, "WinDLL"):
        class _Fn:
            argtypes = restype = None

            def __call__(self, *a):
                return 0

        class _Dll:
            def __getattr__(self, n):
                f = _Fn()
                setattr(self, n, f)
                return f
        ctypes.WinDLL = lambda *a, **k: _Dll()
        ctypes.windll = types.SimpleNamespace(shcore=_Dll(), shell32=_Dll())
    from gamechat.winkeys import combo_pressed
    return combo_pressed


def test_hotkeys_ignore_alt_and_win():
    combo_pressed = _combo_pressed()
    f10 = _combo_vks("f10")

    def down_of(*names):
        held = set(_combo_vks("+".join(names)))
        return lambda vk: vk in held

    assert combo_pressed(f10, down_of("f10"))
    assert not combo_pressed(f10, down_of("alt", "f10"))       # NVIDIA の Alt+F10
    assert not combo_pressed(f10, down_of("win", "alt", "f10"))
    assert combo_pressed(f10, down_of("shift", "f10"))           # Shift（走りながら）は反応してよい
    assert combo_pressed(_combo_vks("alt+f10"), down_of("alt", "f10"))  # 自分で Alt を含めた場合は反応
    assert not combo_pressed(_combo_vks("ctrl+f10"), down_of("f10"))


def test_key_settings_are_validated():
    _combo_pressed()
    from gamechat.app import check_keys
    s = config.load_settings(os.path.join(config.ROOT, "_none_.toml"))
    check_keys(s)
    s["chat_translate"]["toggle_key"] = "ctrl+f10"
    check_keys(s)
    s["overlay"]["move_key"] = "ctrl+F10"
    with pytest.raises(ValueError):
        check_keys(s)          # 同じキーが2つの機能に
    s["overlay"]["move_key"] = "f7"
    s["chat_translate"]["toggle_key"] = "hoge"
    with pytest.raises(ValueError):
        check_keys(s)


# ---------- 設定画面 ----------
def test_settings_text_update_keeps_comments_and_types():
    text = open(config.DEFAULT_SETTINGS_PATH, encoding="utf-8").read()
    new = config.update_settings_text(text, {
        (None, "game"): "apex", ("voice", "hotkey"): "mouse4", ("voice", "auto_send"): False,
        ("voice", "input_device"): 'マイク (Logicool "G533")', ("overlay", "alpha"): 0.7,
        ("chat_translate", "toggle_key"): "ctrl+f10", ("api", "deepl_key"): "ab\\c:fx",
        ("voice", "input_device_extra"): 3, ("newsection", "x"): 1})
    d = tomllib.loads(new)
    assert d["game"] == "apex" and d["voice"]["hotkey"] == "mouse4" and d["voice"]["auto_send"] is False
    assert d["voice"]["input_device"] == 'マイク (Logicool "G533")'
    assert d["overlay"]["alpha"] == 0.7 and d["chat_translate"]["toggle_key"] == "ctrl+f10"
    assert d["api"]["deepl_key"] == "ab\\c:fx"
    assert d["voice"]["input_device_extra"] == 3 and d["newsection"] == {"x": 1}
    assert new.count("#") == text.count("#")          # コメントは消えない
    assert d["voice"]["max_seconds"] == tomllib.loads(text)["voice"]["max_seconds"]  # 他の値はそのまま


def test_settings_file_update_refuses_broken_result(tmp_path):
    p = tmp_path / "settings.toml"
    p.write_text('game = "bf6"\n[voice]\nhotkey = "f8"  # 録音キー\n', encoding="utf-8")
    config.update_settings_file({("voice", "hotkey"): "f6"}, str(p), config.DEFAULT_SETTINGS_PATH)
    assert p.read_text(encoding="utf-8") == 'game = "bf6"\n[voice]\nhotkey = "f6"  # 録音キー\n'


def test_key_capture_names():
    from gamechat.keynames import combo_name, keysym_to_name
    assert keysym_to_name("F8") == "f8" and keysym_to_name("Caps_Lock") == "caps lock"
    assert keysym_to_name("Shift_L") is None and keysym_to_name("v") == "v"
    assert keysym_to_name("KP_5") == "num5" and keysym_to_name("Prior") == "page up"
    assert combo_name("F10", 0x0004) == "ctrl+f10"
    assert combo_name("F10", 0x0004 | 0x0001) == "ctrl+shift+f10"
    assert combo_name("F10", 0x20000) == "alt+f10"
    assert combo_name("F10", 0x0008) == "f10"           # Num Lock は修飾キーにしない
    assert combo_name("F8", 0x0004, allow_mods=False) == "f8"
    assert combo_name("Shift_L", 0x0001) is None
    # 作った名前は設定として読める
    _combo_pressed()
    from gamechat.winkeys import parse_combo
    for n in ("ctrl+f10", "caps lock", "num5", "page up", "`", "mouse4"):
        parse_combo(n)


def test_invalid_settings_are_not_saved(tmp_path):
    _combo_pressed()
    from gamechat.app import check_keys
    p = tmp_path / "settings.toml"
    p.write_text('[chat_translate]\ntoggle_key = "f10"\n', encoding="utf-8")
    with pytest.raises(ValueError):
        config.update_settings_file({("chat_translate", "toggle_key"): "hoge"}, str(p),
                                    config.DEFAULT_SETTINGS_PATH, validate=check_keys)
    assert 'toggle_key = "f10"' in p.read_text(encoding="utf-8")   # 元のまま
    config.update_settings_file({("chat_translate", "toggle_key"): "ctrl+f10"}, str(p),
                                config.DEFAULT_SETTINGS_PATH, validate=check_keys)
    assert 'toggle_key = "ctrl+f10"' in p.read_text(encoding="utf-8")
