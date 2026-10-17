"""
Speech-to-Text (STT) Abstraction and Adapters for Falcon.
Supports SpeechRecognition, Faster-Whisper, and graceful degradation for missing packages.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger("Falcon.STT")


class BaseSTT(ABC):
    """Abstract interface for speech-to-text engines."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if engine dependencies and models are loaded."""
        pass

    @abstractmethod
    async def listen_and_recognize(self, timeout: float = 5.0, language: str = "en-US") -> Optional[str]:
        """Capture microphone audio and transcribe into text."""
        pass


class SpeechRecognitionSTT(BaseSTT):
    """Adapter using Python speech_recognition package."""

    def __init__(self, device_index: Optional[int] = None):
        self.device_index = device_index
        self._sr = None
        try:
            import speech_recognition as sr  # type: ignore
            self._sr = sr
            self._recognizer = sr.Recognizer()
            self._recognizer.energy_threshold = 300
            self._recognizer.dynamic_energy_threshold = True
        except ImportError:
            self._sr = None

    def is_available(self) -> bool:
        return self._sr is not None

    async def listen_and_recognize(self, timeout: float = 5.0, language: str = "en-US") -> Optional[str]:
        if not self.is_available():
            logger.warning("speech_recognition package is not installed.")
            return None

        sr = self._sr

        def _record_and_transcribe():
            try:
                mic_kwargs = {}
                if self.device_index is not None:
                    mic_kwargs["device_index"] = self.device_index

                with sr.Microphone(**mic_kwargs) as source:
                    self._recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    audio = self._recognizer.listen(source, timeout=timeout, phrase_time_limit=10.0)
                    text = self._recognizer.recognize_google(audio, language=language)
                    return text
            except sr.WaitTimeoutError:
                return None
            except sr.UnknownValueError:
                return None
            except Exception as e:
                logger.error(f"STT recognition error: {e}")
                return None

        return await asyncio.to_thread(_record_and_transcribe)


class VachanaSTT(BaseSTT):
    """Gnani.ai / Vachana Voice AI Speech-to-Text adapter (gnani-prisma-v2.5)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        language_code: str = "hi-IN",
        model: str = "gnani-prisma-v2.5",
        device_index: Optional[int] = None,
        timeout: float = 20.0,
    ):
        self.api_key = api_key
        self.language_code = language_code
        self.model = model
        self.device_index = device_index
        self.timeout = timeout
        self._sr = None
        try:
            import speech_recognition as sr  # type: ignore
            self._sr = sr
            self._recognizer = sr.Recognizer()
        except ImportError:
            self._sr = None

    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def transcribe_wav_bytes(self, wav_bytes: bytes, language: Optional[str] = None) -> Optional[str]:
        """Synchronously send WAV bytes to Vachana STT REST endpoint."""
        import io
        import json
        import urllib.request
        import uuid

        url = "https://api.vachana.ai/stt/v3"
        lang = language or self.language_code
        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
        buffer = io.BytesIO()

        def add_field(name: str, value: str):
            buffer.write(f"--{boundary}\r\n".encode("utf-8"))
            buffer.write(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
            buffer.write(f"{value}\r\n".encode("utf-8"))

        def add_file(name: str, filename: str, data: bytes, content_type: str = "audio/wav"):
            buffer.write(f"--{boundary}\r\n".encode("utf-8"))
            buffer.write(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode("utf-8"))
            buffer.write(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
            buffer.write(data)
            buffer.write(b"\r\n")

        add_field("language_code", lang)
        add_field("preferred_language", lang)
        add_field("format", "transcribe")
        add_field("itn_native_numerals", "true")
        add_file("audio_file", "audio.wav", wav_bytes)
        buffer.write(f"--{boundary}--\r\n".encode("utf-8"))

        payload = buffer.getvalue()
        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "X-API-Key-ID": self.api_key or "",
            "User-Agent": "FalconAssistant/1.0",
        }

        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                transcript = result.get("transcript") or (result.get("output", {}).get("literal"))
                return transcript.strip() if transcript else None
        except Exception as e:
            logger.error(f"Vachana STT transcription error: {e}")
            return None

    def transcribe_file(self, file_path: str, language: Optional[str] = None) -> Optional[str]:
        """Transcribe an audio file using Vachana STT."""
        try:
            with open(file_path, "rb") as f:
                return self.transcribe_wav_bytes(f.read(), language=language)
        except Exception as e:
            logger.error(f"Failed to read audio file '{file_path}': {e}")
            return None

    async def listen_and_recognize(self, timeout: float = 5.0, language: str = "hi-IN") -> Optional[str]:
        """Record audio from microphone and transcribe via Vachana STT."""
        if not self.is_available():
            return None

        if self._sr is None:
            logger.warning("speech_recognition package required for microphone capture.")
            return None

        sr = self._sr

        def _capture_and_send():
            try:
                mic_kwargs = {}
                if self.device_index is not None:
                    mic_kwargs["device_index"] = self.device_index

                with sr.Microphone(**mic_kwargs) as source:
                    self._recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    audio = self._recognizer.listen(source, timeout=timeout, phrase_time_limit=15.0)
                    wav_data = audio.get_wav_data()
                    return self.transcribe_wav_bytes(wav_data, language=language)
            except sr.WaitTimeoutError:
                return None
            except Exception as e:
                logger.error(f"Vachana microphone listen error: {e}")
                return None

        return await asyncio.to_thread(_capture_and_send)


class DisabledSTT(BaseSTT):
    """Null STT implementation when voice input is disabled."""

    def is_available(self) -> bool:
        return True

    async def listen_and_recognize(self, timeout: float = 5.0, language: str = "en-US") -> Optional[str]:
        return None
