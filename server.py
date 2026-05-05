from __future__ import annotations

import asyncio
import os
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from azure.identity.aio import DefaultAzureCredential
from azure.core.credentials_async import AsyncTokenCredential
from dotenv import load_dotenv

from main import BasicVoiceAssistant, load_instructions

# Load environment variables
load_dotenv("./.env", override=True)

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(APP_ROOT, "web")

app = FastAPI()
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

    async def connect(self, websocket: WebSocket) -> None:
        print("Manager.connect() called", flush=True)
        self.websocket = websocket
        await self._send("status", {"message": "Connected"})

    async def disconnect(self) -> None:
        await self.stop()
        self.websocket = None

    async def start(self, initial_text: Optional[str] = None) -> None:
        print("Manager.start() called", flush=True)
        print("Stopping any existing task", flush=True)
        self._initial_text = initial_text
        await self.stop()
        print("Creating assistant task", flush=True)
        self.task = asyncio.create_task(self._run_assistant())
        print("Task created", flush=True)

    async def stop(self) -> None:
        print("Manager.stop() called", flush=True)
        if self.task:
            print("Cancelling task", flush=True)
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                print("Task cancelled successfully", flush=True)
            self.task = None
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
            assistant = BasicVoiceAssistant(
                endpoint=endpoint,
                credential=credential,
                model=os.environ.get("AZURE_VOICELIVE_MODEL", "gpt-realtime"),
                voice=os.environ.get("AZURE_VOICELIVE_VOICE", "en-US-AvaMultilingualNeural"),
                instructions=instructions,
                initial_text=self._initial_text,
                event_callback=self._send,
                audio_callback=self._send,  # Pass the send method for audio events
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
                await manager.start(initial_text=data.get("text"))
            elif event_type == "stop":
                await manager.stop()
            elif event_type == "audio":
                # Handle audio input from web client
                audio_data = data.get("data")
                if not audio_data:
                    print("Audio message has no data", flush=True)
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
