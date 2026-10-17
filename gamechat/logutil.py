# -*- coding: utf-8 -*-
"""コンソールに出した内容を、時刻つきでログファイルにも残す（不具合報告用）"""
import os
import sys
import threading
import time

MAX_BYTES = 1_000_000  # これを超えたら .old に回して新しく始める
_listeners = []        # 1行出るたびに呼ぶ関数（画面の下の帯に出すため）


def add_listener(fn):
    _listeners.append(fn)


class _Tee:
    def __init__(self, stream, logfile, lock):
        self._stream = stream
        self._file = logfile
        self._lock = lock
        self._at_line_start = True
        self._buf = ""

    def isatty(self):
        return False

    def write(self, text):
        try:
            if self._stream is not None:
                self._stream.write(text)
        except Exception:
            pass
        with self._lock:
            try:
                for part in text.splitlines(keepends=True):
                    if self._at_line_start:
                        self._file.write(time.strftime("%Y-%m-%d %H:%M:%S  "))
                    self._file.write(part)
                    self._at_line_start = part.endswith("\n")
                self._file.flush()
            except Exception:
                pass
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                for fn in list(_listeners):
                    try:
                        fn(line)
                    except Exception:
                        pass
        return len(text)

    def flush(self):
        try:
            if self._stream is not None:
                self._stream.flush()
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self._stream, name)


def start_logging(log_dir, name="gamechat.log"):
    """標準出力とエラー出力をログファイルにも書く。ログファイルの場所を返す（失敗したら None）"""
    try:
        os.makedirs(log_dir, exist_ok=True)
        path = os.path.join(log_dir, name)
        if os.path.exists(path) and os.path.getsize(path) > MAX_BYTES:
            os.replace(path, path + ".old")
        f = open(path, "a", encoding="utf-8")
    except OSError:
        return None
    lock = threading.Lock()
    f.write("\n" + "=" * 20 + time.strftime(" %Y-%m-%d %H:%M:%S 起動 ") + "=" * 20 + "\n")
    sys.stdout = _Tee(sys.stdout, f, lock)
    sys.stderr = _Tee(sys.stderr, f, lock)
    return path
