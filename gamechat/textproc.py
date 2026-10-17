# -*- coding: utf-8 -*-
"""文字の処理：チャット行の解析・重複チェック・辞書（スラング／音声用語）"""
import csv
import difflib
import re
import unicodedata
from collections import deque

KANA_RE = re.compile(r"[぀-ヿ]")                            # ひらがな・カタカナ（日本語）
CJK_RE = re.compile(r"[㐀-䶿一-鿿豈-﫿]")  # 漢字（中国語の判定用）
NAME_RE = re.compile(r"^(.{1,40}?)\s*[:：]\s*(.+)$")
TAG_RE = re.compile(r"^\s*([\[【(（][^\]】)）]{1,10}[\]】)）])\s*")  # [ALL] [全員] 【分隊】 など


def split_tag(text):
    """先頭の [ALL] [全員] などのチャンネル表示を分ける → (表示 or None, 残り)"""
    m = TAG_RE.match(text)
    if m:
        return m.group(1), text[m.end():].strip()
    return None, text


class LineFilter:
    """ゲームの画面に出る決まった文字（操作の説明など）を取り除く・無視する

    strip_patterns  … 行の中から取り除く部分（正規表現）
    ignore_patterns … これを含む行は丸ごと無視（正規表現）
    """

    def __init__(self, strip_patterns=(), ignore_patterns=()):
        self.strip = [re.compile(p, re.I) for p in strip_patterns if p]
        self.ignore = [re.compile(p, re.I) for p in ignore_patterns if p]

    def clean(self, line):
        for pat in self.ignore:
            if pat.search(line):
                return None
        for pat in self.strip:
            line = pat.sub(" ", line)
        line = " ".join(line.split())
        return line or None


# ---------- チャット行 ----------
def parse_line(line):
    """'名前: 本文' を (名前, 本文) に分ける。名前がなければ (None, 行全体)"""
    line = " ".join(line.split())
    m = NAME_RE.match(line)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return None, line


def worth_translating(text):
    """英語（英字2文字以上）か中国語（漢字2文字以上）の行だけ翻訳する。日本語の行は翻訳しない
    （漢字1文字だけの行は、読み取りの誤り（ゴミ）であることが多いので翻訳しない。スラング辞書の1文字の語は別扱い）"""
    if KANA_RE.search(text):
        return False
    if len(CJK_RE.findall(text)) >= 2:
        return True
    return len(re.findall(r"[A-Za-z]", text)) >= 2


def norm_key(text):
    """比較用に、英数字と漢字だけを小文字で残す（記号・空白・OCRの揺れを無視）"""
    return re.sub(r"[\W_]+", "", text.lower())


def similar(a, b, threshold=0.85):
    a, b = norm_key(a), norm_key(b)
    if not a or not b:
        return False
    if a == b:
        return True
    sm = difflib.SequenceMatcher(None, a, b)
    return sm.quick_ratio() >= threshold and sm.ratio() >= threshold


class SeenLines:
    """一度翻訳した行を覚えておき、スクロールやOCRの揺れで重複しないようにする"""

    def __init__(self, size=80):
        self._lines = deque(maxlen=size)

    def is_new(self, line):
        for old in self._lines:
            if similar(line, old):
                return False
        self._lines.append(line)
        return True


def clean_ascii(s, max_chars=120):
    """キー入力で送れる文字（英数字・記号）だけにする。全角の英数字・記号は半角にする"""
    s = unicodedata.normalize("NFKC", s)  # Ｂ → B、！ → ! など
    for a, b in {"‘": "'", "’": "'", "“": '"', "”": '"',
                 "–": "-", "—": "-", "…": "...", " ": " "}.items():
        s = s.replace(a, b)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = " ".join(s.split())
    if len(s) > max_chars:
        s = s[:max_chars].rsplit(" ", 1)[0]
    return s.strip()


# ---------- 無視リスト ----------
def read_ignore(paths):
    """1行に1つ、無視したい文字列（その文字列を含む行は翻訳しない）。# で始まる行はコメント"""
    out = []
    for path in paths:
        with open(path, encoding="utf-8-sig") as f:
            for ln in f:
                ln = ln.strip()
                if ln and not ln.startswith("#"):
                    out.append(ln)
    return out


# ---------- 辞書ファイル ----------
def read_csv_rows(paths):
    """CSV（UTF-8、1行目は見出し、# で始まる行はコメント）を読み込む"""
    rows = []
    for path in paths:
        with open(path, encoding="utf-8-sig", newline="") as f:
            lines = [ln for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
        for row in csv.DictReader(lines):
            rows.append({(k or "").strip(): (v or "").strip() for k, v in row.items()})
    return rows


def _term_pattern(term):
    """英数字の単語は単語単位で、漢字などは文字列そのままで探す"""
    if re.fullmatch(r"[A-Za-z0-9 '\-]+", term):
        return re.compile(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])", re.I)
    return re.compile(re.escape(term))


class SlangDict:
    """相手のチャット用。列: term（略語・スラング）, expand（翻訳前に置き換える正式な言い方）, ja（その語だけの発言なら直接表示する訳）"""

    def __init__(self, rows=()):
        self.whole = {}
        self.expands = {}
        for r in rows:
            term = r.get("term", "")
            if not term:
                continue
            key = norm_key(term)
            if r.get("ja"):
                self.whole[key] = r["ja"]
            if r.get("expand"):
                self.expands[term.lower()] = (term, r["expand"])
        # 長い語から順に置き換える（"gg wp" を "gg" より先に）
        self._patterns = [(_term_pattern(t), e) for t, e in
                          sorted(self.expands.values(), key=lambda x: -len(x[0]))]

    @classmethod
    def load(cls, paths):
        return cls(read_csv_rows(paths))

    def __len__(self):
        return len(set(self.whole) | {norm_key(t) for t, _ in self.expands.values()})

    def lookup_whole(self, msg):
        """発言がスラング1語だけなら、その訳を返す"""
        return self.whole.get(norm_key(msg))

    def expand(self, msg):
        for pat, rep in self._patterns:
            msg = pat.sub(rep, msg)
        return msg


class SpeechDict:
    """自分の発言用。列: ja（日本語の言い方）, en（英語での言い方）"""

    def __init__(self, rows=()):
        pairs = {}
        for r in rows:
            ja, en = r.get("ja", ""), r.get("en", "")
            if ja and en:
                pairs[ja] = en
        self.pairs = sorted(pairs.items(), key=lambda x: -len(x[0]))

    @classmethod
    def load(cls, paths):
        return cls(read_csv_rows(paths))

    def __len__(self):
        return len(self.pairs)

    def prompt(self, limit=60):
        """音声認識に「この単語が出てくるかも」と教えるための文"""
        terms = [ja for ja, _ in self.pairs[:limit]]
        return "ゲーム中のボイスチャットです。" + ("用語: " + "、".join(terms) + "。" if terms else "")

    def apply(self, ja_text):
        """日本語の文中のゲーム用語を、先に英語へ置き換える（翻訳エンジンに正しい用語を使わせる）"""
        for ja, en in self.pairs:
            ja_text = ja_text.replace(ja, f" {en} ")
        return " ".join(ja_text.split())
