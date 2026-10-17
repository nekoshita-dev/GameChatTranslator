# -*- coding: utf-8 -*-
"""画面の文字の読み取り（RapidOCR：英語・中国語に対応）"""


class ChatOCR:
    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR
        import cv2
        self._cv2 = cv2
        self._engine = RapidOCR()

    def read_lines(self, img_bgr, min_score=0.6):
        """画像（BGR）からテキストを読み取り、画面上の1行ごとの文字列リストを返す"""
        if img_bgr.shape[0] < 600:  # 小さい文字は拡大した方が読み取りやすい
            img_bgr = self._cv2.resize(img_bgr, None, fx=2, fy=2,
                                       interpolation=self._cv2.INTER_CUBIC)
        try:
            out = self._engine(img_bgr)
        except Exception:
            return []  # 文字が何もない画面などで失敗しても無視する
        result = out[0] if isinstance(out, tuple) else out
        try:
            return group_lines(result, min_score)
        except Exception:
            return []


def group_lines(result, min_score=0.6):
    """OCRの結果（枠・文字・信頼度）を、同じ高さのものごとに1行へまとめる"""
    if not result:
        return []
    items = []
    for box, text, score in result:
        text = (text or "").strip()
        if not text or float(score) < min_score:
            continue
        ys = [p[1] for p in box]
        xs = [p[0] for p in box]
        items.append((min(ys), max(ys), min(xs), text))
    items.sort(key=lambda t: (t[0] + t[1]) / 2)

    lines = []  # [上端, 下端, [(x, 文字)]]
    for top, bot, x, text in items:
        cy = (top + bot) / 2
        for ln in lines:
            if abs(cy - (ln[0] + ln[1]) / 2) < max(bot - top, ln[1] - ln[0]) * 0.5:
                ln[2].append((x, text))
                ln[0], ln[1] = min(ln[0], top), max(ln[1], bot)
                break
        else:
            lines.append([top, bot, [(x, text)]])
    lines.sort(key=lambda l: l[0])
    return [" ".join(t for _, t in sorted(l[2])) for l in lines]
