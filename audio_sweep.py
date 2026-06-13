#!/usr/bin/env python3
"""
芯伴X1 变声器 — espeak-ng 合成 + scipy 变声 + USB 声卡
预设: child cartoon deep robot whisper warm
用法: python3 audio_sweep.py [预设名]
"""

import subprocess, struct, wave, os, tempfile, sys
import numpy as np
from scipy import signal
from scipy.fft import rfft, irfft
from scipy.interpolate import interp1d

TEXT = "今天天气不错"
DEVICE = "hw:0,0"
SR = 22050


# ─── STFT / ISTFT ─────────────────────────────────────────

def _stft(x, n_fft=1024, hop=256):
    w = np.hanning(n_fft)
    n_frames = (len(x) - n_fft) // hop + 1
    X = np.zeros((n_frames, n_fft // 2 + 1), dtype=complex)
    for i in range(n_frames):
        X[i] = rfft(x[i * hop : i * hop + n_fft] * w)
    return X


def _istft(X, n_fft=1024, hop=256):
    w = np.hanning(n_fft)
    n_frames = X.shape[0]
    out_len = (n_frames - 1) * hop + n_fft
    out = np.zeros(out_len)
    ws = np.zeros(out_len)
    for i in range(n_frames):
        chunk = irfft(X[i])
        idx = slice(i * hop, i * hop + n_fft)
        out[idx] += chunk * w
        ws[idx] += w ** 2
    ws[ws < 1e-6] = 1.0
    return out / ws


# ─── 效果器 ───────────────────────────────────────────────

def pitch_shift(x, semitones, n_fft=1024, hop=256):
    """移调不变速 (phase vocoder)"""
    X = _stft(x, n_fft, hop)
    n_frames, n_bins = X.shape
    factor = 2 ** (semitones / 12)
    new_hop = max(1, int(hop / factor))
    out_frames = max(1, int(n_frames * factor))

    mag = np.abs(X)
    phase = np.angle(X)
    dphi = np.diff(phase, axis=0, prepend=phase[:1])
    dphi -= 2 * np.pi * np.round(dphi / (2 * np.pi))

    out_X = np.zeros((out_frames, n_bins), dtype=complex)
    out_phase = np.zeros(n_bins)

    for i in range(out_frames):
        src = i / factor
        lo, hi = min(int(src), n_frames - 1), min(int(src) + 1, n_frames - 1)
        t = max(0, min(1, src - int(src)))
        interp_mag = mag[lo] * (1 - t) + mag[hi] * t
        out_phase += dphi[lo] * factor
        out_X[i] = interp_mag * np.exp(1j * out_phase)

    return _istft(out_X, n_fft, new_hop)


def formant_shift(x, factor, n_fft=1024, hop=256):
    """共振峰偏移 — 改变音色 (男↔女)"""
    X = _stft(x, n_fft, hop)
    n_bins = X.shape[1]
    mag, phase = np.abs(X), np.angle(X)

    old = np.arange(n_bins)
    new = np.clip(np.arange(n_bins) * factor, 0, n_bins - 1)

    out_mag = np.zeros_like(mag)
    for i in range(X.shape[0]):
        out_mag[i] = interp1d(old, mag[i], kind='cubic',
                              bounds_error=False, fill_value=0)(new)

    return _istft(out_mag * np.exp(1j * phase), n_fft, hop)


def reverb(x, mix=0.25, decay=0.35):
    """Schroeder 混响"""
    comb_delays = [29, 37, 41, 43]
    out = np.zeros_like(x)
    for d_ms in comb_delays:
        d = max(1, int(SR * d_ms / 1000))
        buf = np.zeros(len(x) + d)
        gain = decay ** (d_ms / 50)
        for i in range(len(x)):
            buf[i + d] = x[i] + gain * buf[i]
        out += buf[d:] * 0.25

    for d_ms in [5, 13]:
        d = max(1, int(SR * d_ms / 1000))
        y = out.copy()
        for i in range(d, len(y)):
            y[i] = -0.7 * out[i] + out[i - d] + 0.7 * y[i - d]
        out = y

    return x * (1 - mix) + out * mix


def robotize(x, bits=8):
    """量化 → 机器人声"""
    mx = max(abs(x))
    return np.round(x / (2 * mx / (2 ** bits))) * (2 * mx / (2 ** bits)) * 1.3


# ─── 预设 ─────────────────────────────────────────────────

def apply_effects(x, preset):
    x = np.array(x, dtype=float) / 32768.0

    if preset == "child":
        print("   👶 儿童声")
        x = pitch_shift(x, +4)
        x = formant_shift(x, 1.30)
        x = reverb(x, 0.20, 0.30)

    elif preset == "cartoon":
        print("   🐱 卡通声")
        x = pitch_shift(x, +7)
        x = formant_shift(x, 1.50)
        x = reverb(x, 0.29, 0.40)

    elif preset == "deep":
        print("   🎙️  深沉声")
        x = pitch_shift(x, -5)
        x = formant_shift(x, 0.70)
        x = reverb(x, 0.22, 0.50)

    elif preset == "robot":
        print("   🤖 机器人")
        x = pitch_shift(x, +2)
        x = robotize(x)
        b, a = signal.butter(4, 3000 / (SR / 2), 'low')
        x = signal.filtfilt(b, a, x)

    elif preset == "whisper":
        print("   🌬️  耳语")
        env = np.abs(signal.hilbert(x))
        env = env / (env.max() + 1e-6)
        x = env * np.random.normal(0, 0.3, len(x)) * 1.5

    elif preset == "warm":
        print("   ☕ 温暖人声")
        b, a = signal.butter(2, 300 / (SR / 2), 'low')
        x = x + signal.filtfilt(b, a, x) * 0.4
        x = reverb(x, 0.18, 0.35)

    else:
        print(f"   → 直通 ({preset})")
        x = reverb(x, 0.15, 0.25)

    return np.clip(x, -0.98, 0.98)


# ─── 主流程 ───────────────────────────────────────────────

def main():
    preset = sys.argv[1] if len(sys.argv) > 1 else "child"

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        raw = f.name

    try:
        subprocess.run([
            "espeak-ng", "-v", "cmn", "-s", "135", "-p", "50",
            "-a", "75", "-w", raw, TEXT,
        ], check=True, stderr=subprocess.DEVNULL)

        with wave.open(raw, "r") as w:
            nf = w.getnframes()
            nc = w.getnchannels()
            pcm = w.readframes(nf)

        samples = np.frombuffer(pcm, dtype=np.int16).astype(float)
        if nc == 2:
            samples = samples.reshape(-1, 2).mean(axis=1)

        print(f'\n🎙️  "{TEXT}" ({nf / SR:.1f}s)  → 预设: {preset}')
        processed = apply_effects(samples, preset)

        out_i16 = np.clip(processed * 32767, -32767, 32767).astype(np.int16)
        stereo = np.column_stack([out_i16, out_i16]).ravel().tobytes()

        print(f"🔊 → {DEVICE}\n")
        proc = subprocess.Popen(
            ["aplay", "-q", "-D", DEVICE, "-f", "S16_LE", "-r", str(SR), "-c", "2"],
            stdin=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        _, stderr = proc.communicate(stereo)
        print("✅ 完成" if proc.returncode == 0 else f"❌ {stderr.decode().strip()}")

    finally:
        os.unlink(raw)


if __name__ == "__main__":
    print("🎤 芯伴X1 变声器")
    print("   用法: python3 audio_sweep.py [child|cartoon|deep|robot|whisper|warm]\n")
    main()
