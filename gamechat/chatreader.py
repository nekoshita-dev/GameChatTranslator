# -*- coding: utf-8 -*-
"""相手のチャット：画面の読み取り → スラング辞書 → 日本語に翻訳"""
import time

import numpy as np

from .textproc import LineFilter, norm_key, parse_line, similar, split_tag, worth_translating


def process_line(line, slang, translate, my_name="", recent_sent=(), line_filter=None):
    """読み取った1行を処理する。表示すべきなら (名前, 日本語, 元の本文)、不要なら None

    translate(text) は訳を返す。表示しない（元が日本語など）ときは None を返す。
    """
    if line_filter:
        line = line_filter.clean(line)
        if not line:
            return None
    tag, rest = split_tag(" ".join(line.split()))
    name, msg = parse_line(rest)
    if name is None and tag:
        name = tag
    elif tag:
        name = f"{tag} {name}"
    if not msg:
        return None
    if my_name and name and my_name.lower() in name.lower():
        return None
    if any(similar(msg, s) for s in recent_sent):
        return None
    direct = slang.lookup_whole(msg)  # "gg" "666" など、スラング1語だけの発言
    if direct:
        return name, direct, msg
    if not worth_translating(msg):
        return None
    ja = translate(slang.expand(msg))
    if not ja:
        return None
    return name, ja, msg


def build_filter(profile_chat, settings_chat, user_ignore=()):
    """プロファイル・settings.toml の正規表現と、user/ignore.txt の文字列から行フィルターを作る"""
    import re
    strip = list(profile_chat.get("strip_patterns", [])) + list(settings_chat.get("strip_patterns", []))
    ignore = list(profile_chat.get("ignore_patterns", [])) + list(settings_chat.get("ignore_patterns", []))
    ignore += [re.escape(x) for x in user_ignore]
    return LineFilter(strip, ignore)


def chat_loop(state, ui_q, settings, dicts, translator):
    cfg = settings["chat_translate"]
    debug = settings["debug"]
    try:
        from .capture import Grabber
        from .ocr import ChatOCR
        ocr = ChatOCR()
        grabber = Grabber(cfg.get("capture", "auto"))
    except Exception as e:
        print(f"チャット読み取り機能を開始できませんでした: {e}")
        return

    from .textproc import SeenLines
    from .winkeys import foreground_title
    seen = SeenLines()
    last_frame = None
    skipped_for_window = False
    first_method_logged = False
    filter_src = None
    line_filter = None

    def translate(text):
        out = translator.translate(text, "ja")
        if (translator.last_lang or "").lower().startswith("ja"):
            return None  # 元から日本語（ゲームの画面表示など）
        if norm_key(out) == norm_key(text):
            return None  # 訳しても変わらない（名前・数字など）
        return out

    while True:
        time.sleep(cfg["poll_interval"])
        req = state.snap_request
        if req:
            state.snap_request = None
            mon, title, rect = req
            try:
                img = grabber.grab_fresh(mon)
                ui_q.put(("snapshot", img, mon, title, rect))
            except Exception as e:
                print(f"画面を撮れませんでした: {e}")
        region = state.region
        if not state.enabled or not region or state.sending:
            continue
        # 範囲を選んだときのウィンドウ（ゲーム）が手前にあるときだけ読む
        window = region.get("window")
        if window and foreground_title() != window:
            if debug and not skipped_for_window:
                print(f"  （「{window}」が手前にないので読み取りを休みます）")
            skipped_for_window = True
            last_frame = None
            continue
        skipped_for_window = False
        if filter_src is not dicts.ignore:  # F11 で無視リストを読み直したら作り直す
            try:
                line_filter = build_filter(dicts.profile["chat"], cfg, dicts.ignore)
            except Exception as e:
                print(f"※ ignore_patterns / strip_patterns の書き方が正しくありません: {e}")
                line_filter = None
            filter_src = dicts.ignore
        try:
            frame = grabber.grab(region)
            if isinstance(frame, str):
                continue  # 画面が変わっていない
            if not first_method_logged:
                first_method_logged = True
                print(f"画面の撮影方法: {grabber.last_method}"
                      + ("（フルスクリーンにも対応）" if grabber.last_method == "dxcam" else ""))
            small = frame[::4, ::4]
            if last_frame is not None and small.shape == last_frame.shape \
                    and np.array_equal(small, last_frame):
                continue  # 画面が変わっていなければ読み取らない
            last_frame = small.copy()

            for line in ocr.read_lines(frame, cfg["min_score"]):
                if not seen.is_new(line):
                    continue
                if debug:
                    print(f"  [読取] {line}")
                try:
                    out = process_line(line, dicts.slang, translate,
                                       cfg["my_name"], list(state.recent_sent), line_filter)
                except Exception as e:
                    if debug:
                        print(f"  翻訳エラー: {e}")
                    continue
                if out:
                    name, ja, msg = out
                    print(f"  [受信] {line}\n         → {ja}")
                    ui_q.put(("line", name, ja, msg))
        except Exception as e:
            if debug:
                print(f"  読み取りエラー: {e}")
            time.sleep(1)
