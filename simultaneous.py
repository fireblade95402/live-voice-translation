"""Simultaneous interpretation pipeline using Azure Speech SDK.

Architecture (true overlap-with-speaker streaming):

    web mic (PCM16 24kHz)
        |
        v
    PushAudioInputStream  --->  TranslationRecognizer
                                    |  recognizing  -> si_partial event
                                    |               (live captions while
                                    |                speaker is still talking)
                                    |  recognized   -> si_final event +
                                    v                  SpeechSynthesizer ->
                                                       PCM16 24kHz audio
                                                       chunks streamed back
                                                       to web client.

Auto-detects the spoken language between two configured locales so a
two-person bilingual conversation works without re-arming after every turn.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
from typing import Awaitable, Callable, Optional

import azure.cognitiveservices.speech as speechsdk
from azure.identity import DefaultAzureCredential
from azure.cognitiveservices.speech.audio import (
    AudioStreamFormat,
    PushAudioInputStream,
    AudioConfig,
)
from azure.cognitiveservices.speech.translation import (
    SpeechTranslationConfig,
    TranslationRecognizer,
)

logger = logging.getLogger(__name__)

EmitCallback = Callable[[str, dict], Awaitable[None]]

# Default voices per BCP-47 locale used when synthesising translated audio.
# Override individually with AZURE_SPEECH_VOICE_<LOCALE_UPPER> env vars
# (e.g. AZURE_SPEECH_VOICE_FR_FR=fr-FR-DeniseNeural).
_DEFAULT_VOICES = {
    "en-US": "en-US-AvaMultilingualNeural",
    "en-GB": "en-GB-SoniaNeural",
    "es-ES": "es-ES-ElviraNeural",
    "es-MX": "es-MX-DaliaNeural",
    "fr-FR": "fr-FR-DeniseNeural",
    "de-DE": "de-DE-KatjaNeural",
    "it-IT": "it-IT-ElsaNeural",
    "pt-PT": "pt-PT-RaquelNeural",
    "pt-BR": "pt-BR-FranciscaNeural",
    "nl-NL": "nl-NL-FennaNeural",
    "ja-JP": "ja-JP-NanamiNeural",
    "zh-CN": "zh-CN-XiaoxiaoNeural",
    "ko-KR": "ko-KR-SunHiNeural",
    "ar-EG": "ar-EG-SalmaNeural",
    "hi-IN": "hi-IN-SwaraNeural",
    "ru-RU": "ru-RU-SvetlanaNeural",
}


def _get_speech_auth_token() -> str:
    """Return an AAD authorization token for keyless Azure Speech authentication.

    The token is formatted as required by the Speech SDK:
    ``aad#<resource_id>#<aad_access_token>``
    where *resource_id* is the full ARM resource ID of the Speech / AI Services
    resource (e.g. /subscriptions/.../providers/Microsoft.CognitiveServices/accounts/...).
    Set ``AZURE_SPEECH_RESOURCE_ID`` in your environment.
    """
    resource_id = os.environ.get("AZURE_SPEECH_RESOURCE_ID", "")
    if not resource_id:
        raise ValueError(
            "AZURE_SPEECH_RESOURCE_ID must be set for keyless Speech authentication. "
            "It is the full ARM resource ID of your Azure Speech / AI Services resource."
        )
    credential = DefaultAzureCredential()
    token = credential.get_token("https://cognitiveservices.azure.com/.default")
    return f"aad#{resource_id}#{token.token}"


def _voice_for(locale: str) -> str:
    env_key = "AZURE_SPEECH_VOICE_" + locale.upper().replace("-", "_")
    return (
        os.environ.get(env_key)
        or _DEFAULT_VOICES.get(locale)
        or os.environ.get("AZURE_SPEECH_DEFAULT_VOICE", "en-US-AvaMultilingualNeural")
    )


def _iso639(locale: str) -> str:
    """fr-FR -> fr (TranslationRecognizer's target language wants ISO-639-1)."""
    return locale.split("-")[0].lower()


class SimultaneousInterpreter:
    """Streaming bidirectional interpreter between two locales.

    The recognizer emits partial results (`recognizing`) every few hundred
    ms while the speaker is still talking, which we surface as live captions.
    On a finalised utterance (`recognized`), we synthesise translated audio
    and stream it back chunk-by-chunk so playback can begin before the full
    sentence is rendered.
    """

    # PCM format used both for incoming mic audio (from the browser) and for
    # outgoing TTS audio (consumed by the existing browser playAudio path).
    SAMPLE_RATE = 24000

    def __init__(
        self,
        speech_region: str,
        locale_a: str,
        locale_b: str,
        event_callback: EmitCallback,
        audio_callback: EmitCallback,
    ) -> None:
        self._speech_region = speech_region
        self._locale_a = locale_a
        self._locale_b = locale_b
        self._event_callback = event_callback
        self._audio_callback = audio_callback

        self._loop = asyncio.get_event_loop()
        self._push_stream: Optional[PushAudioInputStream] = None
        self._recognizer: Optional[TranslationRecognizer] = None
        self._stop_event = asyncio.Event()
        self._tts_lock = asyncio.Lock()

    # ---- public API -------------------------------------------------------

    async def start(self) -> None:
        """Start the recognizer; returns once it is listening."""
        await self._emit("status", {"message": "Starting simultaneous interpreter..."})

        translation_config = SpeechTranslationConfig(
            subscription="placeholder", region=self._speech_region
        )
        translation_config.authorization_token = _get_speech_auth_token()
        # Both locales are added as targets in ISO-639-1 form. When we get a
        # recognition we look up which language was detected and pick the
        # OTHER one as the translation to surface.
        translation_config.add_target_language(_iso639(self._locale_a))
        translation_config.add_target_language(_iso639(self._locale_b))
        # Continuous recognition with auto language id between the two
        # configured locales.
        auto_detect = speechsdk.languageconfig.AutoDetectSourceLanguageConfig(
            languages=[self._locale_a, self._locale_b]
        )

        stream_format = AudioStreamFormat(
            samples_per_second=self.SAMPLE_RATE, bits_per_sample=16, channels=1
        )
        self._push_stream = PushAudioInputStream(stream_format)
        audio_config = AudioConfig(stream=self._push_stream)

        self._recognizer = TranslationRecognizer(
            translation_config=translation_config,
            auto_detect_source_language_config=auto_detect,
            audio_config=audio_config,
        )

        self._recognizer.recognizing.connect(self._on_recognizing)
        self._recognizer.recognized.connect(self._on_recognized)
        self._recognizer.canceled.connect(self._on_canceled)
        self._recognizer.session_stopped.connect(lambda evt: self._stop_event.set())

        self._recognizer.start_continuous_recognition()
        await self._emit(
            "status",
            {"message": f"Ready ({self._locale_a} <-> {self._locale_b})"},
        )
        await self._emit(
            "si_languages",
            {"locale_a": self._locale_a, "locale_b": self._locale_b},
        )

        # Block until something stops us.
        await self._stop_event.wait()

    async def stop(self) -> None:
        if self._recognizer is not None:
            try:
                self._recognizer.stop_continuous_recognition()
            except Exception as exc:  # pragma: no cover - best effort cleanup
                logger.warning("Error stopping recognizer: %s", exc)
        if self._push_stream is not None:
            try:
                self._push_stream.close()
            except Exception:
                pass
        self._stop_event.set()

    def push_audio(self, pcm16_bytes: bytes) -> None:
        """Feed mic audio (PCM16 mono @ 24kHz) into the recognizer."""
        if self._push_stream is not None and pcm16_bytes:
            self._push_stream.write(pcm16_bytes)

    # ---- recognizer event handlers (run on SDK thread) --------------------

    def _on_recognizing(self, evt) -> None:
        result = evt.result
        if result.reason != speechsdk.ResultReason.TranslatingSpeech:
            return
        source_text = result.text or ""
        detected = self._detected_locale(result) or self._locale_a
        target_locale = self._other_locale(detected)
        translated = result.translations.get(_iso639(target_locale), "")
        self._schedule(
            self._emit(
                "si_partial",
                {
                    "source_text": source_text,
                    "translated_text": translated,
                    "source_locale": detected,
                    "target_locale": target_locale,
                },
            )
        )

    def _on_recognized(self, evt) -> None:
        result = evt.result
        if result.reason != speechsdk.ResultReason.TranslatedSpeech:
            return
        source_text = (result.text or "").strip()
        if not source_text:
            return
        detected = self._detected_locale(result) or self._locale_a
        target_locale = self._other_locale(detected)
        translated = (result.translations.get(_iso639(target_locale), "") or "").strip()

        self._schedule(
            self._emit(
                "si_final",
                {
                    "source_text": source_text,
                    "translated_text": translated,
                    "source_locale": detected,
                    "target_locale": target_locale,
                },
            )
        )
        if translated:
            self._schedule(self._synthesize(translated, target_locale))

    def _on_canceled(self, evt) -> None:
        logger.error("Recognition canceled: %s", evt)
        self._schedule(
            self._emit("error", {"message": f"Recognition canceled: {evt.reason}"})
        )
        self._stop_event.set()

    # ---- helpers ----------------------------------------------------------

    def _detected_locale(self, result) -> Optional[str]:
        """Return the configured locale (e.g. fr-FR) that best matches the SDK's
        auto-detect result.

        The SDK may return a full BCP-47 tag (``fr-FR``), a bare ISO-639-1 code
        (``fr``), or an empty string.  We resolve whichever form is returned back
        to one of our two configured locales by comparing language-code prefixes
        so that ``fr``, ``fr-FR``, and ``fr-CA`` all map correctly to the
        configured locale that starts with ``fr``.
        """
        try:
            raw = (
                result.properties.get(
                    speechsdk.PropertyId.SpeechServiceConnection_AutoDetectSourceLanguageResult
                )
                or ""
            ).strip()
            if not raw:
                return None
            raw_lang = raw.split("-")[0].lower()
            for locale in (self._locale_a, self._locale_b):
                if locale.split("-")[0].lower() == raw_lang:
                    return locale
            return None
        except Exception:
            return None

    def _other_locale(self, locale: str) -> str:
        """Return the locale to translate *into* given the detected source locale."""
        lang = locale.split("-")[0].lower()
        if lang == self._locale_a.split("-")[0].lower():
            return self._locale_b
        if lang == self._locale_b.split("-")[0].lower():
            return self._locale_a
        # Unrecognised — default to locale_b so we at least translate *somewhere*.
        logger.warning("Unrecognised detected locale %r; defaulting to %s", locale, self._locale_b)
        return self._locale_b

    def _schedule(self, coro) -> None:
        """Schedule a coroutine from the SDK callback thread onto our loop."""
        try:
            asyncio.run_coroutine_threadsafe(coro, self._loop)
        except Exception as exc:
            logger.warning("Failed to schedule coroutine: %s", exc)

    async def _emit(self, event_type: str, payload: dict) -> None:
        try:
            await self._event_callback(event_type, payload)
        except Exception as exc:
            logger.warning("Emit callback failed for %s: %s", event_type, exc)

    async def _synthesize(self, text: str, target_locale: str) -> None:
        """Synthesize translated text and stream PCM audio chunks to client.

        Serialised so two overlapping final translations don't talk over
        each other in the playback queue.
        """
        async with self._tts_lock:
            voice = _voice_for(target_locale)
            speech_config = speechsdk.SpeechConfig(
                subscription="placeholder", region=self._speech_region
            )
            speech_config.authorization_token = _get_speech_auth_token()
            speech_config.speech_synthesis_voice_name = voice
            speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Raw24Khz16BitMonoPcm
            )
            # No audio device, no file - we'll pull bytes from result.audio_data.
            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=speech_config, audio_config=None
            )
            try:
                future = synthesizer.speak_text_async(text)
                # The SDK call is blocking under the hood; run in executor so
                # the asyncio loop stays responsive.
                result = await asyncio.get_event_loop().run_in_executor(
                    None, future.get
                )
            except Exception as exc:
                logger.error("TTS synthesis failed: %s", exc)
                return

            if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
                logger.error(
                    "TTS did not complete: reason=%s details=%s",
                    result.reason,
                    getattr(result, "error_details", ""),
                )
                return

            audio_bytes = result.audio_data or b""
            if not audio_bytes:
                return

            # Stream to the browser in ~50ms chunks (24000 samples/s * 2 bytes
            # * 0.05s = 2400 bytes) so playback can begin almost immediately.
            chunk_size = 2400
            for offset in range(0, len(audio_bytes), chunk_size):
                chunk = audio_bytes[offset : offset + chunk_size]
                b64 = base64.b64encode(chunk).decode("ascii")
                await self._audio_callback("audio", {"data": b64})
                # Tiny yield so we don't flood the websocket in one tick.
                await asyncio.sleep(0)
