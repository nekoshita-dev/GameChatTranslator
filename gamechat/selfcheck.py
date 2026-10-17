# -*- coding: utf-8 -*-
"""動作チェック（run.bat --check / check.bat）

ゲームを起動しなくても、部品が正しく動くかを順番に確かめ、結果を data/logs/check.txt に保存します。
不具合報告のときは、このファイルを添付してください。
"""
import os
import platform
import sys
import time
import traceback

from . import __version__, config

RESULTS = []


def _step(title):
    def deco(fn):
        def run(*a, **kw):
            print(f"\n■ {title}")
            t0 = time.time()
            try:
                detail = fn(*a, **kw) or ""
                status = "OK"
            except SkipCheck as e:
                detail, status = str(e), "SKIP"
            except Exception as e:
                detail = f"{type(e).__name__}: {e}"
                status = "NG"
                if os.environ.get("GAMECHAT_DEBUG"):
                    traceback.print_exc()
            dt = time.time() - t0
            print(f"  → {status}  {detail}  ({dt:.1f}秒)")
            RESULTS.append((status, title, detail))
            return status == "OK"
        return run
    return deco


class SkipCheck(Exception):
    pass


@_step("Python と Windows")
def check_env():
    v = sys.version_info
    info = f"Python {v.major}.{v.minor}.{v.micro} / {platform.platform()}"
    if v < (3, 11):
        raise RuntimeError(info + "（3.11 以上が必要）")
    return info


@_step("必要な部品（ライブラリ）")
def check_modules():
    from .app import missing_modules
    missing = missing_modules()
    if missing:
        raise RuntimeError("入っていない: " + ", ".join(missing) + "（setup.bat を実行してください）")
    return "すべて入っています"


@_step("設定ファイルとゲームプロファイル")
def check_config():
    config.ensure_user_files()
    s = config.load_settings()
    ids = [g for g, _ in config.list_profiles()]
    p = config.load_profile(s["game"])
    from .app import check_keys
    check_keys(s)
    v = s["voice"]
    return f"ゲーム: {p['name']} / プロファイル {len(ids)} 個 / 録音キー {v['hotkey']}"


@_step("辞書")
def check_dicts():
    from .textproc import SlangDict, SpeechDict
    s = config.load_settings()
    p = config.load_profile(s["game"])
    slang = SlangDict.load(config.dictionary_paths(p, "slang"))
    speech = SpeechDict.load(config.dictionary_paths(p, "speech"))
    assert slang.lookup_whole("gg"), "スラング辞書に gg がありません"
    return f"スラング {len(slang)} 語 / 用語 {len(speech)} 語"


@_step("Windows のキー操作（判定・管理者権限）")
def check_keys():
    from .winkeys import is_admin, is_down, vk_of
    is_down(vk_of("f8"))
    return "管理者権限: " + ("あり" if is_admin() else "なし（チェックでは問題ありません。run.bat から起動すると付きます）")


@_step("マイク（2秒録音して音量を測る）")
def check_mic():
    import numpy as np
    from .voice import Mic, input_devices, pick_device
    s = config.load_settings()
    devs = input_devices()
    if not devs:
        raise RuntimeError("マイクが見つかりません")
    dev = pick_device(s["voice"]["input_device"], devs)
    name = next((n for i, n, d in devs if (i == dev if dev is not None else d)), "既定")
    print("  2秒間、何か話してください…")
    mic = Mic(dev, preroll=0, postroll=0)
    mic.ensure_open()
    mic.start()
    time.sleep(2)
    audio = mic.stop()
    mic.close()
    peak = float(np.max(np.abs(audio))) if audio is not None and len(audio) else 0.0
    db = 20 * np.log10(peak) if peak > 0 else -99
    note = ""
    if peak < 0.003:
        note = ("  ※ ほぼ無音です。話していなかった場合は無視してOK。話したのにこの表示なら、"
                "マイクのミュート（ヘッドセットのマイクを上げるとミュートになる機種もあります）・入力音量を確認してください")
    elif db < -40:
        note = "  ※ 小さめです。Windowsのマイク入力音量を上げると認識が良くなります"
    return f"{name} / 最大音量 {db:.0f} dB / マイク数 {len(devs)}{note}"


@_step("翻訳（英語・中国語 → 日本語、日本語 → 英語）")
def check_translate():
    from .translate import Translator
    s = config.load_settings()
    tr = Translator(s["chat_translate"]["translator"], s["api"]["deepl_key"], label="翻訳チェック")
    en = tr.translate("push B now", "ja")
    zh = tr.translate("快去B点", "ja")
    ja = tr.translate("裏取りして", "en", "ja")
    used = tr.last_engine
    # 予備のエンジンも個別に確かめる（本番で切り替わったときに使えるか）
    spare = []
    for name in tr.order[1:]:
        try:
            tr._backends[name]("good game", "ja")
            spare.append(f"{name}: OK")
        except Exception as e:
            spare.append(f"{name}: NG（{str(e)[:60]}）")
    return (f"「push B now」→「{en}」 / 「快去B点」→「{zh}」 / 「裏取りして」→「{ja}」"
            f"（{used}）  予備 → {' / '.join(spare) or 'なし'}")


@_step("画面の文字の読み取り（OCR）")
def check_ocr():
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    from .ocr import ChatOCR

    img = Image.new("RGB", (640, 120), (30, 34, 40))
    d = ImageDraw.Draw(img)
    font = None
    for path in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\YuGothM.ttc",
                 r"C:\Windows\Fonts\meiryo.ttc", r"C:\Windows\Fonts\arial.ttf"):
        if os.path.exists(path):
            font = ImageFont.truetype(path, 26)
            break
    font = font or ImageFont.load_default()
    d.text((10, 15), "[ALL] Sniper77: push B now", fill=(240, 240, 240), font=font)
    d.text((10, 65), "[ALL] 小龙: 快去B点", fill=(240, 240, 240), font=font)
    bgr = np.ascontiguousarray(np.asarray(img)[:, :, ::-1])
    ocr = ChatOCR()
    t0 = time.time()
    lines = ocr.read_lines(bgr)
    dt = time.time() - t0
    empty = ocr.read_lines(np.zeros((80, 300, 3), np.uint8))  # 文字が無い画面でも落ちない
    joined = " | ".join(lines)
    if "push" not in joined.lower():
        raise RuntimeError(f"英語が読めませんでした: {joined!r}")
    zh_ok = "快去" in joined
    return f"読み取り結果: {joined} / 1回 {dt:.2f}秒 / 空の画面: {len(empty)} 行" + \
        ("" if zh_ok else "  ※ 中国語が読めていません")


@_step("画面の撮影（チャット欄の読み取りに使用）")
def check_capture():
    from .capture import Grabber
    g = Grabber("auto")
    mons = g.monitors()
    m = mons[0]
    img = g.grab_fresh({"left": m["left"], "top": m["top"], "width": 200, "height": 100})
    note = "（フルスクリーンのゲームも撮れます）" if g.last_method == "dxcam" else \
        "（フルスクリーンのゲームは撮れないことがあります。setup.bat をもう一度実行すると改善する場合があります）"
    g.close()
    return f"モニター {len(mons)} 台 / メイン {m['width']}x{m['height']} / 撮影方法 {g.last_method}{note} / {img.shape[1]}x{img.shape[0]}"


@_step("音声認識（Whisper モデルの読み込みと認識）")
def check_whisper(skip):
    if skip:
        raise SkipCheck("--quick のため省略")
    import numpy as np
    from .voice import load_model
    s = config.load_settings()
    model = load_model(s["voice"]["model"])
    t0 = time.time()
    list(model.transcribe(np.zeros(16000 * 2, np.float32), language="ja")[0])
    return f"2秒の音声の処理 {time.time() - t0:.1f}秒"


def main(quick=False):
    from .logutil import start_logging
    start_logging(config.LOG_DIR, "check.txt")
    print(f"GameChat Translator {__version__} 動作チェック")
    print("=" * 60)
    check_env()
    if not check_modules():
        print("\n必要な部品が足りないため、ここで終わります。setup.bat を実行してください。")
    else:
        check_config()
        check_dicts()
        check_keys()
        check_capture()
        check_ocr()
        check_translate()
        check_mic()
        check_whisper(quick)

    print("\n" + "=" * 60)
    print("結果")
    for status, title, detail in RESULTS:
        print(f"  [{status:>4}] {title}")
    ng = [r for r in RESULTS if r[0] == "NG"]
    print("=" * 60)
    if ng:
        print(f"{len(ng)} 個の項目で問題がありました。上の「NG」の行を確認してください。")
    else:
        print("すべて問題ありません。run.bat で起動できます。")
    print(f"結果は {os.path.relpath(os.path.join(config.LOG_DIR, 'check.txt'), config.ROOT)} にも保存しました。")
    return 1 if ng else 0
