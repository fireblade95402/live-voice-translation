"""FastAPI server that exposes the Live Interpreter over a WebSocket.

Protocol (client -> server):
    {"type": "start", "langA": "en-US", "langB": "es-ES"}
    {"type": "stop"}
    {"type": "audio", "data": "<base64 PCM16 24kHz mono>"}

Protocol (server -> client):
    {"type": "status", "message": "..."}
    {"type": "language_pair", "lang1": "...", "lang2": "...",
                              "locale1": "en-US", "locale2": "es-ES"}
    {"type": "partial", "source": "...", "translation": "...",
                        "source_locale": "en-US", "target_locale": "es-ES"}
    {"type": "final",   "source": "...", "translation": "...",
                        "source_locale": "en-US", "target_locale": "es-ES"}
    {"type": "audio",   "data": "<base64 PCM16 24kHz mono>"}
    {"type": "error",   "message": "..."}
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from contextlib import asynccontextmanager
from typing import Optional

from azure.identity.aio import DefaultAzureCredential
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from interpreter import LiveInterpreter

load_dotenv("./.env", override=True)

logging.basicConfig(
    format="%(asctime)s:%(name)s:%(levelname)s:%(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(APP_ROOT, "web")


class InterpreterManager:
    """Owns the active LiveInterpreter for a single WebSocket connection."""

    def __init__(self) -> None:
        self.websocket: Optional[WebSocket] = None
        self.interpreter: Optional[LiveInterpreter] = None
        self.task: Optional[asyncio.Task] = None
        self._credential: Optional[DefaultAzureCredential] = None

    async def connect(self, websocket: WebSocket) -> None:
        self.websocket = websocket
        await self._send("status", {"message": "Connected"})

    async def disconnect(self) -> None:
        await self.stop()
        self.websocket = None
        if self._credential is not None:
            try:
                await self._credential.close()
            except Exception:
                pass
            self._credential = None

    async def start(self, lang_a: str, lang_b: str) -> None:
        await self.stop()

        resource_id = os.environ.get("AZURE_SPEECH_RESOURCE_ID")
        region = os.environ.get("AZURE_SPEECH_REGION")
        if not resource_id or not region:
            await self._send(
                "error",
                {
                    "message": (
                        "AZURE_SPEECH_RESOURCE_ID and AZURE_SPEECH_REGION must "
                        "be set in the environment."
                    )
                },
            )
            return

        if self._credential is None:
            self._credential = DefaultAzureCredential()

        self.interpreter = LiveInterpreter(
            resource_id=resource_id,
            region=region,
            credential=self._credential,
            lang_a=lang_a,
            lang_b=lang_b,
            event_callback=self._send,
        )
        self.task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self.interpreter is not None:
            await self.interpreter.stop()
        if self.task is not None:
            try:
                await asyncio.wait_for(self.task, timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self.task.cancel()
            except Exception:
                logger.exception("Error awaiting interpreter task")
            self.task = None
        self.interpreter = None
        await self._send("status", {"message": "Idle"})

    def push_audio(self, audio_b64: str) -> None:
        if self.interpreter is None:
            return
        self.interpreter.push_audio(audio_b64)

    async def _run(self) -> None:
        assert self.interpreter is not None
        try:
            await self.interpreter.start()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Interpreter failed")
            await self._send("error", {"message": str(exc)})

    async def _send(self, event_type: str, payload: dict) -> None:
        if not self.websocket:
            return
        message = {"type": event_type, **payload}
        try:
            await self.websocket.send_json(message)
        except Exception:
            # Connection likely closed; ignore.
            pass


manager = InterpreterManager()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    loop = asyncio.get_running_loop()

    def _request_shutdown(sig_name: str) -> None:
        logger.info("Received %s - shutting down interpreter", sig_name)
        asyncio.create_task(manager.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_shutdown, sig.name)
        except (NotImplementedError, RuntimeError):
            # Windows / non-main-thread - uvicorn handles signals itself.
            pass

    try:
        yield
    finally:
        await manager.disconnect()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(os.path.join(WEB_DIR, "index.html"))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    await manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_json()
            event_type = data.get("type")

            if event_type == "start":
                lang_a = data.get("langA") or "en-US"
                lang_b = data.get("langB") or "es-ES"
                logger.info("Starting interpreter: %s <-> %s", lang_a, lang_b)
                await manager.start(lang_a, lang_b)
            elif event_type == "stop":
                await manager.stop()
            elif event_type == "audio":
                audio_data = data.get("data")
                if audio_data:
                    manager.push_audio(audio_data)
            else:
                logger.debug("Ignoring unknown event: %s", event_type)
    except WebSocketDisconnect:
        await manager.disconnect()
    except Exception:
        logger.exception("WebSocket error")
        await manager.disconnect()
