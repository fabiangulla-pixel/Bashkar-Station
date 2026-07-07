"""
core/voice_dictation.py — Dictado por voz para el módulo Normalizar.

Flujo:
  1. Captura audio del micrófono en chunks con sounddevice
  2. Convierte a WAV en memoria
  3. Transcribe con SpeechRecognition usando el motor de Windows (offline)
     o Google Web Speech (online, mejor precisión) según disponibilidad

El módulo es completamente independiente de tkinter — la UI llama a
DictadoSession y recibe texto via callback.
"""

from __future__ import annotations

import io
import queue
import threading
import wave
from typing import Callable

SAMPLE_RATE   = 16000   # Hz — óptimo para reconocimiento de voz
CHUNK_SECONDS = 4       # segundos por chunk de reconocimiento
CHANNELS      = 1


def _numpy_a_wav(frames: "np.ndarray", sample_rate: int) -> bytes:
    """Convierte array numpy de audio a bytes WAV en memoria."""
    import numpy as np
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # int16 = 2 bytes
        wf.setframerate(sample_rate)
        pcm = (frames * 32767).astype(np.int16)
        wf.writeframes(pcm.tobytes())
    buf.seek(0)
    return buf.read()


class DictadoSession:
    """
    Sesión de dictado por voz.

    Uso:
        session = DictadoSession(callback=lambda texto: ...)
        session.iniciar()
        # ... usuario dicta ...
        session.detener()
    """

    def __init__(
        self,
        callback: Callable[[str], None],
        idioma: str = "es-CO",
        modo_online: bool = True,
    ):
        self.callback    = callback
        self.idioma      = idioma
        self.modo_online = modo_online

        self._activo     = False
        self._hilo: threading.Thread | None = None
        self._q_audio: queue.Queue = queue.Queue()
        self._q_estado: queue.Queue = queue.Queue()  # mensajes de estado para la UI

    # ── API pública ──────────────────────────────────────────────────────────

    def iniciar(self):
        """Inicia la captura y transcripción en un hilo daemon."""
        if self._activo:
            return
        self._activo = True
        self._hilo = threading.Thread(target=self._bucle, daemon=True)
        self._hilo.start()

    def detener(self):
        """Detiene la captura limpiamente."""
        self._activo = False

    def estado(self) -> str | None:
        """Retorna el próximo mensaje de estado, o None si no hay."""
        try:
            return self._q_estado.get_nowait()
        except queue.Empty:
            return None

    # ── Implementación interna ───────────────────────────────────────────────

    def _bucle(self):
        try:
            import sounddevice as sd
            import numpy as np
            import speech_recognition as sr
        except ImportError as e:
            self._q_estado.put(f"error:Falta dependencia: {e}")
            return

        recognizer = sr.Recognizer()
        recognizer.energy_threshold      = 300
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold        = 0.8

        self._q_estado.put("escuchando")

        chunk_frames = int(SAMPLE_RATE * CHUNK_SECONDS)

        while self._activo:
            try:
                # Grabar un chunk
                audio_np = sd.rec(
                    chunk_frames,
                    samplerate=SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype="float32",
                    blocking=True,
                )
                if not self._activo:
                    break

                # Convertir a WAV y crear AudioData para SpeechRecognition
                wav_bytes = _numpy_a_wav(audio_np[:, 0], SAMPLE_RATE)
                audio_data = sr.AudioData(wav_bytes, SAMPLE_RATE, 2)

                # Transcribir
                texto = self._transcribir(recognizer, audio_data)
                if texto:
                    self.callback(texto)

            except Exception as ex:
                self._q_estado.put(f"error:{ex}")
                break

        self._q_estado.put("detenido")

    def _transcribir(self, recognizer, audio_data) -> str:
        """Intenta transcribir primero online (Google), luego offline (Sphinx)."""
        import speech_recognition as sr

        if self.modo_online:
            try:
                return recognizer.recognize_google(
                    audio_data, language=self.idioma
                )
            except sr.UnknownValueError:
                return ""
            except sr.RequestError:
                # Sin internet — caer a motor offline de Windows
                pass

        # Motor offline: Windows Speech Recognition (requiere Windows 8+)
        try:
            return recognizer.recognize_whisper(
                audio_data, language="spanish"
            )
        except Exception:
            pass

        return ""
