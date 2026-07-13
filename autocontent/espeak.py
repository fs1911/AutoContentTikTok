"""Offline-Sprachsynthese über die gebündelte espeak-ng-Bibliothek (via ctypes).

Kein externer Host, kein API-Key: `espeakng-loader` liefert die kompilierte
`libespeak-ng.so` samt Sprachdaten als PyPI-Wheel. Wir treiben die C-API direkt an
und schreiben echtes PCM-WAV. Robuste, verständliche Stimme in vielen Sprachen (inkl. de).
"""
from __future__ import annotations

import ctypes
import os
import struct
import wave
from pathlib import Path
from typing import Optional

_AUDIO_OUTPUT_RETRIEVAL = 1
_espeakCHARS_UTF8 = 1
_POS_CHARACTER = 1
_espeakRATE = 1
_espeakPITCH = 3


def available() -> bool:
    try:
        import espeakng_loader  # noqa: F401
        return True
    except Exception:
        return False


_lib = None
_rate = 0
_data_parent = ""


def _ensure_lib() -> tuple:
    global _lib, _rate, _data_parent
    if _lib is not None:
        return _lib, _rate
    import espeakng_loader
    _data_parent = os.path.dirname(espeakng_loader.get_data_path())
    lib = ctypes.CDLL(espeakng_loader.get_library_path())
    lib.espeak_Initialize.restype = ctypes.c_int
    rate = lib.espeak_Initialize(_AUDIO_OUTPUT_RETRIEVAL, 0, _data_parent.encode(), 0)
    if rate <= 0:
        raise RuntimeError(f"espeak_Initialize fehlgeschlagen ({rate})")
    _lib, _rate = lib, rate
    return lib, rate


def synth_to_wav(text: str, out_path: Path, voice: str = "de",
                 speed: int = 165, pitch: int = 50) -> float:
    """Synthetisiert `text` als mono-16bit-WAV. Gibt die Dauer in Sekunden zurück."""
    lib, rate = _ensure_lib()
    buf: list[int] = []

    CB = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short),
                          ctypes.c_int, ctypes.c_void_p)

    def _cb(wav, numsamples, events):  # pragma: no cover - C-Callback
        if wav and numsamples > 0:
            buf.extend(wav[i] for i in range(numsamples))
        return 0

    c_cb = CB(_cb)
    lib.espeak_SetSynthCallback(c_cb)
    lib.espeak_SetVoiceByName(voice.encode())
    lib.espeak_SetParameter(_espeakRATE, int(speed), 0)
    lib.espeak_SetParameter(_espeakPITCH, int(pitch), 0)

    data = (text or " ").encode("utf-8")
    lib.espeak_Synth(data, len(data) + 1, 0, _POS_CHARACTER, 0,
                     _espeakCHARS_UTF8, None, None)
    lib.espeak_Synchronize()

    with wave.open(str(out_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<%dh" % len(buf), *buf))
    return round(len(buf) / rate, 3)
