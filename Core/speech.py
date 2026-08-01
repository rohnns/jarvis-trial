from __future__ import annotations

import asyncio
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
    """Continuous OpenWakeWord microphone listener.

    The listener can be suspended (e.g. while STT/execution/TTS are running)
    so that it stops competing with other audio I/O for the microphone and
    doesn't re-trigger on the assistant's own speech. Suspension actually
    closes the input stream rather than merely ignoring predictions, so the
    audio device is fully released during the suspended window.
    """

    wake_words: list[str]
    models_dir: Path
    sample_rate: int = 16_000
    frame_size: int = 1_280
    threshold: float = 0.55
    resume_cooldown_seconds: float = 2.0

    def __post_init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._paused = asyncio.Event()
        self._model: Any | None = None

    async def start(self, on_wake: WakeCallback) -> None:
        """Start the background wake-word listener and return immediately."""
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._paused.clear()
        self._model = await asyncio.to_thread(self._load_model)
        self._task = asyncio.create_task(self._run(on_wake), name="jarvis-wakeword")
        log.info("Wake word listener started", extra={"wake_words": self.wake_words})

    async def stop(self) -> None:
        """Stop the listener."""
        self._stop_event.set()
        if self._task:
            await asyncio.gather(self._task, return_exceptions=True)

    def suspend(self) -> None:
        """Immediately stop capturing microphone audio for wake-word detection.

        Call this as soon as a wake word fires, and before starting STT,
        command execution, or TTS playback.
        """
        if not self._paused.is_set():
            self._paused.set()
            log.info("Wake word detection suspended")

    async def resume_after_cooldown(self, cooldown_seconds: float | None = None) -> None:
        """Resume wake-word detection after STT/execution/TTS finish plus a cooldown.

        The cooldown prevents the tail end of the assistant's own TTS audio
        (or its acoustic echo) from immediately re-triggering the wake word.
        """
        delay = self.resume_cooldown_seconds if cooldown_seconds is None else cooldown_seconds
        await asyncio.sleep(delay)
        self._paused.clear()
        log.info("Wake word detection resumed", extra={"cooldown_seconds": delay})

    def _load_model(self) -> OpenWakeWordModel:
        self.models_dir.mkdir(parents=True, exist_ok=True)
        custom_models = [str(path) for path in self.models_dir.glob("*.onnx")]
        if custom_models:
            return OpenWakeWordModel(wakeword_models=custom_models, inference_framework="onnx")
        return OpenWakeWordModel(wakeword_models=["hey_jarvis"], inference_framework="onnx")

    async def _run(self, on_wake: WakeCallback) -> None:
        """Outer loop: open a listening session whenever not paused/stopped."""
        while not self._stop_event.is_set():
            if self._paused.is_set():
                await asyncio.sleep(0.05)
                continue
            await self._listen_session(on_wake)

    async def _listen_session(self, on_wake: WakeCallback) -> None:
        """Open the microphone and listen until paused, stopped, or a wake fires."""
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
            while not self._stop_event.is_set() and not self._paused.is_set():
                try:
                    frame = await asyncio.wait_for(queue.get(), timeout=0.2)
                except asyncio.TimeoutError:
                    continue
                prediction = await asyncio.to_thread(self._model.predict, frame)  # type: ignore[union-attr]
                wake_name, score = self._best_prediction(prediction)
                if score >= self.threshold:
                    log.info("Wake word detected", extra={"wake_word": wake_name, "score": score})
                    # Suspend immediately (before invoking the callback) so the
                    # mic is freed for the entire STT/execution/TTS cycle, not
                    # just after the callback returns.
                    self.suspend()
                    await on_wake(wake_name, score)
                    return

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
        log.info("Recording command audio", extra={"command_seconds": self.command_seconds})
        model = await self._get_model()
        audio = await asyncio.to_thread(self._record_audio)
        segments, _info = await asyncio.to_thread(model.transcribe, audio, language="en", vad_filter=True, beam_size=5)
        text = " ".join(segment.text.strip() for segment in segments).strip()
        log.info("Transcription complete", extra={"transcript": text})
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
        clean_text = text.strip()
        if not clean_text:
            return
        wav_path = self.temp_dir / "jarvis_response.wav"
        log.info("TTS started", extra={"text": clean_text})
        await asyncio.to_thread(self._synthesize, clean_text, wav_path)
        await asyncio.to_thread(self._play_wav, wav_path)
        log.info("TTS finished", extra={"text": clean_text})

    def _synthesize(self, text: str, wav_path: Path) -> None:
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        executable = self._resolve_executable()
        if not self.voice.exists():
            raise FileNotFoundError(f"Piper voice model not found: {self.voice}")
        # Piper writes WAV audio to --output_file and reads the input text from stdin.
        command = [str(executable), "--model", str(self.voice), "--output_file", str(wav_path)]
        log.info("Synthesizing speech with Piper", extra={"voice": str(self.voice), "text": text})
        result = subprocess.run(command, input=text, text=True, capture_output=True)
        if result.returncode != 0:
            log.error(
                "Piper synthesis failed",
                extra={"returncode": result.returncode, "stderr": result.stderr.strip()},
            )
            raise RuntimeError(f"Piper exited with code {result.returncode}: {result.stderr.strip()}")
        if not wav_path.exists() or wav_path.stat().st_size == 0:
            raise RuntimeError(f"Piper did not produce audio output at {wav_path}")
        log.info("Speech synthesized", extra={"wav_path": str(wav_path), "size_bytes": wav_path.stat().st_size})

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
            sample_width = wav_file.getsampwidth()
            frame_count = wav_file.getnframes()
            frames = wav_file.readframes(frame_count)

        if frame_count == 0 or not frames:
            log.warning("Piper produced an empty WAV file; nothing to play", extra={"wav_path": str(wav_path)})
            return

        dtype = {1: np.uint8, 2: np.int16, 4: np.int32}.get(sample_width, np.int16)
        audio = np.frombuffer(frames, dtype=dtype)
        if channels > 1:
            audio = audio.reshape(-1, channels)

        # Reset any stale PortAudio state (e.g. left over from the wake-word
        # input stream) and explicitly pick the default output device so
        # playback isn't silently routed to a stale/disconnected device.
        sd.stop()
        log.info(
            "Playing synthesized speech",
            extra={
                "wav_path": str(wav_path),
                "sample_rate": sample_rate,
                "channels": channels,
                "duration_seconds": round(frame_count / float(sample_rate), 2),
            },
        )
        try:
            sd.play(audio, samplerate=sample_rate, blocking=True)
        finally:
            sd.stop()
