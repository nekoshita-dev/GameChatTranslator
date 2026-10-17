# -*- coding: utf-8 -*-
"""画面の撮影

フルスクリーンのゲームは、ふつうの方法（mss / GDI）では撮れずに後ろのデスクトップが写ることがあります。
そのため、使えるときは Windows の Desktop Duplication（dxcam。OBS の画面キャプチャと同じ仕組み）で撮り、
使えないときは mss で撮ります。どちらもゲームのプロセスには触れません。

返す画像は numpy の BGR 配列（OCR 用）です。
"""
import numpy as np


class Grabber:
    def __init__(self, method="auto", log=print):
        self.log = log
        self.method = method  # "auto" / "dxcam" / "mss"
        self._mss = None
        self._dx = {}         # 出力番号 → (camera, (left, top, right, bottom))
        self._dx_ok = method in ("auto", "dxcam")
        self._dx_failed_logged = False
        if self._dx_ok:
            try:
                import dxcam  # noqa: F401
            except Exception:
                self._dx_ok = False
                if method == "dxcam":
                    self.log("※ dxcam が入っていません。setup.bat をもう一度実行してください（mss で撮影します）")
        self.last_method = None

    # ---------- dxcam ----------
    def _dx_outputs(self):
        if self._dx:
            return self._dx
        import dxcam
        for idx in range(8):
            try:
                cam = dxcam.create(output_idx=idx, output_color="BGR")
            except Exception:
                break
            if cam is None:
                break
            try:
                rc = cam._output.desc.DesktopCoordinates
                self._dx[idx] = (cam, (rc.left, rc.top, rc.right, rc.bottom))
            except Exception:
                self._dx[idx] = (cam, (0, 0, cam.width, cam.height))
        return self._dx

    def _dx_grab(self, region):
        l, t = region["left"], region["top"]
        r, b = l + region["width"], t + region["height"]
        for cam, (ol, ot, orr, ob) in self._dx_outputs().values():
            if ol <= l < orr and ot <= t < ob:
                box = (l - ol, t - ot, min(r, orr) - ol, min(b, ob) - ot)
                frame = cam.grab(region=box)
                if frame is None:
                    return "same"  # 前回から画面が変わっていない
                return np.ascontiguousarray(frame[:, :, :3])
        raise RuntimeError("範囲がどのモニターにも入っていません")

    # ---------- mss ----------
    def _mss_grab(self, region):
        if self._mss is None:
            import mss
            self._mss = mss.mss()
        shot = self._mss.grab(region)
        return np.ascontiguousarray(np.asarray(shot)[:, :, :3])

    def grab(self, region):
        """BGR 画像。dxcam で「前回と同じ」なら文字列 "same" を返す"""
        if self._dx_ok:
            try:
                out = self._dx_grab(region)
                self.last_method = "dxcam"
                return out
            except Exception as e:
                self._dx_ok = self.method == "dxcam"
                if not self._dx_failed_logged:
                    self._dx_failed_logged = True
                    self.log(f"※ dxcam で撮影できないため mss を使います（{str(e)[:80]}）")
        self.last_method = "mss"
        return self._mss_grab(region)

    def grab_fresh(self, region, tries=10):
        """「前回と同じ」を返さず、必ず画像を返す（範囲選択の画面用）"""
        import time
        for _ in range(tries):
            out = self.grab(region)
            if not isinstance(out, str):
                return out
            time.sleep(0.05)
        return self._mss_grab(region)

    def monitors(self):
        """[{"left","top","width","height"}]（1番目がメイン）"""
        if self._mss is None:
            import mss
            self._mss = mss.mss()
        return self._mss.monitors[1:]

    def close(self):
        for cam, _ in self._dx.values():
            try:
                cam.release()
            except Exception:
                pass
        self._dx.clear()


# ---------- モニターとウィンドウの位置 ----------
def monitor_of(rect, monitors):
    """rect（left, top, right, bottom）の中心があるモニター。見つからなければメイン"""
    if rect:
        cx, cy = (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2
        for m in monitors:
            if m["left"] <= cx < m["left"] + m["width"] and m["top"] <= cy < m["top"] + m["height"]:
                return m
    return monitors[0]


def covers_monitor(rect, mon, margin=8):
    """ウィンドウがモニター全体を覆っているか（フルスクリーン・ボーダーレスフルスクリーン）"""
    if not rect:
        return False
    return (rect[0] <= mon["left"] + margin and rect[1] <= mon["top"] + margin
            and rect[2] >= mon["left"] + mon["width"] - margin
            and rect[3] >= mon["top"] + mon["height"] - margin)
