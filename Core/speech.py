from __future__ import annotations

import asyncio
from email.mime import text
import logging
import shutil
import subprocess
import wave
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from openwakeword.model import Model as OpenWakeWordModel

log = logging.getLogger(__name__)
WakeCallback = Callable[[str, float], Awaitable[None]]


@dataclass
class WakeWordService:
    """Continuous OpenWakeWord microphone listener."""

    wake_words: list[str]
    models_dir: Path
    sample_rate: int = 16_000
    frame_size: int = 1_280
    threshold: float = 0.55

    def __post_init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._model: Any | None = None

    async def start(self, on_wake: WakeCallback) -> None:
        """Start the background wake-word listener and return immediately."""
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._model = await asyncio.to_thread(self._load_model)
        self._task = asyncio.create_task(self._listen(on_wake), name="jarvis-wakeword")
        log.info("Wake word listener started", extra={"wake_words": self.wake_words})

    async def stop(self) -> None:
        """Stop the listener."""
        self._stop_event.set()
        if self._task:
            await asyncio.gather(self._task, return_exceptions=True)

    def _load_model(self) -> OpenWakeWordModel:
        self.models_dir.mkdir(parents=True, exist_ok=True)
        custom_models = [str(path) for path in self.models_dir.glob("*.onnx")]
        if custom_models:
            return OpenWakeWordModel(wakeword_models=custom_models, inference_framework="onnx")
        return OpenWakeWordModel(wakeword_models=["hey_jarvis"], inference_framework="onnx")

    async def _listen(self, on_wake: WakeCallback) -> None:
        queue: asyncio.Queue[np.ndarray] = asyncio.Queue(maxsize=8)
        loop = asyncio.get_running_loop()

        def enqueue_audio(audio: np.ndarray) -> None:
            if queue.full():
                log.debug("Dropping wake audio frame because queue is full")
                return
            queue.put_nowait(audio)

        def callback(indata: np.ndarray, frames: int, time_info: object, status: sd.CallbackFlags) -> None:
            if status:
                log.debug("Wake microphone status: %s", status)
            audio = np.frombuffer(indata, dtype=np.int16).copy()
            loop.call_soon_threadsafe(enqueue_audio, audio)

        with sd.RawInputStream(samplerate=self.sample_rate, blocksize=self.frame_size, dtype="int16", channels=1, callback=callback):
            while not self._stop_event.is_set():
                frame = await queue.get()
                prediction = await asyncio.to_thread(self._model.predict, frame)  # type: ignore[union-attr]
                wake_name, score = self._best_prediction(prediction)
                if score >= self.threshold:
                    log.info("Wake word detected", extra={"wake_word": wake_name, "score": score})
                    await on_wake(wake_name, score)
                    await asyncio.sleep(1.0)

    def _best_prediction(self, prediction: dict[str, float]) -> tuple[str, float]:
        wanted = {word.lower().replace(" ", "_") for word in self.wake_words}
        candidates = prediction.items()
        filtered = [(name, score) for name, score in candidates if not wanted or name.lower() in wanted or name.lower().replace("_", " ") in self.wake_words]
        if not filtered:
            filtered = list(prediction.items())
        if not filtered:
            return "unknown", 0.0
        name, score = max(filtered, key=lambda item: item[1])
        return name, float(score)


@dataclass
class WhisperSpeechRecognizer:
    """Faster-Whisper recognizer with CUDA preference and CPU fallback."""

    model_name: str
    models_dir: Path
    device: str = "auto"
    compute_type: str = "auto"
    sample_rate: int = 16_000
    command_seconds: float = 5.0

    def __post_init__(self) -> None:
        self._model: WhisperModel | None = None

    async def transcribe_once(self) -> str:
        """Record a short command from the default microphone and transcribe it."""
        model = await self._get_model()
        audio = await asyncio.to_thread(self._record_audio)
        segments, _info = await asyncio.to_thread(model.transcribe, audio, language="en", vad_filter=True, beam_size=5)
        text = " ".join(segment.text.strip() for segment in segments).strip()
        import logging
        logging.getLogger(__name__).info("TRANSCRIPT: %r", text)
        log.info("Transcribed command", extra={"text": text})
        return text

    async def _get_model(self) -> WhisperModel:
        if self._model is not None:
            return self._model
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self._model = await asyncio.to_thread(self._load_model)
        return self._model

    def _load_model(self) -> WhisperModel:
        device = self._select_device()
        compute_type = self._select_compute_type(device)
        log.info("Loading Faster-Whisper", extra={"model": self.model_name, "device": device, "compute_type": compute_type})
        try:
            return WhisperModel(self.model_name, device=device, compute_type=compute_type, download_root=str(self.models_dir))
        except Exception:
            if device == "cuda":
                log.exception("CUDA Whisper load failed; falling back to CPU")
                return WhisperModel(self.model_name, device="cpu", compute_type="int8", download_root=str(self.models_dir))
            raise

    def _select_device(self) -> str:
        if self.device in {"cuda", "cpu"}:
            return self.device
        try:
            import ctranslate2

            return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        except Exception:
            return "cpu"

    def _select_compute_type(self, device: str) -> str:
        if self.compute_type != "auto":
            return self.compute_type
        return "float16" if device == "cuda" else "int8"

    def _record_audio(self) -> np.ndarray:
        frames = int(self.sample_rate * self.command_seconds)
        recording = sd.rec(frames, samplerate=self.sample_rate, channels=1, dtype="float32")
        sd.wait()
        return np.squeeze(recording)


@dataclass
class PiperVoiceService:
    """Piper text-to-speech service that synthesizes and plays WAV audio."""

    executable: Path
    voice: Path
    temp_dir: Path

    async def speak(self, text: str) -> None:
        if not text.strip():
            return
        wav_path = self.temp_dir / "jarvis_response.wav"
        await asyncio.to_thread(self._synthesize, text, wav_path)
        await asyncio.to_thread(self._play_wav, wav_path)

    def _synthesize(self, text: str, wav_path: Path) -> None:
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        executable = self._resolve_executable()
        if not self.voice.exists():
            raise FileNotFoundError(f"Piper voice model not found: {self.voice}")
        command = [str(executable), "--model", str(self.voice), "--output_file", str(wav_path)]
        log.info("Synthesizing speech with Piper", extra={"voice": str(self.voice)})
        subprocess.run(command, input=text, text=True, check=True, capture_output=True)

    def _resolve_executable(self) -> Path:
        if self.executable.exists():
            return self.executable
        found = shutil.which("piper")
        if found:
            return Path(found)
        raise FileNotFoundError(f"Piper executable not found: {self.executable}")

    def _play_wav(self, wav_path: Path) -> None:
        with wave.open(str(wav_path), "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_rate = wav_file.getframerate()
            frames = wav_file.readframes(wav_file.getnframes())
            dtype = np.int16 if wav_file.getsampwidth() == 2 else np.uint8
        audio = np.frombuffer(frames, dtype=dtype)
        if channels > 1:
            audio = audio.reshape(-1, channels)
        sd.play(audio, sample_rate)
        sd.wait()
