from __future__ import annotations

import asyncio
import logging
import os
import signal
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from azure.identity.aio import DefaultAzureCredential
from azure.core.credentials_async import AsyncTokenCredential
from dotenv import load_dotenv

from main import BasicVoiceAssistant, load_instructions
from simultaneous import SimultaneousInterpreter

# Load environment variables
load_dotenv("./.env", override=True)

logger = logging.getLogger(__name__)

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(APP_ROOT, "web")


def _env_bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).lower() in ("true", "1", "yes", "on")


def _build_session_overrides() -> dict:
    """Read VoiceLive session-config tunables from environment variables.

    Mirrors the Foundry Playground 'Advanced settings' (VAD, audio enhancement).
    """
    # Defaults tuned for translation: avoid splitting a single utterance into
    # two turns when the speaker briefly pauses mid-sentence. If only the second
    # half of a sentence gets translated, increase VOICELIVE_VAD_SILENCE_MS.
    return {
        # Higher default threshold (0.8) reduces pickup of ambient/background
        # speech (e.g. people talking in another room, TVs). Lower if your own
        # speech is being missed.
        "vad_threshold": float(os.environ.get("VOICELIVE_VAD_THRESHOLD", "0.8")),
        "prefix_padding_ms": int(os.environ.get("VOICELIVE_VAD_PREFIX_PADDING_MS", "300")),
        "silence_duration_ms": int(os.environ.get("VOICELIVE_VAD_SILENCE_MS", "1000")),
        "echo_cancellation": _env_bool("VOICELIVE_ECHO_CANCELLATION", True),
        "noise_reduction": _env_bool("VOICELIVE_NOISE_REDUCTION", True),
        "noise_reduction_type": os.environ.get(
            "VOICELIVE_NOISE_REDUCTION_TYPE", "azure_deep_noise_suppression"
        ),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan: install async signal handlers for graceful shutdown.

    On SIGTERM/SIGINT (e.g. Azure Container Apps stopping the container),
    cancel any active assistant task and close its VoiceLive WebSocket.
    On Windows, add_signal_handler isn't supported so we silently skip.
    """
    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def _request_shutdown(sig_name: str) -> None:
        logger.info("Received %s - shutting down assistant", sig_name)
        shutdown_event.set()
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
        await manager.stop()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(os.path.join(WEB_DIR, "index.html"))


class AssistantManager:
    def __init__(self) -> None:
        self.websocket: Optional[WebSocket] = None
        self.task: Optional[asyncio.Task] = None
        self._initial_text: Optional[str] = None
        self.voicelive_connection: Optional[object] = None  # Reference to VoiceLive connection
        self.mode: str = "voicelive"
        self.simultaneous: Optional[SimultaneousInterpreter] = None
        self._si_locales: tuple[str, str] = ("en-US", "es-ES")

    async def connect(self, websocket: WebSocket) -> None:
        print("Manager.connect() called", flush=True)
        self.websocket = websocket
        await self._send("status", {"message": "Connected"})

    async def disconnect(self) -> None:
        await self.stop()
        self.websocket = None

    async def start(
        self,
        initial_text: Optional[str] = None,
        mode: str = "voicelive",
        locale_a: Optional[str] = None,
        locale_b: Optional[str] = None,
    ) -> None:
        print(f"Manager.start() called mode={mode}", flush=True)
        print("Stopping any existing task", flush=True)
        self._initial_text = initial_text
        self.mode = mode if mode in ("voicelive", "simultaneous") else "voicelive"
        if locale_a and locale_b:
            self._si_locales = (locale_a, locale_b)
        await self.stop()
        print("Creating assistant task", flush=True)
        if self.mode == "simultaneous":
            self.task = asyncio.create_task(self._run_simultaneous())
        else:
            self.task = asyncio.create_task(self._run_assistant())
        print("Task created", flush=True)

    async def stop(self) -> None:
        print("Manager.stop() called", flush=True)
        if self.simultaneous is not None:
            try:
                await self.simultaneous.stop()
            except Exception as exc:
                print(f"Error stopping simultaneous: {exc}", flush=True)
            self.simultaneous = None
        if self.task:
            print("Cancelling task", flush=True)
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                print("Task cancelled successfully", flush=True)
            self.task = None
        self.voicelive_connection = None
        await self._send("status", {"message": "Idle"})

    async def _run_assistant(self) -> None:
        try:
            print("_run_assistant started", flush=True)
            endpoint = os.environ.get("AZURE_VOICELIVE_ENDPOINT")
            print(f"Endpoint: {endpoint}", flush=True)
            if not endpoint:
                print("Endpoint is empty!", flush=True)
                await self._send("error", {"message": "AZURE_VOICELIVE_ENDPOINT not set in .env"})
                return

            print("Creating credential", flush=True)
            # DefaultAzureCredential supports multiple auth methods:
            # - Managed Identity (for Azure Container Apps)
            # - Azure CLI (for local development)
            credential: AsyncTokenCredential = DefaultAzureCredential()

            instructions = load_instructions()

            print("Creating assistant", flush=True)
            session_overrides = _build_session_overrides()
            print(f"Session overrides: {session_overrides}", flush=True)

            assistant = BasicVoiceAssistant(
                endpoint=endpoint,
                credential=credential,
                model=os.environ.get("AZURE_VOICELIVE_MODEL", "gpt-realtime"),
                voice=os.environ.get("AZURE_VOICELIVE_VOICE", "en-US-Ava:DragonHDLatestNeural"),
                instructions=instructions,
                initial_text=self._initial_text,
                event_callback=self._send,
                audio_callback=self._send,  # Pass the send method for audio events
                session_overrides=session_overrides,
            )

            print("Starting assistant", flush=True)
            await assistant.start()
            print("Assistant finished", flush=True)
        except asyncio.CancelledError:
            print("Task cancelled", flush=True)
        except Exception as e:
            print(f"Error in _run_assistant: {e}", flush=True)
            import traceback
            traceback.print_exc()
            await self._send("error", {"message": str(e)})

    async def _run_simultaneous(self) -> None:
        try:
            print("_run_simultaneous started", flush=True)
            speech_region = os.environ.get("AZURE_SPEECH_REGION")
            if not speech_region:
                await self._send(
                    "error",
                    {
                        "message": "AZURE_SPEECH_REGION must be set in .env for simultaneous mode."
                    },
                )
                return

            locale_a, locale_b = self._si_locales
            interpreter = SimultaneousInterpreter(
                speech_region=speech_region,
                locale_a=locale_a,
                locale_b=locale_b,
                event_callback=self._send,
                audio_callback=self._send,
            )
            self.simultaneous = interpreter
            await interpreter.start()
            print("Simultaneous interpreter finished", flush=True)
        except asyncio.CancelledError:
            print("Simultaneous task cancelled", flush=True)
        except Exception as e:
            print(f"Error in _run_simultaneous: {e}", flush=True)
            import traceback
            traceback.print_exc()
            await self._send("error", {"message": str(e)})
        finally:
            self.simultaneous = None

    async def _send(self, event_type: str, payload: dict) -> None:
        if not self.websocket:
            return
        
        # Handle connection_ready event specially
        if event_type == "connection_ready":
            # Store the connection but don't send it to client
            connection = payload.get("connection")
            if connection:
                self.voicelive_connection = connection
            return
        
        message = {"type": event_type, **payload}
        try:
            await self.websocket.send_json(message)
        except Exception:
            pass

    def set_voicelive_connection(self, connection: object) -> None:
        """Store the VoiceLive connection so we can send audio to it."""
        self.voicelive_connection = connection


manager = AssistantManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    await manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_json()
            event_type = data.get("type")
            print(f"WebSocket received: {event_type}", flush=True)
            if event_type == "start":
                await manager.start(
                    initial_text=data.get("text"),
                    mode=data.get("mode", "voicelive"),
                    locale_a=data.get("locale_a"),
                    locale_b=data.get("locale_b"),
                )
            elif event_type == "stop":
                await manager.stop()
            elif event_type == "audio":
                # Handle audio input from web client
                audio_data = data.get("data")
                if not audio_data:
                    print("Audio message has no data", flush=True)
                    continue

                # Route to whichever pipeline is active.
                if manager.mode == "simultaneous":
                    if manager.simultaneous is None:
                        # Not yet started - drop silently.
                        continue
                    try:
                        import base64 as _b64
                        manager.simultaneous.push_audio(_b64.b64decode(audio_data))
                    except Exception as e:
                        print(f"Error pushing audio to interpreter: {e}", flush=True)
                    continue

                if not manager.voicelive_connection:
                    print("No VoiceLive connection available", flush=True)
                    continue

                try:
                    await manager.voicelive_connection.input_audio_buffer.append(audio=audio_data)
                    # Log every 50th audio chunk to avoid spam
                    if not hasattr(manager, '_audio_count'):
                        manager._audio_count = 0
                    manager._audio_count += 1
                    if manager._audio_count % 50 == 0:
                        print(f"Sent {manager._audio_count} audio chunks to VoiceLive", flush=True)
                except Exception as e:
                    print(f"Error appending audio: {e}", flush=True)
                    import traceback
                    traceback.print_exc()
    except WebSocketDisconnect:
        await manager.disconnect()
    except Exception as e:
        print(f"WebSocket error: {e}", flush=True)
        await manager.disconnect()
