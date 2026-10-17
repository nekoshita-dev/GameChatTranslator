# -*- coding: utf-8 -*-
"""自分の発言：マイク録音 → 音声認識（Whisper）→ 英語に翻訳"""
import os
import sys
import threading
import time
from collections import deque

import numpy as np

SAMPLE_RATE = 16000

HALLUCINATIONS = (
    "thank you for watching", "thanks for watching", "please subscribe",
    "subtitles by", "ご視聴ありがとうございました", "チャンネル登録",
    "ゲーム中のボイスチャット", "用語:",  # 無音のとき認識用のヒント文がそのまま出ることがある
)


# ---------- マイクの選択 ----------
def input_devices():
    """入力デバイスの一覧 [(番号, 名前, 既定かどうか)]"""
    import sounddevice as sd
    try:
        default_in = sd.default.device[0]
    except Exception:
        default_in = -1
    return [(i, d["name"], i == default_in)
            for i, d in enumerate(sd.query_devices()) if d["max_input_channels"] > 0]


def pick_device(spec, devices):
    """設定の input_device（-1 / 番号 / 名前の一部）を、デバイス番号（既定なら None）にする"""
    if spec in (-1, "", None):
        return None
    if isinstance(spec, int) or (isinstance(spec, str) and spec.strip().isdigit()):
        n = int(spec)
        if any(i == n for i, _, _ in devices):
            return n
        raise ValueError(f"マイクの番号 {n} が見つかりません（run.bat --devices で一覧を確認）")
    hits = [(i, name) for i, name, _ in devices if spec.lower() in name.lower()]
    if not hits:
        raise ValueError(f"名前に '{spec}' を含むマイクが見つかりません（run.bat --devices で一覧を確認）")
    return hits[0][0]


# ---------- 録音（マイクは開きっぱなしにして、押す直前の音も残しておく） ----------
class Mic:
    def __init__(self, device=None, preroll=0.4, postroll=0.3):
        self.device = device
        self.preroll = preroll
        self.postroll = postroll
        self.lock = threading.Lock()
        self.recording = False
        self.frames = []
        self.stream = None
        self.rate = SAMPLE_RATE
        self.pre = deque()
        self.pre_len = 0
        self.level = 0.0

    def _callback(self, indata, frames, t, status):
        block = indata[:, 0].copy()
        peak = float(np.max(np.abs(block))) if len(block) else 0.0
        self.level = max(peak, self.level * 0.85)  # 画面の音量メーター用（ゆっくり下がる）
        with self.lock:
            if self.recording:
                self.frames.append(block)
            else:
                self.pre.append(block)
                self.pre_len += len(block)
                limit = int(self.preroll * self.rate)
                while self.pre and self.pre_len - len(self.pre[0]) >= limit:
                    self.pre_len -= len(self.pre.popleft())

    def ensure_open(self):
        """マイクを開く（切断・エラーで止まっていたら開き直す）"""
        import sounddevice as sd
        if self.stream is not None and self.stream.active:
            return
        self.close()
        last_err = None
        for rate in (SAMPLE_RATE, None):  # 16kHzがだめならマイク本来の周波数で
            try:
                if rate is None:
                    rate = int(sd.query_devices(self.device, "input")["default_samplerate"])
                st = sd.InputStream(samplerate=rate, channels=1, dtype="float32",
                                    device=self.device, callback=self._callback)
                st.start()
                self.stream, self.rate = st, rate
                with self.lock:
                    self.pre.clear()
                    self.pre_len = 0
                return
            except Exception as e:
                last_err = e
        raise RuntimeError(f"マイクを開けませんでした: {last_err}")

    def close(self):
        if self.stream is not None:
            try:
                self.stream.close()
            except Exception:
                pass
            self.stream = None

    def start(self):
        self.ensure_open()
        with self.lock:
            self.frames = list(self.pre)
            self.pre.clear()
            self.pre_len = 0
            self.recording = True

    def stop(self):
        time.sleep(self.postroll)
        with self.lock:
            self.recording = False
            frames, self.frames = self.frames, []
        if not frames:
            return None
        audio = np.concatenate(frames)
        if self.rate != SAMPLE_RATE:  # 16kHz に変換
            n = int(len(audio) * SAMPLE_RATE / self.rate)
            audio = np.interp(np.linspace(0, len(audio) - 1, n),
                              np.arange(len(audio)), audio).astype(np.float32)
        return audio


def prepare_audio(audio, auto_gain=True, show_level=True):
    """音量を確認し、小さければ持ち上げる"""
    peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
    if show_level:
        db = 20 * np.log10(peak) if peak > 0 else -99
        bar = "#" * max(0, min(20, int((db + 60) / 3)))
        print(f"  マイク音量 {db:5.0f} dB  [{bar:<20}]")
    if peak < 0.003:
        print("  ※ マイクの音がほぼ入っていません（マイクの選択・ミュート・音量を確認してください）")
    if auto_gain and 0 < peak < 0.5:
        audio = audio * min(0.7 / peak, 50.0)
    return audio.astype(np.float32)


# ---------- Whisper ----------
def _add_cuda_dll_dirs():
    """pipで入れた nvidia-cublas / nvidia-cudnn のDLLを見つけられるようにする"""
    try:
        import nvidia  # noqa
    except ImportError:
        return
    for base in list(getattr(nvidia, "__path__", [])):
        for sub in ("cublas", "cudnn", "cuda_nvrtc"):
            d = os.path.join(base, sub, "bin")
            if os.path.isdir(d):
                os.add_dll_directory(d)
                os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")


MODEL_INFO = {"text": "準備中"}


def load_model(model_size="auto"):
    _add_cuda_dll_dirs()
    from faster_whisper import WhisperModel
    import ctranslate2

    tries = []
    if ctranslate2.get_cuda_device_count() > 0:
        tries.append(("cuda", "float16"))
    tries.append(("cpu", "int8"))

    for device, ctype in tries:
        size = model_size
        if size == "auto":
            size = "medium" if device == "cuda" else "small"
        try:
            print(f"音声認識モデル読み込み中: {size} ({device}) ※初回はダウンロードに数分かかります")
            model = WhisperModel(size, device=device, compute_type=ctype)
            list(model.transcribe(np.zeros(SAMPLE_RATE, dtype=np.float32), language="ja")[0])
            print(f"準備OK: {size} / {device}")
            MODEL_INFO["text"] = f"{size} / {'GPU' if device == 'cuda' else 'CPU'}"
            return model
        except Exception as e:
            print(f"[{device}] で失敗: {e}")
    MODEL_INFO["text"] = "読み込めませんでした"
    raise RuntimeError("音声認識モデルを読み込めませんでした（setup.bat をもう一度実行してください）")


class VoiceTranslator:
    """日本語の音声 → 英語の文"""

    def __init__(self, model, engine, translator, dicts, vad_threshold=0.3):
        self.model = model
        self.engine = engine          # "whisper" / "google" / "deepl"
        self.translator = translator  # Translator（engine が whisper のときは None）
        self.dicts = dicts            # 辞書の入れ物（.speech を使う）
        self.vad_threshold = vad_threshold
        self.last_ja = ""   # 直前に認識した日本語（会話ログ用）

    def _transcribe(self, audio, task, vad, prompt=None):
        kw = dict(language="ja", task=task, beam_size=5, condition_on_previous_text=False)
        if prompt:
            kw["initial_prompt"] = prompt
        if vad:
            kw["vad_filter"] = True
            kw["vad_parameters"] = dict(threshold=self.vad_threshold,
                                        min_silence_duration_ms=500, speech_pad_ms=400)
        segments, _ = self.model.transcribe(audio, **kw)
        return " ".join(s.text.strip() for s in segments).strip()

    def _recognize(self, audio, task, prompt=None):
        text = self._transcribe(audio, task, True, prompt)
        if not text:  # 小さい声で声判定に弾かれた場合は、判定なしでもう一度
            text = self._transcribe(audio, task, False, prompt)
        low = text.lower().strip(" .!。")
        if not text or any(h in low for h in HALLUCINATIONS):
            return ""
        return text

    def to_english(self, audio):
        self.last_ja = ""
        if self.engine == "whisper":
            return self._recognize(audio, "translate")
        speech = self.dicts.speech
        ja = self._recognize(audio, "transcribe", speech.prompt())
        if not ja:
            return ""
        self.last_ja = ja
        prepared = speech.apply(ja)
        print(f"  [認識] {ja}" + (f"  → {prepared}" if prepared != ja else ""))
        try:
            return self.translator.translate(prepared, "en", "ja")
        except Exception:
            # 翻訳サービスが使えないときは、ネット不要の Whisper で直接英訳する
            print("  （翻訳サービスが使えないため、Whisper で直接英訳します）")
            return self._recognize(audio, "translate")
