"""windowing.py — sliding window untuk buffer sensor kontinu."""
from collections import deque


class RollingWindow:
    """Buffer sederhana per device: simpan N pembacaan terakhir (fhr,mhr,uc)."""

    def __init__(self, seq_len: int):
        self.seq_len = seq_len
        self.buf = deque(maxlen=seq_len)

    def push(self, fhr_bpm, mhr_bpm, uc_per_10min):
        self.buf.append((fhr_bpm, mhr_bpm, uc_per_10min))

    def is_ready(self) -> bool:
        return len(self.buf) == self.seq_len

    def as_list(self):
        return list(self.buf)
