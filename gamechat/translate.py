# -*- coding: utf-8 -*-
"""翻訳エンジン

  google   … 無料・キー不要（非公式の方法。使いすぎると一時的に断られることがある）
  deepl    … APIキーが必要。自然な訳
  mymemory … 無料・キー不要（1日の上限あり）。予備用

選んだエンジンが失敗したときは、使える別のエンジンで翻訳し直します。
失敗したエンジンはしばらく休ませ（30秒〜5分）、連続で断られないようにします。
"""
import json
import re
import threading
import time
import urllib.parse
import urllib.request

_DEEPL_LANG = {"ja": "JA", "en": "EN-US", "zh": "ZH"}
ENGINES = ("google", "deepl", "mymemory")
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
_CJK_RE = re.compile(r"[㐀-鿿]")
_KANA_RE = re.compile(r"[぀-ヿ]")


class TranslateError(Exception):
    pass


def _get_json(url, timeout=8, data=None, headers=None):
    h = {"User-Agent": _UA}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# ---------- 各エンジン ----------
def google_translate(text, target, source=None):
    """Google翻訳（translate.googleapis.com の公開エンドポイント）"""
    params = urllib.parse.urlencode({
        "client": "gtx", "sl": source or "auto", "tl": "zh-CN" if target == "zh" else target,
        "dt": "t", "q": text,
    })
    data = _get_json("https://translate.googleapis.com/translate_a/single?" + params)
    out = "".join(seg[0] for seg in (data[0] or []) if seg and seg[0])
    lang = data[2] if len(data) > 2 and isinstance(data[2], str) else None
    return out.strip(), lang


def google_web_translate(text, target, source=None):
    """Google翻訳（deep-translator 経由。google_translate が使えないときの予備）"""
    from deep_translator import GoogleTranslator
    return GoogleTranslator(source=source or "auto", target=target).translate(text)


def deepl_translate(api_key, text, target, source=None):
    if not api_key:
        raise TranslateError("DeepLのAPIキーが設定されていません（settings.toml の [api] deepl_key）")
    host = "api-free.deepl.com" if api_key.endswith(":fx") else "api.deepl.com"
    params = {"text": text, "target_lang": _DEEPL_LANG.get(target, target.upper())}
    if source:
        params["source_lang"] = _DEEPL_LANG.get(source, source.upper()).split("-")[0]
    data = _get_json(f"https://{host}/v2/translate", timeout=10,
                     data=urllib.parse.urlencode(params).encode(),
                     headers={"Authorization": f"DeepL-Auth-Key {api_key}"})
    tr = data["translations"][0]
    return tr["text"], (tr.get("detected_source_language") or "").lower() or None


def guess_lang(text):
    if _KANA_RE.search(text):
        return "ja"
    if _CJK_RE.search(text):
        return "zh-CN"
    return "en"


def mymemory_translate(text, target, source=None):
    src = source or guess_lang(text)
    if src == "zh":
        src = "zh-CN"
    tgt = "zh-CN" if target == "zh" else target
    if src.split("-")[0] == tgt.split("-")[0]:
        return text, src.split("-")[0]
    params = urllib.parse.urlencode({"q": text[:480], "langpair": f"{src}|{tgt}"})
    data = _get_json("https://api.mymemory.translated.net/get?" + params)
    status = int(data.get("responseStatus") or 0)
    out = (data.get("responseData") or {}).get("translatedText") or ""
    if status != 200 or not out or "MYMEMORY WARNING" in out.upper():
        raise TranslateError(f"MyMemory: {data.get('responseDetails') or status}")
    return out, src.split("-")[0]


def _google_any(text, target, source=None):
    try:
        return google_translate(text, target, source)
    except Exception as first:
        try:
            return google_web_translate(text, target, source)
        except Exception:
            raise first


# ---------- 窓口 ----------
class Translator:
    """翻訳の窓口。キャッシュ・予備エンジンへの切り替え・失敗したエンジンの休止・警告（1分に1回まで）"""

    WARN_INTERVAL = 60
    COOLDOWN_MIN = 30
    COOLDOWN_MAX = 300

    def __init__(self, engine="google", deepl_key="", label="翻訳", backends=None, log=print,
                 clock=time.time):
        if engine not in ENGINES:
            raise ValueError(f"翻訳エンジン '{engine}' は使えません（{' / '.join(ENGINES)}）")
        self.deepl_key = deepl_key
        self.label = label
        self.log = log
        self.clock = clock
        self._backends = backends or {
            "google": _google_any,
            "deepl": lambda text, target, source=None: deepl_translate(self.deepl_key, text, target, source),
            "mymemory": mymemory_translate,
        }
        if engine == "deepl" and not deepl_key:
            self.log(f"※ {label}: DeepLのAPIキーが無いので、Google翻訳を使います")
            engine = "google"
        self.engine = engine
        self.order = [engine] + [e for e in ENGINES if e != engine and self._usable(e)]
        self.last_engine = None
        self.last_lang = None   # 直前の翻訳で判定された元の言語（"en" "zh-CN" "ja" など。分からなければ None）
        self._cache = {}
        self._lock = threading.Lock()
        self._last_warn = 0.0
        self._failing = False
        self._rest_until = {}   # エンジン → この時刻まで使わない
        self._rest_len = {}     # エンジン → 次に休ませる秒数

    def _usable(self, engine):
        return engine != "deepl" or bool(self.deepl_key)

    def _warn(self, msg):
        now = self.clock()
        if now - self._last_warn >= self.WARN_INTERVAL:
            self._last_warn = now
            self.log(msg)

    def _rest(self, engine):
        length = self._rest_len.get(engine, self.COOLDOWN_MIN)
        self._rest_until[engine] = self.clock() + length
        self._rest_len[engine] = min(length * 2, self.COOLDOWN_MAX)

    def _ok(self, engine):
        self._rest_until.pop(engine, None)
        self._rest_len.pop(engine, None)

    def translate(self, text, target, source=None):
        key = (text, target, source)
        with self._lock:
            if key in self._cache:
                out, self.last_lang = self._cache[key]
                return out
        now = self.clock()
        ready = [e for e in self.order if self._rest_until.get(e, 0) <= now]
        if not ready:  # 全部休み中なら、休みが一番早く明けるものを試す
            ready = [min(self.order, key=lambda e: self._rest_until.get(e, 0))]
        errors = []
        for engine in ready:
            try:
                out = self._backends[engine](text, target, source)
                lang = None
                if isinstance(out, tuple):  # (訳, 判定された元の言語)
                    out, lang = out
            except Exception as e:
                errors.append(f"{engine}: {str(e)[:120]}")
                self._rest(engine)
                continue
            if not out:
                errors.append(f"{engine}: 空の結果")
                self._rest(engine)
                continue
            self._ok(engine)
            self.last_engine = engine
            self.last_lang = lang
            if engine != self.order[0]:
                self._warn(f"※ {self.label}: {self.order[0]} が使えないため {engine} で翻訳しています")
            if self._failing:
                self._failing = False
                self.log(f"※ {self.label}: 翻訳サービスに再びつながりました")
            with self._lock:
                if len(self._cache) > 500:
                    self._cache.clear()
                self._cache[key] = (out, lang)
            return out
        self._failing = True
        self._warn(f"※ {self.label}: 翻訳できませんでした（ネット接続を確認してください）  {' / '.join(errors)}")
        raise TranslateError("; ".join(errors))
