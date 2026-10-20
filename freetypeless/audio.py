"""录音、WAV 编码、长音频切分。"""
from __future__ import annotations

import io
import logging
import threading
import time
import wave

import numpy as np

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000
# MiMo ASR 单次请求 base64 不超过 10MB：16k/16bit/mono ≈ 32KB/s → 150s ≈ 6.4MB base64
MAX_CHUNK_SECONDS = 150


def to_wav_bytes(pcm: np.ndarray, sr: int = SAMPLE_RATE) -> bytes:
    pcm = np.asarray(pcm, dtype=np.int16).reshape(-1)
    bio = io.BytesIO()
    with wave.open(bio, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return bio.getvalue()


def read_wav(path: str) -> np.ndarray:
    """读取 wav 为 16k 单声道 int16（仅用于命令行测试）。"""
    with wave.open(path, "rb") as w:
        sr, ch, sw = w.getframerate(), w.getnchannels(), w.getsampwidth()
        frames = w.readframes(w.getnframes())
    if sw != 2:
        raise ValueError("仅支持 16-bit wav")
    x = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    x = resample(x, sr, SAMPLE_RATE)
    return np.clip(x, -32768, 32767).astype(np.int16)


def resample(x: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out or len(x) == 0:
        return x
    n_out = int(round(len(x) * sr_out / sr_in))
    t_in = np.arange(len(x)) / sr_in
    t_out = np.arange(n_out) / sr_out
    return np.interp(t_out, t_in, x).astype(np.float32)


def rms_dbfs(pcm: np.ndarray) -> float:
    if len(pcm) == 0:
        return -120.0
    x = pcm.astype(np.float32) / 32768.0
    r = float(np.sqrt(np.mean(x * x)) + 1e-12)
    return 20 * np.log10(r)


def split_for_upload(pcm: np.ndarray, sr: int = SAMPLE_RATE, max_sec: float = MAX_CHUNK_SECONDS,
                     search_sec: float = 10.0) -> list[np.ndarray]:
    """把长音频切成不超过 max_sec 的片段，切点选在边界前 search_sec 内能量最低的位置（尽量切在停顿处）。"""
    max_len = int(max_sec * sr)
    if len(pcm) <= max_len:
        return [pcm]
    chunks: list[np.ndarray] = []
    start = 0
    frame = int(0.05 * sr)
    while len(pcm) - start > max_len:
        end = start + max_len
        lo = max(start + frame, end - int(search_sec * sr))
        seg = pcm[lo:end].astype(np.float32)
        n = len(seg) // frame
        if n > 0:
            energy = (seg[: n * frame].reshape(n, frame) ** 2).mean(axis=1)
            cut = lo + int(np.argmin(energy)) * frame + frame // 2
        else:
            cut = end
        chunks.append(pcm[start:cut])
        start = cut
    chunks.append(pcm[start:])
    return [c for c in chunks if len(c) > 0]


def resolve_device(spec):
    """配置里的设备可以是空（系统默认）、序号或名称片段。"""
    if spec in (None, "", "default"):
        return None
    if isinstance(spec, int) or (isinstance(spec, str) and spec.strip().isdigit()):
        return int(spec)
    import sounddevice as sd

    spec_l = str(spec).lower()
    for i, d in enumerate(sd.query_devices()):
        if d.get("max_input_channels", 0) > 0 and spec_l in d["name"].lower():
            return i
    log.warning("未找到麦克风 %r，使用系统默认", spec)
    return None


def list_input_devices() -> list[str]:
    try:
        import sounddevice as sd

        hostapis = sd.query_hostapis()
        names = []
        for d in sd.query_devices():
            if d.get("max_input_channels", 0) > 0:
                api = hostapis[d["hostapi"]]["name"]
                if "MME" in api:  # MME 名称最全且兼容性最好，避免重复
                    names.append(d["name"])
        return sorted(set(names))
    except Exception as e:  # pragma: no cover
        log.warning("枚举麦克风失败: %s", e)
        return []


class Recorder:
    """按需打开麦克风；stop() 返回 16k 单声道 int16。"""

    def __init__(self, on_level=None):
        self.on_level = on_level
        self._stream = None
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._sr = SAMPLE_RATE
        self._t0 = 0.0
        self.recording = False

    def _callback(self, indata, frames, time_info, status):  # PortAudio 线程
        x = indata[:, 0].copy() if indata.ndim > 1 else indata.copy()
        with self._lock:
            self._chunks.append(x)
        if self.on_level:
            try:
                self.on_level(float(np.abs(x).max()) if len(x) else 0.0)
            except Exception:
                pass

    def start(self, device=None) -> None:
        import sounddevice as sd

        if self.recording:
            return
        with self._lock:
            self._chunks = []
        dev = resolve_device(device)
        last_err = None
        rates = [SAMPLE_RATE]
        try:
            default_sr = int(sd.query_devices(dev if dev is not None else sd.default.device[0])["default_samplerate"])
            if default_sr not in rates:
                rates.append(default_sr)
        except Exception:
            rates += [48000, 44100]
        for sr in rates:
            try:
                self._stream = sd.InputStream(samplerate=sr, channels=1, dtype="float32",
                                              device=dev, callback=self._callback, blocksize=0)
                self._stream.start()
                self._sr = sr
                self._t0 = time.monotonic()
                self.recording = True
                return
            except Exception as e:
                last_err = e
                self._stream = None
        raise RuntimeError(f"无法打开麦克风: {last_err}")

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self._t0 if self.recording else 0.0

    def _close(self) -> np.ndarray:
        self.recording = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:  # pragma: no cover
                log.warning("关闭麦克风出错: %s", e)
            self._stream = None
        with self._lock:
            data = np.concatenate(self._chunks) if self._chunks else np.zeros(0, np.float32)
            self._chunks = []
        return data

    def stop(self) -> np.ndarray:
        data = self._close()
        data = resample(data, self._sr, SAMPLE_RATE)
        return np.clip(data * 32767.0, -32768, 32767).astype(np.int16)

    def cancel(self) -> None:
        self._close()
