# -*- coding: utf-8 -*-
"""Windows がなくても動く部分（文字処理・辞書・設定）のテスト。 python -m pytest tests"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gamechat import config  # noqa: E402
from gamechat.chatreader import process_line  # noqa: E402
from gamechat.ocr import group_lines  # noqa: E402
from gamechat.textproc import (SeenLines, SlangDict, SpeechDict, clean_ascii,  # noqa: E402
                               parse_line, worth_translating)


def fake_translate(text):
    return f"<訳>{text}"


NO_USER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_no_user_dir")


def slang_for(game):
    # 開発者自身の user/ 辞書に影響されないよう、配布する辞書だけでテストする
    return SlangDict.load(config.dictionary_paths(config.load_profile(game), "slang", user_dir=NO_USER_DIR))


def speech_for(game):
    return SpeechDict.load(config.dictionary_paths(config.load_profile(game), "speech", user_dir=NO_USER_DIR))


def test_group_lines_joins_name_and_message():
    res = [
        ([[10, 10], [90, 10], [90, 30], [10, 30]], "[ALL] xXSniper:", 0.95),
        ([[95, 12], [300, 12], [300, 31], [95, 31]], "anyone want to squad up?", 0.93),
        ([[10, 40], [80, 40], [80, 60], [10, 60]], "Bob_77:", 0.9),
        ([[85, 41], [250, 41], [250, 59], [85, 59]], "push B now", 0.88),
        ([[10, 70], [60, 70], [60, 90], [10, 90]], "##", 0.3),
    ]
    assert group_lines(res) == ["[ALL] xXSniper: anyone want to squad up?", "Bob_77: push B now"]
    assert group_lines(None) == []


def test_parse_and_filter():
    assert parse_line("王五：快去B点") == ("王五", "快去B点")
    assert parse_line("no name here") == (None, "no name here")
    assert worth_translating("push B now")
    assert worth_translating("快去B点")
    assert not worth_translating("よろしく")
    assert not worth_translating("66")


def test_seen_lines_ignores_ocr_noise():
    s = SeenLines()
    assert s.is_new("xXSniper: anyone want to squad up?")
    assert not s.is_new("xXSniper: anyone want t0 squad up?")
    assert s.is_new("小龙: 有人一起组队吗？")
    assert not s.is_new("小龙：有人一起组队吗")


def test_clean_ascii_converts_fullwidth():
    assert clean_ascii("Ｐｕｓｈ　Ｂ！") == "Push B!"
    assert clean_ascii("“Go” — now…") == '"Go" - now...'
    assert clean_ascii("hello 日本 world") == "hello world"


def test_slang_whole_message():
    slang = slang_for("generic")
    assert process_line("Bob: gg", slang, fake_translate) == ("Bob", "お疲れさま（GG）", "gg")
    assert process_line("小龙: 666", slang, fake_translate)[1] == "すごい（666）"
    assert process_line("小龙: 冲", slang, fake_translate)[1] == "突撃！"


def test_slang_expand_in_sentence():
    slang = slang_for("generic")
    assert process_line("Bob: ns bro", slang, fake_translate)[1] == "<訳>nice shot bro"
    # 単語の一部は置き換えない（"guns" の中の "ns" など）
    assert process_line("Bob: nice guns", slang, fake_translate)[1] == "<訳>nice guns"
    # 漢字1文字は文の中では置き換えない
    assert process_line("小龙: 上面有人", slang, fake_translate)[1] == "<訳>上面有人"
    assert process_line("小龙: 这人开挂", slang, fake_translate)[1] == "<訳>这人使用作弊软件"


def test_game_dictionary_overrides_common():
    assert process_line("A: op", slang_for("generic"), fake_translate)[1] == "強すぎ"
    assert process_line("A: op", slang_for("valorant"), fake_translate)[1] == "オペレーター（OP）"


def test_skips_own_messages():
    slang = slang_for("generic")
    assert process_line("Me: push b", slang, fake_translate, my_name="me") is None
    assert process_line("X: Flank left", slang, fake_translate, recent_sent=["Flank left"]) is None
    assert process_line("X: こんにちは", slang, fake_translate) is None


def test_speech_dictionary():
    sp = speech_for("bf6")
    assert sp.apply("裏取りして") == "flank して"
    assert sp.apply("分隊長にビーコン置いて") == "squad leader に beacon 置いて"
    assert "裏取り" in sp.prompt()


def test_all_profiles_load():
    ids = [g for g, _ in config.list_profiles()]
    assert {"bf6", "apex", "valorant", "r6s", "generic"} <= set(ids)
    for gid in ids:
        p = config.load_profile(gid)
        assert p["chat"]["open_key"]
        for kind in ("slang", "speech"):
            for fn in p["dictionary"][kind]:
                assert os.path.exists(os.path.join(config.PROFILE_DIR, fn)), fn
            SlangDict.load(config.dictionary_paths(p, "slang"))
            SpeechDict.load(config.dictionary_paths(p, "speech"))


def test_settings_file_loads():
    s = config.load_settings()
    assert s["game"] in [g for g, _ in config.list_profiles()]
    assert s["voice"]["translator"] in ("google", "deepl", "whisper")
