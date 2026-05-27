"""CLI for the Live Interpreter using the local microphone and speakers.

Reads PCM16 24kHz mono from the default mic, pushes it into the interpreter,
and plays synthesised audio back through the default output device.

Usage:
    python main.py --lang-a en-US --lang-b es-ES
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import logging
import os
import queue
import signal
from typing import Optional

import pyaudio
from azure.identity.aio import DefaultAzureCredential
from dotenv import load_dotenv

from interpreter import LiveInterpreter

load_dotenv("./.env", override=True)

logging.basicConfig(
    format="%(asctime)s:%(name)s:%(levelname)s:%(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

SAMPLE_RATE = LiveInterpreter.SAMPLE_RATE  # 24kHz PCM16 mono
CHUNK = 1200  # ~50ms


class LocalAudio:
    """Mic capture + speaker playback for a single interpreter session."""

    def __init__(self, interpreter: LiveInterpreter) -> None:
        self.interpreter = interpreter
        self.pa = pyaudio.PyAudio()
        self.input_stream: Optional[pyaudio.Stream] = None
        self.output_stream: Optional[pyaudio.Stream] = None
        self.play_queue: queue.Queue[bytes] = queue.Queue()
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

        def _capture(in_data, _frame_count, _time_info, _status):
            self.interpreter.push_audio(base64.b64encode(in_data).decode("ascii"))
            return (None, pyaudio.paContinue)

        self.input_stream = self.pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK,
            stream_callback=_capture,
        )

        remaining = bytearray()

        def _playback(_in_data, frame_count, _time_info, _status):
            nonlocal remaining
            want = frame_count * 2  # 16-bit mono
            out = bytes(remaining[:want])
            remaining = remaining[want:]
            while len(out) < want:
                try:
                    chunk = self.play_queue.get_nowait()
                except queue.Empty:
                    out += b"\x00" * (want - len(out))
                    break
                out += chunk[: want - len(out)]
                if len(chunk) > want - len(out):
                    remaining.extend(chunk[want - len(out) :])
            return (out, pyaudio.paContinue)

        self.output_stream = self.pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            output=True,
            frames_per_buffer=CHUNK,
            stream_callback=_playback,
        )

    def enqueue_audio(self, audio_b64: str) -> None:
        try:
            self.play_queue.put(base64.b64decode(audio_b64))
        except Exception:
            logger.exception("Failed to decode playback audio")

    def shutdown(self) -> None:
        for s in (self.input_stream, self.output_stream):
            if s is not None:
                try:
                    s.stop_stream()
                    s.close()
                except Exception:
                    pass
        self.pa.terminate()


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Live Interpreter CLI")
    p.add_argument("--lang-a", default=os.environ.get("INTERPRETER_LANG_A", "en-US"))
    p.add_argument("--lang-b", default=os.environ.get("INTERPRETER_LANG_B", "es-ES"))
    p.add_argument(
        "--resource-id",
        default=os.environ.get("AZURE_SPEECH_RESOURCE_ID"),
        help="Speech resource ID (subscription/.../accounts/<name>).",
    )
    p.add_argument(
        "--region",
        default=os.environ.get("AZURE_SPEECH_REGION"),
        help="Speech resource Azure region (e.g. swedencentral).",
    )
    return p.parse_args()


async def _run() -> None:
    args = _parse_args()
    if not args.resource_id or not args.region:
        raise SystemExit(
            "AZURE_SPEECH_RESOURCE_ID and AZURE_SPEECH_REGION must be set "
            "(via .env or CLI args)."
        )

    credential = DefaultAzureCredential()
    audio: Optional[LocalAudio] = None

    interpreter_ref: dict[str, LiveInterpreter] = {}

    async def _on_event(event_type: str, payload: dict) -> None:
        if event_type == "audio" and audio is not None:
            audio.enqueue_audio(payload.get("data", ""))
        elif event_type == "final":
            src = payload.get("source", "")
            tgt = payload.get("translation", "")
            print(f"\n[{payload.get('source_locale')}] {src}")
            print(f"   -> [{payload.get('target_locale')}] {tgt}")
        elif event_type == "status":
            logger.info("status: %s", payload.get("message"))
        elif event_type == "error":
            logger.error("error: %s", payload.get("message"))

    interpreter = LiveInterpreter(
        resource_id=args.resource_id,
        region=args.region,
        credential=credential,
        lang_a=args.lang_a,
        lang_b=args.lang_b,
        event_callback=_on_event,
    )
    interpreter_ref["i"] = interpreter

    audio = LocalAudio(interpreter)

    loop = asyncio.get_running_loop()

    def _request_shutdown(*_args):
        asyncio.run_coroutine_threadsafe(interpreter.stop(), loop)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_shutdown)
        except (NotImplementedError, RuntimeError):
            signal.signal(sig, _request_shutdown)

    print(f"\nLive Interpreter ready: {args.lang_a} <-> {args.lang_b}")
    print("Speak into your default microphone. Press Ctrl+C to exit.\n")

    audio.start(loop)
    try:
        await interpreter.start()
    finally:
        audio.shutdown()
        await credential.close()


if __name__ == "__main__":
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        print("\nGoodbye!")
