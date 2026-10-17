"""
Text-to-Speech (TTS) Abstraction and Adapters for Falcon.
Supports pyttsx3, native Windows SAPI fallback, rate/volume controls, and speech interruption.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger("Falcon.TTS")


class BaseTTS(ABC):
    """Abstract interface for speech synthesis engines."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if TTS provider is operational."""
        pass

    @abstractmethod
    async def speak(self, text: str) -> None:
        """Speak the given text asynchronously."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Interrupt any currently playing speech."""
        pass


class Pyttsx3TTS(BaseTTS):
    """Offline Windows SAPI5 adapter using pyttsx3."""

    def __init__(self, rate: int = 190, volume: float = 0.95):
        self.rate = rate
        self.volume = volume
        self._engine = None
        self._is_speaking = False
        try:
            import pyttsx3  # type: ignore
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", self.rate)
            self._engine.setProperty("volume", self.volume)
        except Exception as e:
            logger.debug(f"pyttsx3 initialization note: {e}")
            self._engine = None

    def is_available(self) -> bool:
        return self._engine is not None

    async def speak(self, text: str) -> None:
        if not self._engine:
            return

        def _run_speak():
            try:
                self._is_speaking = True
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception as e:
                logger.error(f"pyttsx3 speech error: {e}")
            finally:
                self._is_speaking = False

        await asyncio.to_thread(_run_speak)

    def stop(self) -> None:
        if self._engine and self._is_speaking:
            try:
                self._engine.stop()
            except Exception:
                pass


class WindowsSapiTTS(BaseTTS):
    """Native Windows PowerShell speech synthesizer fallback (zero external packages required)."""

    def __init__(self, rate: int = 0, volume: int = 100):
        self.rate = rate
        self.volume = volume
        self._current_proc: Optional[subprocess.Popen] = None

    def is_available(self) -> bool:
        return os.name == "nt"

    async def speak(self, text: str) -> None:
        if not self.is_available() or not text:
            return

        # Sanitize single quotes for PowerShell string
        safe_text = text.replace("'", "''").replace("\n", " ")

        def _speak():
            ps_cmd = (
                f"Add-Type -AssemblyName System.Speech; "
                f"$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                f"$synth.Rate = {self.rate}; $synth.Volume = {self.volume}; "
                f"$synth.Speak('{safe_text}');"
            )
            try:
                self._current_proc = subprocess.Popen(
                    ["powershell", "-NoProfile", "-Command", ps_cmd],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._current_proc.wait()
            except Exception as e:
                logger.error(f"Windows SAPI TTS error: {e}")
            finally:
                self._current_proc = None

        await asyncio.to_thread(_speak)

    def stop(self) -> None:
        if self._current_proc and self._current_proc.poll() is None:
            try:
                self._current_proc.terminate()
            except Exception:
                pass

class SarvamTTS(BaseTTS):
    """High-fidelity Indian Voice Text-to-Speech adapter using Sarvam AI (Bulbul v3)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        speaker: str = "aditya",
        model: str = "bulbul:v3",
        language_code: str = "hi-IN",
        timeout: float = 15.0,
    ):
        self.api_key = api_key
        self.speaker = speaker
        self.model = model
        self.language_code = language_code
        self.timeout = timeout
        self._is_speaking = False
        self._sapi_fallback = WindowsSapiTTS()

    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    async def speak(self, text: str) -> None:
        if not self.is_available() or not text.strip():
            return

        import base64
        import json
        import tempfile
        import urllib.request
        from pathlib import Path

        clean_text = text.strip()
        # Truncate text if excessively long for a single speech turn
        if len(clean_text) > 500:
            clean_text = clean_text[:500] + "..."

        url = "https://api.sarvam.ai/text-to-speech"
        payload = {
            "inputs": [clean_text],
            "target_language_code": self.language_code,
            "speaker": self.speaker,
            "model": self.model,
        }

        def _fetch_and_play():
            try:
                self._is_speaking = True
                req = urllib.request.Request(
                    url,
                    headers={
                        "api-subscription-key": self.api_key,
                        "Content-Type": "application/json",
                    },
                    data=json.dumps(payload).encode("utf-8"),
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    audios = data.get("audios", [])
                    if not audios:
                        raise ValueError("No audio returned from Sarvam AI.")

                    audio_bytes = base64.b64decode(audios[0])
                    # Write to temporary wav file
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                        tmp_path = tmp.name
                        tmp.write(audio_bytes)

                    # Play on Windows using winsound
                    if os.name == "nt":
                        import winsound  # type: ignore
                        winsound.PlaySound(tmp_path, winsound.SND_FILENAME)
                        # Clean up temp file
                        try:
                            Path(tmp_path).unlink(missing_ok=True)
                        except Exception:
                            pass
            except Exception as e:
                logger.warning(f"Sarvam AI TTS error: {e}. Falling back to Windows SAPI...")
                # Fallback to local Windows SAPI
                try:
                    import subprocess
                    safe_sapi = clean_text.replace("'", "")
                    ps_cmd = (
                        f"Add-Type -AssemblyName System.Speech; "
                        f"$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                        f"$synth.Speak('{safe_sapi}');"
                    )
                    subprocess.call(["powershell", "-NoProfile", "-Command", ps_cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass
            finally:
                self._is_speaking = False

        await asyncio.to_thread(_fetch_and_play)

    def stop(self) -> None:
        if os.name == "nt":
            try:
                import winsound  # type: ignore
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
        self._sapi_fallback.stop()


class VachanaTTS(BaseTTS):
    """Gnani.ai / Vachana Voice AI Text-to-Speech adapter (timbre-v3.0 / timbre-v2.5)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        voice: str = "Devansh",
        model: str = "timbre-v3.0",
        sample_rate: int = 24000,
        timeout: float = 15.0,
    ):
        self.api_key = api_key
        self.voice = voice
        self.model = model
        self.sample_rate = sample_rate
        self.timeout = timeout
        self._is_speaking = False
        self._sapi_fallback = WindowsSapiTTS()

    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    async def speak(self, text: str) -> None:
        if not self.is_available() or not text.strip():
            return

        import json
        import tempfile
        import urllib.request
        from pathlib import Path

        clean_text = text.strip()
        if len(clean_text) > 800:
            clean_text = clean_text[:800] + "..."

        url = "https://api.vachana.ai/api/v1/tts/inference"
        payload = {
            "text": clean_text,
            "voice": self.voice,
            "model": self.model,
            "audio_config": {
                "container": "wav",
                "sample_rate": self.sample_rate,
            },
        }

        def _fetch_and_play():
            self._is_speaking = True
            try:
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=data,
                    headers={
                        "Content-Type": "application/json",
                        "X-API-Key-ID": self.api_key or "",
                        "User-Agent": "FalconAssistant/1.0",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    wav_data = resp.read()

                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp_path = tmp.name
                    tmp.write(wav_data)

                try:
                    if os.name == "nt":
                        import winsound  # type: ignore
                        winsound.PlaySound(tmp_path, winsound.SND_FILENAME)
                finally:
                    try:
                        Path(tmp_path).unlink(missing_ok=True)
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"Vachana AI TTS error: {e}. Falling back to Windows SAPI...")
                try:
                    import subprocess
                    safe_sapi = clean_text.replace("'", "")
                    ps_cmd = (
                        f"Add-Type -AssemblyName System.Speech; "
                        f"$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                        f"$synth.Speak('{safe_sapi}');"
                    )
                    subprocess.call(["powershell", "-NoProfile", "-Command", ps_cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass
            finally:
                self._is_speaking = False

        await asyncio.to_thread(_fetch_and_play)

    def stop(self) -> None:
        if os.name == "nt":
            try:
                import winsound  # type: ignore
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
        self._sapi_fallback.stop()


class DisabledTTS(BaseTTS):
    """Null TTS implementation when audio playback is disabled."""

    def is_available(self) -> bool:
        return True

    async def speak(self, text: str) -> None:
        pass

    def stop(self) -> None:
        pass
