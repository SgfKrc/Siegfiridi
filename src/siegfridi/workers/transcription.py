"""Cancellable multiprocessing boundary for audio transcription."""

from __future__ import annotations

import multiprocessing as mp
import queue
import time
from dataclasses import dataclass
from typing import Any, Self

from ..audio.decoder import AudioCache
from ..transcription.basic_pitch import transcribe_file


@dataclass(frozen=True, slots=True)
class TranscriptionRequest:
    audio_path: str
    model_path: str | None = None
    cache_dir: str | None = None
    target_rate: int = 22050


def run_transcription_job(request: TranscriptionRequest, messages: Any | None = None) -> dict[str, Any]:
    """Run one job and optionally emit JSON-like progress messages to a queue."""
    def emit(payload: dict[str, Any]) -> None:
        if messages is not None:
            messages.put(payload)

    emit({"type": "started", "audio_path": request.audio_path})
    try:
        cache = AudioCache(request.cache_dir) if request.cache_dir else None
        result = transcribe_file(
            request.audio_path,
            model_path=request.model_path,
            cache=cache,
            target_rate=request.target_rate,
        )
    except Exception as exc:  # noqa: BLE001 - worker boundary must return failures to the UI
        payload = {"type": "failed", "error": str(exc), "error_type": type(exc).__name__}
        emit(payload)
        return payload
    payload = {"type": "completed", "result": result}
    emit(payload)
    return payload


class TranscriptionProcess:
    """Spawn-on-Windows worker with non-blocking queue polling."""

    def __init__(self, request: TranscriptionRequest) -> None:
        self.request = request
        self._context = mp.get_context("spawn")
        self._messages = self._context.Queue()
        self._process: mp.Process | None = None

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.is_alive()

    def start(self) -> None:
        if self.is_running:
            raise RuntimeError("transcription process is already running")
        self._process = self._context.Process(
            target=run_transcription_job,
            args=(self.request, self._messages),
            name="siegfridi-transcription",
        )
        self._process.start()

    def poll(self, timeout: float = 0.0) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        while True:
            try:
                if timeout:
                    messages.append(self._messages.get(timeout=timeout))
                    timeout = 0.0
                else:
                    messages.append(self._messages.get_nowait())
            except queue.Empty:
                return messages

    def wait(self, timeout: float | None = None) -> list[dict[str, Any]]:
        """Wait for worker completion, then drain late queue messages."""
        process = self._process
        if process is not None:
            process.join(timeout)
        # Queue feeder threads can publish just after process exit on Windows.
        deadline = time.monotonic() + 1.0
        messages = self.poll(timeout=0.1)
        while time.monotonic() < deadline:
            more = self.poll()
            if more:
                messages.extend(more)
                continue
            if process is None or not process.is_alive():
                time.sleep(0.01)
            else:
                break
        return messages

    def cancel(self) -> None:
        process = self._process
        if process is None:
            return
        if process.is_alive():
            process.terminate()
            process.join(timeout=1.0)
        self._process = None

    def close(self) -> None:
        self.cancel()
        self._messages.close()

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
