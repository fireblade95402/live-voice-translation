"""Live Interpreter built on the Azure Speech SDK.

Bidirectional, low-latency speech-to-speech translation between two locales.
The user picks a language pair (e.g. en-US <-> es-ES); the recognizer
auto-detects which one is being spoken on each utterance and we synthesise
the translation in the other language's neural voice.

The class is consumed by ``server.py`` and emits high-level events
(``status``, ``partial``, ``final``, ``audio``, ``language_pair``, ``error``)
to the WebSocket client via the provided ``event_callback``.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
from typing import Awaitable, Callable, Optional, Tuple, Union

import azure.cognitiveservices.speech as speechsdk
from azure.core.credentials_async import AsyncTokenCredential

logger = logging.getLogger(__name__)

EventCallback = Callable[[str, dict], Union[None, Awaitable[None]]]


# Default neural voice per target locale. Overridable per-locale via
# AZURE_SPEECH_VOICE_<LOCALE>, e.g. AZURE_SPEECH_VOICE_FR_FR=fr-FR-DeniseNeural.
LANGUAGE_DEFAULT_VOICES = {
    "en-US": "en-US-AvaMultilingualNeural",
    "es-ES": "es-ES-ElviraNeural",
    "fr-FR": "fr-FR-DeniseNeural",
    "de-DE": "de-DE-KatjaNeural",
    "it-IT": "it-IT-ElsaNeural",
    "pt-BR": "pt-BR-FranciscaNeural",
    "pt-PT": "pt-PT-RaquelNeural",
    "ja-JP": "ja-JP-NanamiNeural",
    "ko-KR": "ko-KR-SunHiNeural",
    "zh-CN": "zh-CN-XiaoxiaoNeural",
    "ar-SA": "ar-SA-ZariyahNeural",
    "ru-RU": "ru-RU-SvetlanaNeural",
    "hi-IN": "hi-IN-SwaraNeural",
    "nl-NL": "nl-NL-ColetteNeural",
    "pl-PL": "pl-PL-AgnieszkaNeural",
    "tr-TR": "tr-TR-EmelNeural",
}

LANGUAGE_DISPLAY_NAMES = {
    "en-US": "English",
    "es-ES": "Spanish",
    "fr-FR": "French",
    "de-DE": "German",
    "it-IT": "Italian",
    "pt-BR": "Portuguese",
    "pt-PT": "Portuguese",
    "ja-JP": "Japanese",
    "ko-KR": "Korean",
    "zh-CN": "Chinese",
    "ar-SA": "Arabic",
    "ru-RU": "Russian",
    "hi-IN": "Hindi",
    "nl-NL": "Dutch",
    "pl-PL": "Polish",
    "tr-TR": "Turkish",
}

# Locales whose translator code differs from a simple ISO-639-1 split.
_TRANSLATION_CODE_OVERRIDES = {
    "zh-CN": "zh-Hans",
    "zh-TW": "zh-Hant",
    "pt-BR": "pt",
    "pt-PT": "pt",
}


def translation_code(locale: str) -> str:
    """Map a BCP-47 input locale to the translator language code."""
    return _TRANSLATION_CODE_OVERRIDES.get(locale, locale.split("-")[0])


def language_display(locale: str) -> str:
    return LANGUAGE_DISPLAY_NAMES.get(locale, locale)


def voice_for(locale: str, default: Optional[str] = None) -> str:
    env_key = f"AZURE_SPEECH_VOICE_{locale.upper().replace('-', '_')}"
    return (
        os.environ.get(env_key)
        or LANGUAGE_DEFAULT_VOICES.get(locale)
        or default
        or os.environ.get("AZURE_SPEECH_DEFAULT_VOICE", "en-US-AvaMultilingualNeural")
    )


class LiveInterpreter:
    """Bidirectional speech-to-speech interpreter over a push audio stream."""

    SAMPLE_RATE = 24000  # PCM16 mono, matches what the browser already sends/plays.

    def __init__(
        self,
        resource_id: str,
        region: str,
        credential: AsyncTokenCredential,
        lang_a: str,
        lang_b: str,
        event_callback: EventCallback,
    ) -> None:
        self.resource_id = resource_id
        self.region = region
        self.credential = credential
        self.lang_a = lang_a
        self.lang_b = lang_b
        self.code_a = translation_code(lang_a)
        self.code_b = translation_code(lang_b)
        self._emit_cb = event_callback

        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.push_stream: Optional[speechsdk.audio.PushAudioInputStream] = None
        self.recognizer: Optional[speechsdk.translation.TranslationRecognizer] = None
        self.synth_a: Optional[speechsdk.SpeechSynthesizer] = None
        self.synth_b: Optional[speechsdk.SpeechSynthesizer] = None

        self._done = asyncio.Event()
        self._stopping = False

    # ---------------- public API ----------------

    async def start(self) -> None:
        self.loop = asyncio.get_running_loop()
        await self._emit("status", {"message": "Connecting to Speech service..."})

        auth_token = await self._get_auth_token()

        translation_config = self._build_translation_config(auth_token)
        self.synth_a = self._build_synth(auth_token, self.lang_a)
        self.synth_b = self._build_synth(auth_token, self.lang_b)

        stream_format = speechsdk.audio.AudioStreamFormat(
            samples_per_second=self.SAMPLE_RATE, bits_per_sample=16, channels=1
        )
        self.push_stream = speechsdk.audio.PushAudioInputStream(stream_format=stream_format)
        audio_config = speechsdk.audio.AudioConfig(stream=self.push_stream)

        auto_detect = speechsdk.languageconfig.AutoDetectSourceLanguageConfig(
            languages=[self.lang_a, self.lang_b]
        )

        self.recognizer = speechsdk.translation.TranslationRecognizer(
            translation_config=translation_config,
            auto_detect_source_language_config=auto_detect,
            audio_config=audio_config,
        )

        self.recognizer.recognizing.connect(self._on_recognizing)
        self.recognizer.recognized.connect(self._on_recognized)
        self.recognizer.session_started.connect(
            lambda _evt: self._emit_threadsafe("status", {"message": "Listening..."})
        )
        self.recognizer.session_stopped.connect(self._on_session_stopped)
        self.recognizer.canceled.connect(self._on_canceled)

        self._emit_threadsafe(
            "language_pair",
            {
                "lang1": language_display(self.lang_a),
                "lang2": language_display(self.lang_b),
                "locale1": self.lang_a,
                "locale2": self.lang_b,
            },
        )

        self.recognizer.start_continuous_recognition()
        logger.info("Live Interpreter started: %s <-> %s", self.lang_a, self.lang_b)
        await self._emit("status", {"message": "Listening..."})

        try:
            await self._done.wait()
        finally:
            await self._cleanup()

    def push_audio(self, audio_b64: str) -> None:
        """Feed a base64-encoded PCM16 chunk from the browser into the recognizer."""
        if not self.push_stream or self._stopping:
            return
        try:
            self.push_stream.write(base64.b64decode(audio_b64))
        except Exception:
            logger.exception("push_audio failed")

    async def stop(self) -> None:
        self._done.set()

    # ---------------- internals ----------------

    async def _emit(self, event_type: str, payload: dict) -> None:
        try:
            result = self._emit_cb(event_type, payload)
            if asyncio.iscoroutine(result):
                await result
        except Exception:
            logger.exception("emit failed: %s", event_type)

    def _emit_threadsafe(self, event_type: str, payload: dict) -> None:
        """Schedule an emit from a Speech SDK callback thread."""
        if not self.loop:
            return
        try:
            asyncio.run_coroutine_threadsafe(self._emit(event_type, payload), self.loop)
        except RuntimeError:
            # Loop already closed.
            pass

    async def _get_auth_token(self) -> str:
        token = await self.credential.get_token("https://cognitiveservices.azure.com/.default")
        # NOTE: Speech SDK requires this exact format for AAD authentication.
        # Token lives ~60 min; a single session re-uses it. For very long
        # sessions the recognizer would need to be rebuilt with a fresh token.
        return f"aad#{self.resource_id}#{token.token}"

    def _build_translation_config(self, auth_token: str) -> speechsdk.translation.SpeechTranslationConfig:
        # Continuous language identification on TranslationRecognizer is only
        # supported via the v2 universal endpoint. With a plain region-based
        # config the SDK falls back to "at-start" LID and effectively pins the
        # source language to the first one in the list, which breaks B->A.
        endpoint = f"wss://{self.region}.stt.speech.microsoft.com/speech/universal/v2"
        cfg = speechsdk.translation.SpeechTranslationConfig(endpoint=endpoint)
        cfg.authorization_token = auth_token
        cfg.add_target_language(self.code_a)
        cfg.add_target_language(self.code_b)
        cfg.set_property(
            property_id=speechsdk.PropertyId.SpeechServiceConnection_LanguageIdMode,
            value="Continuous",
        )
        return cfg

    def _build_synth(self, auth_token: str, locale: str) -> speechsdk.SpeechSynthesizer:
        sc = speechsdk.SpeechConfig(auth_token=auth_token, region=self.region)
        sc.speech_synthesis_voice_name = voice_for(locale)
        sc.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Raw24Khz16BitMonoPcm
        )
        # audio_config=None => we get audio bytes back via result.audio_data
        return speechsdk.SpeechSynthesizer(speech_config=sc, audio_config=None)

    # ---------------- Speech SDK event handlers (SDK threads) ----------------

    def _detected_source(self, evt) -> Optional[str]:
        try:
            return evt.result.properties.get(
                speechsdk.PropertyId.SpeechServiceConnection_AutoDetectSourceLanguageResult
            )
        except Exception:
            return None

    def _target_for_source(self, src_locale: Optional[str]) -> Tuple[str, str]:
        """Pick the other side of the pair as the translation target."""
        if src_locale:
            s = src_locale.lower()
            a = self.lang_a.lower()
            b = self.lang_b.lower()
            s_base = s.split("-")[0]
            if s == b or s_base == b.split("-")[0]:
                return self.code_a, self.lang_a
            if s == a or s_base == a.split("-")[0]:
                return self.code_b, self.lang_b
        # Unknown source: default to translating into B.
        return self.code_b, self.lang_b

    def _on_recognizing(self, evt) -> None:
        text = evt.result.text or ""
        if not text:
            return
        src = self._detected_source(evt)
        target_code, target_locale = self._target_for_source(src)
        translated = evt.result.translations.get(target_code, "")
        self._emit_threadsafe(
            "partial",
            {
                "source": text,
                "translation": translated,
                "source_locale": src,
                "target_locale": target_locale,
            },
        )

    def _on_recognized(self, evt) -> None:
        if evt.result.reason != speechsdk.ResultReason.TranslatedSpeech:
            return
        text = evt.result.text or ""
        if not text:
            return
        src = self._detected_source(evt)
        target_code, target_locale = self._target_for_source(src)
        translated = evt.result.translations.get(target_code, "")
        if not translated:
            return

        self._emit_threadsafe(
            "final",
            {
                "source": text,
                "translation": translated,
                "source_locale": src,
                "target_locale": target_locale,
            },
        )

        synth = self.synth_a if target_locale == self.lang_a else self.synth_b
        if synth is None:
            return
        try:
            result = synth.speak_text_async(translated).get()
            if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
                logger.warning("Synthesis non-success result: %s", result.reason)
                return
            audio = result.audio_data or b""
            if not audio:
                return
            # 24kHz * 16-bit mono => 48,000 bytes/sec. 4800 bytes ~= 100ms.
            chunk_size = 4800
            for i in range(0, len(audio), chunk_size):
                b64 = base64.b64encode(audio[i : i + chunk_size]).decode("ascii")
                self._emit_threadsafe("audio", {"data": b64})
        except Exception:
            logger.exception("Synthesis failed")

    def _on_session_stopped(self, _evt) -> None:
        logger.info("Speech session stopped")
        self._emit_threadsafe("status", {"message": "Stopped"})
        if self.loop and not self._done.is_set():
            self.loop.call_soon_threadsafe(self._done.set)

    def _on_canceled(self, evt) -> None:
        details = getattr(evt, "cancellation_details", None)
        msg = getattr(details, "error_details", None) or str(evt)
        logger.error("Recognition canceled: %s", msg)
        self._emit_threadsafe("error", {"message": f"Recognition canceled: {msg}"})
        if self.loop and not self._done.is_set():
            self.loop.call_soon_threadsafe(self._done.set)

    async def _cleanup(self) -> None:
        self._stopping = True
        try:
            if self.recognizer:
                self.recognizer.stop_continuous_recognition()
        except Exception:
            logger.exception("stop recognizer failed")
        try:
            if self.push_stream:
                self.push_stream.close()
        except Exception:
            pass
        self.recognizer = None
        self.push_stream = None
        self.synth_a = None
        self.synth_b = None
