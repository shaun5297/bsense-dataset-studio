"""Sound cues for protocol execution.

Cues are short synthesized tones cached as WAV files and played with
whatever the platform offers (winsound on Windows, afplay on macOS, aplay
on Linux). Playback never raises: any failure falls back to the Tk bell so
a missing audio device cannot break an ongoing acquisition.
"""

from __future__ import annotations

import io
import math
import struct
import subprocess
import sys
import tempfile
import wave
from collections.abc import Callable, Sequence
from pathlib import Path

# Cue name -> tone segments of (frequency_hz, duration_s); frequency 0 is silence.
_CUES: dict[str, tuple[tuple[float, float], ...]] = {
    "start": ((880.0, 0.15),),
    "complete": ((660.0, 0.12), (880.0, 0.12), (1320.0, 0.20)),
    "experiment_end": ((660.0, 0.12), (880.0, 0.12), (1320.0, 0.20)),
    "close_eyes": ((520.0, 0.25),),
    "open_eyes": ((780.0, 0.25),),
    "ending_soon": ((440.0, 0.12), (0.0, 0.08), (440.0, 0.12)),
}
_DEFAULT_CUE: tuple[tuple[float, float], ...] = ((700.0, 0.12),)
_SAMPLE_RATE = 44_100


def render_cue(name: str) -> tuple[tuple[float, float], ...]:
    """Return the tone segments for a cue, falling back to a generic beep."""
    return _CUES.get(name, _DEFAULT_CUE)


def synthesize_wav(
    segments: Sequence[tuple[float, float]],
    *,
    sample_rate: int = _SAMPLE_RATE,
) -> bytes:
    """Synthesize 16-bit mono PCM WAV bytes for the given tone segments."""
    frames = bytearray()
    for frequency, duration in segments:
        count = max(0, int(sample_rate * duration))
        fade = min(int(sample_rate * 0.005), count // 2)
        for index in range(count):
            value = 0.0
            if frequency > 0:
                envelope = 1.0
                if fade:
                    if index < fade:
                        envelope = index / fade
                    elif index >= count - fade:
                        envelope = (count - index) / fade
                value = 0.5 * envelope * math.sin(2.0 * math.pi * frequency * index / sample_rate)
            frames += struct.pack("<h", int(value * 32767))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(bytes(frames))
    return buffer.getvalue()


def cue_wav_path(name: str, cache_dir: Path | None = None) -> Path:
    """Write (once) and return the cached WAV file for a cue."""
    directory = cache_dir or (Path(tempfile.gettempdir()) / "bsense-cues")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.wav"
    if not path.exists():
        path.write_bytes(synthesize_wav(render_cue(name)))
    return path


def play_cue(
    name: str | None,
    *,
    bell: Callable[[], None] | None = None,
    player: Callable[[Path], None] | None = None,
) -> None:
    """Play a cue by name; silently no-op for empty names.

    On any playback failure the optional ``bell`` callable (typically the Tk
    ``Widget.bell`` method) is used as a last-resort audible signal.
    """
    if not name:
        return
    try:
        path = cue_wav_path(name)
        (player or _play_file)(path)
    except Exception:
        if bell is not None:
            try:
                bell()
            except Exception:
                pass


def _play_file(path: Path) -> None:
    if sys.platform == "win32":
        import winsound

        winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
    elif sys.platform == "darwin":
        subprocess.Popen(
            ["afplay", str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        subprocess.Popen(
            ["aplay", "-q", str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
