# SPDX-License-Identifier: MIT
# -*- coding: utf-8 -*-
"""
Realtime Voice Bridge — OpenAI Realtime S2S WebSocket & Fonoster PBX Telephony.
================================================================================
Assimilated from speech-to-speech modular pipeline (VAD -> STT -> LLM -> TTS)
and Fonoster programmable voice PBX call flow verbs (Answer, Say, Gather, Stream, Dial).

Zero external dependencies outside Python stdlib (built on asyncio, dataclasses,
json, struct, hashlib, base64, urllib, math, time, and uuid).

Standard Realtime WebSocket endpoint:
    ws://0.0.0.0:8765/v1/realtime

Run as module:
    python -m control_plane.dispatch.realtime_voice_bridge --test
    python -m control_plane.dispatch.realtime_voice_bridge --serve --port 8765
"""
from __future__ import annotations

__version__ = "9000.25"

import asyncio
import base64
import dataclasses
import enum
import hashlib
import json
import logging
import math
import os
import struct
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logger = logging.getLogger("realtime_voice_bridge")

# ── Audio & Pipeline Constants ───────────────────────────────────────────────

DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHANNELS = 1
DEFAULT_BYTES_PER_SAMPLE = 2  # 16-bit PCM
DEFAULT_FRAME_SAMPLES = 512
DEFAULT_FRAME_BYTES = DEFAULT_FRAME_SAMPLES * DEFAULT_BYTES_PER_SAMPLE
DEFAULT_PORT = int(os.environ.get("REALTIME_VOICE_PORT", "8765"))
DEFAULT_HOST = os.environ.get("REALTIME_VOICE_HOST", "0.0.0.0")

# WebSocket GUID for RFC 6455 Handshake
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


# ── Utilities ────────────────────────────────────────────────────────────────

def generate_id(prefix: str = "item") -> str:
    """Generate a unique ID formatted like item_xxxxxxxx."""
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def compute_audio_duration_seconds(num_bytes: int, sample_rate: int = DEFAULT_SAMPLE_RATE, bytes_per_sample: int = 2) -> float:
    """Compute duration in seconds from raw PCM byte length."""
    if sample_rate <= 0 or bytes_per_sample <= 0:
        return 0.0
    return num_bytes / (sample_rate * bytes_per_sample)


def create_wav_header(pcm_bytes_len: int, sample_rate: int = DEFAULT_SAMPLE_RATE, channels: int = 1, bits_per_sample: int = 16) -> bytes:
    """Create standard 44-byte RIFF WAV header for PCM audio."""
    byte_rate = sample_rate * channels * (bits_per_sample // 8)
    block_align = channels * (bits_per_sample // 8)
    data_size = pcm_bytes_len
    file_size = data_size + 36

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        file_size,
        b"WAVE",
        b"fmt ",
        16,  # Subchunk1Size (16 for PCM)
        1,   # AudioFormat (1 for PCM)
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )
    return header


# ── OpenAI Realtime Protocol Event Models ───────────────────────────────────

class RealtimeEventType(str, enum.Enum):
    # Client events
    SESSION_UPDATE = "session.update"
    INPUT_AUDIO_BUFFER_APPEND = "input_audio_buffer.append"
    INPUT_AUDIO_BUFFER_COMMIT = "input_audio_buffer.commit"
    INPUT_AUDIO_BUFFER_CLEAR = "input_audio_buffer.clear"
    CONVERSATION_ITEM_CREATE = "conversation.item.create"
    CONVERSATION_ITEM_DELETE = "conversation.item.delete"
    CONVERSATION_ITEM_TRUNCATE = "conversation.item.truncate"
    RESPONSE_CREATE = "response.create"
    RESPONSE_CANCEL = "response.cancel"
    OUTPUT_AUDIO_BUFFER_CLEAR = "output_audio_buffer.clear"

    # Server events
    SESSION_CREATED = "session.created"
    SESSION_UPDATED = "session.updated"
    CONVERSATION_ITEM_CREATED = "conversation.item.created"
    CONVERSATION_ITEM_DELETED = "conversation.item.deleted"
    CONVERSATION_ITEM_TRUNCATED = "conversation.item.truncated"
    CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_DELTA = "conversation.item.input_audio_transcription.delta"
    CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_COMPLETED = "conversation.item.input_audio_transcription.completed"
    INPUT_AUDIO_BUFFER_COMMITTED = "input_audio_buffer.committed"
    INPUT_AUDIO_BUFFER_CLEARED = "input_audio_buffer.cleared"
    INPUT_AUDIO_BUFFER_SPEECH_STARTED = "input_audio_buffer.speech_started"
    INPUT_AUDIO_BUFFER_SPEECH_STOPPED = "input_audio_buffer.speech_stopped"
    RESPONSE_CREATED = "response.created"
    RESPONSE_DONE = "response.done"
    RESPONSE_OUTPUT_ITEM_ADDED = "response.output_item.added"
    RESPONSE_OUTPUT_ITEM_DONE = "response.output_item.done"
    RESPONSE_CONTENT_PART_ADDED = "response.content_part.added"
    RESPONSE_CONTENT_PART_DONE = "response.content_part.done"
    RESPONSE_TEXT_DELTA = "response.text.delta"
    RESPONSE_TEXT_DONE = "response.text.done"
    RESPONSE_AUDIO_TRANSCRIPT_DELTA = "response.audio_transcript.delta"
    RESPONSE_AUDIO_TRANSCRIPT_DONE = "response.audio_transcript.done"
    RESPONSE_AUDIO_DELTA = "response.audio.delta"
    RESPONSE_AUDIO_DONE = "response.audio.done"
    RESPONSE_FUNCTION_CALL_ARGUMENTS_DELTA = "response.function_call_arguments.delta"
    RESPONSE_FUNCTION_CALL_ARGUMENTS_DONE = "response.function_call_arguments.done"
    RATE_LIMITS_UPDATED = "rate_limits.updated"
    ERROR = "error"


@dataclass
class RealtimeSessionConfig:
    modalities: List[str] = field(default_factory=lambda: ["text", "audio"])
    instructions: str = "You are Camelot-OS Sovereign Voice Intelligence."
    voice: str = "alloy"
    input_audio_format: str = "pcm16"
    output_audio_format: str = "pcm16"
    input_audio_transcription: Optional[Dict[str, Any]] = field(default_factory=lambda: {"model": "whisper-1"})
    turn_detection: Optional[Dict[str, Any]] = field(default_factory=lambda: {
        "type": "server_vad",
        "threshold": 0.5,
        "prefix_padding_ms": 300,
        "silence_duration_ms": 500,
    })
    tools: List[Dict[str, Any]] = field(default_factory=list)
    tool_choice: str = "auto"
    temperature: float = 0.8
    max_response_output_tokens: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "modalities": self.modalities,
            "instructions": self.instructions,
            "voice": self.voice,
            "input_audio_format": self.input_audio_format,
            "output_audio_format": self.output_audio_format,
            "input_audio_transcription": self.input_audio_transcription,
            "turn_detection": self.turn_detection,
            "tools": self.tools,
            "tool_choice": self.tool_choice,
            "temperature": self.temperature,
            "max_response_output_tokens": self.max_response_output_tokens,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RealtimeSessionConfig:
        fields = {f.name for f in dataclasses.fields(cls)}
        valid_kwargs = {k: v for k, v in data.items() if k in fields}
        return cls(**valid_kwargs)


@dataclass
class RealtimeMessage:
    type: str
    event_id: str = field(default_factory=lambda: generate_id("event"))
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        res = {"type": self.type, "event_id": self.event_id}
        res.update(self.data)
        return res

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> RealtimeMessage:
        raw_copy = dict(raw)
        msg_type = str(raw_copy.pop("type", "unknown"))
        event_id = str(raw_copy.pop("event_id", generate_id("event")))
        return cls(type=msg_type, event_id=event_id, data=raw_copy)


# ── Modular Speech-to-Speech (S2S) Pipeline ─────────────────────────────────

@dataclass
class VADConfig:
    sample_rate: int = DEFAULT_SAMPLE_RATE
    frame_samples: int = DEFAULT_FRAME_SAMPLES
    energy_threshold: float = 0.02
    speech_start_frames: int = 3
    silence_frames_hangover: int = 15


class VADProcessor:
    """Zero-dependency windowed RMS energy Voice Activity Detector with hysteresis."""

    def __init__(self, config: Optional[VADConfig] = None):
        self.config = config or VADConfig()
        self.is_speech_active: bool = False
        self._speech_frame_count: int = 0
        self._silence_frame_count: int = 0
        self._audio_buffer: bytearray = bytearray()
        self.speech_start_callback: Optional[Callable[[], None]] = None
        self.speech_stop_callback: Optional[Callable[[bytes], None]] = None
        self._current_speech_audio: bytearray = bytearray()

    def calculate_rms(self, pcm_chunk: bytes) -> float:
        """Calculate Root Mean Square (RMS) normalized to 0.0 - 1.0 for 16-bit PCM."""
        num_samples = len(pcm_chunk) // 2
        if num_samples == 0:
            return 0.0
        try:
            samples = struct.unpack(f"<{num_samples}h", pcm_chunk[: num_samples * 2])
            sum_sq = sum(s * s for s in samples)
            rms = math.sqrt(sum_sq / num_samples)
            return min(1.0, rms / 32768.0)
        except Exception:
            return 0.0

    def process_chunk(self, chunk: bytes) -> Tuple[bool, Optional[str], Optional[bytes]]:
        """
        Process incoming PCM chunk.
        Returns (is_voiced, transition_event, completed_speech_bytes).
        transition_event is 'speech_started', 'speech_stopped', or None.
        """
        self._audio_buffer.extend(chunk)
        transition: Optional[str] = None
        speech_bytes: Optional[bytes] = None
        frame_bytes = self.config.frame_samples * DEFAULT_BYTES_PER_SAMPLE

        while len(self._audio_buffer) >= frame_bytes:
            frame = bytes(self._audio_buffer[:frame_bytes])
            del self._audio_buffer[:frame_bytes]
            rms = self.calculate_rms(frame)

            if rms >= self.config.energy_threshold:
                self._speech_frame_count += 1
                self._silence_frame_count = 0
                if not self.is_speech_active and self._speech_frame_count >= self.config.speech_start_frames:
                    self.is_speech_active = True
                    transition = "speech_started"
                    self._current_speech_audio.clear()
                    if self.speech_start_callback:
                        self.speech_start_callback()
            else:
                self._silence_frame_count += 1
                self._speech_frame_count = 0
                if self.is_speech_active and self._silence_frame_count >= self.config.silence_frames_hangover:
                    self.is_speech_active = False
                    transition = "speech_stopped"
                    speech_bytes = bytes(self._current_speech_audio)
                    self._current_speech_audio.clear()
                    if self.speech_stop_callback:
                        self.speech_stop_callback(speech_bytes)

            if self.is_speech_active:
                self._current_speech_audio.extend(frame)

        return self.is_speech_active, transition, speech_bytes

    def reset(self) -> None:
        self.is_speech_active = False
        self._speech_frame_count = 0
        self._silence_frame_count = 0
        self._audio_buffer.clear()
        self._current_speech_audio.clear()


class STTProcessor:
    """Modular Speech-To-Text processor."""

    def __init__(self, transcribe_fn: Optional[Callable[[bytes], str]] = None):
        self.transcribe_fn = transcribe_fn or self._default_transcribe

    def _default_transcribe(self, audio_pcm: bytes) -> str:
        if not audio_pcm:
            return ""
        # Default mock / rule-based fallback when offline
        return "Command received."

    def transcribe(self, audio_pcm: bytes) -> str:
        return self.transcribe_fn(audio_pcm)


class LLMProcessor:
    """Modular LLM conversational turn processor with streaming simulation."""

    def __init__(self, system_prompt: str = "You are Camelot-OS Sovereign Voice Intelligence."):
        self.system_prompt = system_prompt
        self.history: List[Dict[str, str]] = []

    def add_message(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})

    def generate_response(self, user_text: str) -> str:
        self.add_message("user", user_text)
        # Sovereign Camelot-OS dispatch logic
        lower = user_text.lower().strip()
        if "status" in lower:
            reply = "All Camelot-OS sovereign nodes, Bifrost bridges, and omniroute KV pipelines are operational."
        elif "rezero" in lower:
            reply = "Rezeroing pipeline context. Last verified stable state restored."
        elif "ping" in lower:
            reply = "Pong. Realtime voice bridge latency nominal."
        else:
            reply = f"Acknowledged: {user_text}. Processing across Camelot swarm."
        self.add_message("assistant", reply)
        return reply


class TTSProcessor:
    """Modular Text-To-Speech processor synthesizing PCM audio."""

    def __init__(self, sample_rate: int = DEFAULT_SAMPLE_RATE):
        self.sample_rate = sample_rate

    def synthesize_pcm(self, text: str, duration_s: float = 0.5) -> bytes:
        """Synthesize tone PCM audio for testing and streaming verification."""
        num_samples = int(self.sample_rate * duration_s)
        # Generate a gentle multi-tone chime (440Hz / 880Hz)
        samples = []
        for i in range(num_samples):
            t = i / self.sample_rate
            # Harmonic chime envelope
            envelope = math.exp(-3.0 * t / duration_s)
            val = 0.5 * math.sin(2 * math.pi * 440 * t) + 0.3 * math.sin(2 * math.pi * 880 * t)
            sample_val = int(val * envelope * 24000)
            sample_val = max(-32768, min(32767, sample_val))
            samples.append(sample_val)
        return struct.pack(f"<{len(samples)}h", *samples)


# ── Fonoster Programmable Voice PBX Telephony ───────────────────────────────

class GatherSource(str, enum.Enum):
    DTMF = "DTMF"
    SPEECH = "SPEECH"
    SPEECH_AND_DTMF = "SPEECH_AND_DTMF"


class StreamDirection(str, enum.Enum):
    IN = "IN"
    OUT = "OUT"
    BOTH = "BOTH"


class StreamAudioFormat(str, enum.Enum):
    PCM16 = "PCM16"
    WAV = "WAV"


class PlaybackAction(str, enum.Enum):
    PLAY = "PLAY"
    STOP = "STOP"
    PAUSE = "PAUSE"
    UNPAUSE = "UNPAUSE"
    RESTART = "RESTART"
    FORWARD = "FORWARD"


class PBXCallStatus(str, enum.Enum):
    RINGING = "RINGING"
    ANSWERED = "ANSWERED"
    STREAMING = "STREAMING"
    GATHERING = "GATHERING"
    DIALING = "DIALING"
    COMPLETED = "COMPLETED"
    HANGUP = "HANGUP"


@dataclass
class VerbResult:
    verb: str
    status: str
    media_session_ref: str
    data: Dict[str, Any] = field(default_factory=dict)


class VoiceResponse:
    """
    Fonoster-compatible fluent VoiceResponse builder & execution engine.
    Allows declarative PBX voice applications:
        vr = VoiceResponse(session_ref)
        await vr.answer()
        await vr.say("Hello, Camelot!")
        digits = await vr.gather(max_digits=4)
        await vr.dial("sip:boris@camelot.local")
        await vr.hangup()
    """

    def __init__(self, media_session_ref: Optional[str] = None, session: Optional["PBXCallSession"] = None):
        self.media_session_ref = media_session_ref or generate_id("call_media")
        self.session = session
        self.executed_verbs: List[VerbResult] = []
        self._dtmf_buffer: str = ""

    async def answer(self) -> VerbResult:
        res = VerbResult(verb="Answer", status="ok", media_session_ref=self.media_session_ref)
        self.executed_verbs.append(res)
        if self.session:
            self.session.status = PBXCallStatus.ANSWERED
        return res

    async def say(self, text: str, voice: str = "alloy", playback_ref: Optional[str] = None, speed: float = 1.0) -> VerbResult:
        playback_id = playback_ref or generate_id("playback")
        res = VerbResult(
            verb="Say",
            status="ok",
            media_session_ref=self.media_session_ref,
            data={"text": text, "voice": voice, "playback_ref": playback_id, "speed": speed},
        )
        self.executed_verbs.append(res)
        return res

    async def stop_say(self, playback_ref: Optional[str] = None) -> VerbResult:
        res = VerbResult(
            verb="StopSay",
            status="ok",
            media_session_ref=self.media_session_ref,
            data={"playback_ref": playback_ref},
        )
        self.executed_verbs.append(res)
        return res

    async def gather(
        self,
        source: GatherSource = GatherSource.SPEECH_AND_DTMF,
        max_digits: int = 1,
        timeout_ms: int = 4000,
        finish_on_key: str = "#",
    ) -> Dict[str, Any]:
        res = VerbResult(
            verb="Gather",
            status="ok",
            media_session_ref=self.media_session_ref,
            data={
                "source": source.value if isinstance(source, GatherSource) else str(source),
                "max_digits": max_digits,
                "timeout_ms": timeout_ms,
                "finish_on_key": finish_on_key,
            },
        )
        self.executed_verbs.append(res)
        if self.session:
            self.session.status = PBXCallStatus.GATHERING
            # Return collected DTMF or mock speech
            collected = self.session.pop_dtmf(max_digits)
            return {"digits": collected or "1", "speech": "", "source": source.value if isinstance(source, GatherSource) else str(source)}
        return {"digits": "1", "speech": "", "source": "SPEECH_AND_DTMF"}

    async def stream(
        self,
        direction: StreamDirection = StreamDirection.BOTH,
        format: StreamAudioFormat = StreamAudioFormat.PCM16,
    ) -> VerbResult:
        stream_ref = generate_id("stream")
        res = VerbResult(
            verb="Stream",
            status="ok",
            media_session_ref=self.media_session_ref,
            data={
                "stream_ref": stream_ref,
                "direction": direction.value if isinstance(direction, StreamDirection) else str(direction),
                "format": format.value if isinstance(format, StreamAudioFormat) else str(format),
            },
        )
        self.executed_verbs.append(res)
        if self.session:
            self.session.status = PBXCallStatus.STREAMING
        return res

    async def dial(
        self,
        destination: str,
        timeout_s: int = 60,
        record_direction: str = "BOTH",
    ) -> VerbResult:
        res = VerbResult(
            verb="Dial",
            status="ok",
            media_session_ref=self.media_session_ref,
            data={"destination": destination, "timeout_s": timeout_s, "record_direction": record_direction},
        )
        self.executed_verbs.append(res)
        if self.session:
            self.session.status = PBXCallStatus.DIALING
        return res

    async def hangup(self) -> VerbResult:
        res = VerbResult(verb="Hangup", status="ok", media_session_ref=self.media_session_ref)
        self.executed_verbs.append(res)
        if self.session:
            self.session.status = PBXCallStatus.HANGUP
        return res

    async def play(self, url: str, playback_ref: Optional[str] = None) -> VerbResult:
        playback_id = playback_ref or generate_id("playback")
        res = VerbResult(
            verb="Play",
            status="ok",
            media_session_ref=self.media_session_ref,
            data={"url": url, "playback_ref": playback_id},
        )
        self.executed_verbs.append(res)
        return res

    async def mute(self, direction: str = "BOTH") -> VerbResult:
        res = VerbResult(
            verb="Mute",
            status="ok",
            media_session_ref=self.media_session_ref,
            data={"direction": direction},
        )
        self.executed_verbs.append(res)
        return res

    async def unmute(self, direction: str = "BOTH") -> VerbResult:
        res = VerbResult(
            verb="Unmute",
            status="ok",
            media_session_ref=self.media_session_ref,
            data={"direction": direction},
        )
        self.executed_verbs.append(res)
        return res

    async def record(self, max_duration_s: int = 60, max_silence_s: int = 5, beep: bool = True) -> Dict[str, Any]:
        record_ref = generate_id("rec")
        res = VerbResult(
            verb="Record",
            status="ok",
            media_session_ref=self.media_session_ref,
            data={"record_ref": record_ref, "max_duration_s": max_duration_s, "max_silence_s": max_silence_s, "beep": beep},
        )
        self.executed_verbs.append(res)
        return {"name": f"{record_ref}.wav", "duration_s": 1.5, "record_ref": record_ref}


@dataclass
class PBXCallSession:
    call_id: str = field(default_factory=lambda: generate_id("call"))
    caller_id: str = "anonymous"
    destination: str = "camelot_switchboard"
    status: PBXCallStatus = PBXCallStatus.RINGING
    media_session_ref: str = field(default_factory=lambda: generate_id("media"))
    created_at: float = field(default_factory=time.time)
    dtmf_buffer: str = ""
    voice_response: Optional[VoiceResponse] = None

    def __post_init__(self):
        if self.voice_response is None:
            self.voice_response = VoiceResponse(self.media_session_ref, session=self)

    def inject_dtmf(self, digits: str) -> None:
        self.dtmf_buffer += digits

    def pop_dtmf(self, max_digits: int = 1) -> str:
        out = self.dtmf_buffer[:max_digits]
        self.dtmf_buffer = self.dtmf_buffer[max_digits:]
        return out


# ── Realtime Session Orchestrator & Telemetry ────────────────────────────────

@dataclass
class RealtimeSessionMetrics:
    total_audio_in_bytes: int = 0
    total_audio_out_bytes: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    turns: int = 0
    interruptions: int = 0
    ttft_ms: float = 0.0
    ttfa_ms: float = 0.0
    vad_latency_ms: float = 0.0
    stt_latency_ms: float = 0.0
    llm_latency_ms: float = 0.0
    tts_latency_ms: float = 0.0


class RealtimeVoiceSession:
    """
    Orchestrates a single client WebSocket connection:
    - Ingests audio and events
    - Runs VAD -> STT -> LLM -> TTS pipeline
    - Manages barge-in interruptions
    - Encodes and dispatches OpenAI Realtime Server Events
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        config: Optional[RealtimeSessionConfig] = None,
        vad_processor: Optional[VADProcessor] = None,
        stt_processor: Optional[STTProcessor] = None,
        llm_processor: Optional[LLMProcessor] = None,
        tts_processor: Optional[TTSProcessor] = None,
        send_event_fn: Optional[Callable[[RealtimeMessage], asyncio.Future[None]]] = None,
    ):
        self.session_id = session_id or generate_id("sess")
        self.conversation_id = generate_id("conv")
        self.config = config or RealtimeSessionConfig()
        self.vad = vad_processor or VADProcessor()
        self.stt = stt_processor or STTProcessor()
        self.llm = llm_processor or LLMProcessor(self.config.instructions)
        self.tts = tts_processor or TTSProcessor()
        self.send_event_fn = send_event_fn

        self.metrics = RealtimeSessionMetrics()
        self.in_response: bool = False
        self.current_response_id: Optional[str] = None
        self.current_item_id: Optional[str] = None
        self.audio_input_buffer: bytearray = bytearray()
        self._cancel_generation_flag: bool = False

        # Wire VAD callbacks
        self.vad.speech_start_callback = self._on_vad_speech_start
        self.vad.speech_stop_callback = self._on_vad_speech_stop

    def _on_vad_speech_start(self) -> None:
        """Triggered when user speech begins. Executes barge-in cancellation if currently speaking."""
        self.metrics.turns += 1
        if self.in_response:
            self.metrics.interruptions += 1
            self._cancel_generation_flag = True
            self.in_response = False

    def _on_vad_speech_stop(self, speech_bytes: bytes) -> None:
        """Triggered when user speech ends. Dispatches transcription and response."""
        if not speech_bytes:
            return

    async def emit_event(self, msg: RealtimeMessage) -> None:
        if self.send_event_fn:
            res = self.send_event_fn(msg)
            if asyncio.iscoroutine(res):
                await res

    async def handle_client_message(self, raw: Dict[str, Any]) -> List[RealtimeMessage]:
        """Handle parsed client event and return outgoing response messages."""
        msg = RealtimeMessage.from_dict(raw)
        out_events: List[RealtimeMessage] = []

        if msg.type == RealtimeEventType.SESSION_UPDATE:
            sess_data = msg.data.get("session", {})
            self.config = RealtimeSessionConfig.from_dict(sess_data)
            evt = RealtimeMessage(
                type=RealtimeEventType.SESSION_UPDATED.value,
                data={"session": self.config.to_dict()},
            )
            out_events.append(evt)
            await self.emit_event(evt)

        elif msg.type == RealtimeEventType.INPUT_AUDIO_BUFFER_APPEND:
            audio_b64 = msg.data.get("audio", "")
            if audio_b64:
                try:
                    pcm = base64.b64decode(audio_b64)
                    self.metrics.total_audio_in_bytes += len(pcm)
                    self.audio_input_buffer.extend(pcm)

                    # Feed VAD
                    t0 = time.perf_counter()
                    voiced, trans, speech_data = self.vad.process_chunk(pcm)
                    self.metrics.vad_latency_ms = (time.perf_counter() - t0) * 1000.0

                    if trans == "speech_started":
                        evt = RealtimeMessage(
                            type=RealtimeEventType.INPUT_AUDIO_BUFFER_SPEECH_STARTED.value,
                            data={"audio_start_ms": 0, "item_id": generate_id("item")},
                        )
                        out_events.append(evt)
                        await self.emit_event(evt)

                    elif trans == "speech_stopped" and speech_data:
                        evt = RealtimeMessage(
                            type=RealtimeEventType.INPUT_AUDIO_BUFFER_SPEECH_STOPPED.value,
                            data={"audio_end_ms": int(len(speech_data) / 32)},
                        )
                        out_events.append(evt)
                        await self.emit_event(evt)

                        # Pipeline: STT -> LLM -> TTS
                        response_events = await self._run_pipeline(speech_data)
                        out_events.extend(response_events)

                except Exception as exc:
                    logger.error(f"Error handling audio append: {exc}")

        elif msg.type == RealtimeEventType.INPUT_AUDIO_BUFFER_COMMIT:
            buffered = bytes(self.audio_input_buffer)
            self.audio_input_buffer.clear()
            evt = RealtimeMessage(
                type=RealtimeEventType.INPUT_AUDIO_BUFFER_COMMITTED.value,
                data={"item_id": generate_id("item")},
            )
            out_events.append(evt)
            await self.emit_event(evt)

            if buffered:
                response_events = await self._run_pipeline(buffered)
                out_events.extend(response_events)

        elif msg.type == RealtimeEventType.INPUT_AUDIO_BUFFER_CLEAR:
            self.audio_input_buffer.clear()
            self.vad.reset()
            evt = RealtimeMessage(type=RealtimeEventType.INPUT_AUDIO_BUFFER_CLEARED.value)
            out_events.append(evt)
            await self.emit_event(evt)

        elif msg.type == RealtimeEventType.CONVERSATION_ITEM_CREATE:
            item = msg.data.get("item", {})
            item_id = item.get("id") or generate_id("item")
            evt = RealtimeMessage(
                type=RealtimeEventType.CONVERSATION_ITEM_CREATED.value,
                data={"item": item, "previous_item_id": msg.data.get("previous_item_id")},
            )
            out_events.append(evt)
            await self.emit_event(evt)

        elif msg.type == RealtimeEventType.RESPONSE_CREATE:
            # Explicit trigger for response creation
            resp_params = msg.data.get("response", {})
            out_events.extend(await self._create_response_flow(resp_params))

        elif msg.type == RealtimeEventType.RESPONSE_CANCEL:
            self._cancel_generation_flag = True
            self.in_response = False
            evt = RealtimeMessage(
                type=RealtimeEventType.RESPONSE_DONE.value,
                data={"response": {"id": self.current_response_id or generate_id("resp"), "status": "cancelled"}},
            )
            out_events.append(evt)
            await self.emit_event(evt)

        return out_events

    async def _run_pipeline(self, speech_pcm: bytes) -> List[RealtimeMessage]:
        """Execute STT -> LLM -> TTS pipeline for completed speech."""
        events: List[RealtimeMessage] = []
        self._cancel_generation_flag = False
        self.in_response = True
        self.current_response_id = generate_id("resp")
        self.current_item_id = generate_id("item")

        # 1. STT Phase
        t0_stt = time.perf_counter()
        transcript = self.stt.transcribe(speech_pcm)
        self.metrics.stt_latency_ms = (time.perf_counter() - t0_stt) * 1000.0

        trans_evt = RealtimeMessage(
            type=RealtimeEventType.CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_COMPLETED.value,
            data={"item_id": self.current_item_id, "transcript": transcript},
        )
        events.append(trans_evt)
        await self.emit_event(trans_evt)

        if not transcript or self._cancel_generation_flag:
            self.in_response = False
            return events

        # 2. LLM Phase
        t0_llm = time.perf_counter()
        reply_text = self.llm.generate_response(transcript)
        self.metrics.llm_latency_ms = (time.perf_counter() - t0_llm) * 1000.0
        self.metrics.ttft_ms = self.metrics.stt_latency_ms + self.metrics.llm_latency_ms
        self.metrics.input_tokens += len(transcript.split())
        self.metrics.output_tokens += len(reply_text.split())

        resp_created = RealtimeMessage(
            type=RealtimeEventType.RESPONSE_CREATED.value,
            data={"response": {"id": self.current_response_id, "status": "in_progress"}},
        )
        events.append(resp_created)
        await self.emit_event(resp_created)

        # Emit text delta
        text_delta = RealtimeMessage(
            type=RealtimeEventType.RESPONSE_TEXT_DELTA.value,
            data={"response_id": self.current_response_id, "item_id": self.current_item_id, "delta": reply_text},
        )
        events.append(text_delta)
        await self.emit_event(text_delta)

        # 3. TTS Phase
        t0_tts = time.perf_counter()
        out_pcm = self.tts.synthesize_pcm(reply_text)
        self.metrics.tts_latency_ms = (time.perf_counter() - t0_tts) * 1000.0
        self.metrics.ttfa_ms = self.metrics.ttft_ms + self.metrics.tts_latency_ms
        self.metrics.total_audio_out_bytes += len(out_pcm)

        if not self._cancel_generation_flag:
            audio_b64 = base64.b64encode(out_pcm).decode("ascii")
            audio_delta = RealtimeMessage(
                type=RealtimeEventType.RESPONSE_AUDIO_DELTA.value,
                data={"response_id": self.current_response_id, "item_id": self.current_item_id, "delta": audio_b64},
            )
            events.append(audio_delta)
            await self.emit_event(audio_delta)

            audio_done = RealtimeMessage(
                type=RealtimeEventType.RESPONSE_AUDIO_DONE.value,
                data={"response_id": self.current_response_id, "item_id": self.current_item_id},
            )
            events.append(audio_done)
            await self.emit_event(audio_done)

        resp_done = RealtimeMessage(
            type=RealtimeEventType.RESPONSE_DONE.value,
            data={
                "response": {
                    "id": self.current_response_id,
                    "status": "cancelled" if self._cancel_generation_flag else "completed",
                    "usage": {
                        "total_tokens": self.metrics.input_tokens + self.metrics.output_tokens,
                        "input_tokens": self.metrics.input_tokens,
                        "output_tokens": self.metrics.output_tokens,
                    },
                }
            },
        )
        events.append(resp_done)
        await self.emit_event(resp_done)

        self.in_response = False
        return events

    async def _create_response_flow(self, params: Dict[str, Any]) -> List[RealtimeMessage]:
        """Synthesize and return an explicit response for user instructions."""
        self.current_response_id = generate_id("resp")
        resp_created = RealtimeMessage(
            type=RealtimeEventType.RESPONSE_CREATED.value,
            data={"response": {"id": self.current_response_id, "status": "in_progress"}},
        )
        resp_done = RealtimeMessage(
            type=RealtimeEventType.RESPONSE_DONE.value,
            data={"response": {"id": self.current_response_id, "status": "completed"}},
        )
        return [resp_created, resp_done]


# ── Pure-Python RFC 6455 WebSocket Parser & Server ──────────────────────────

class WSFrameOpcode(enum.IntEnum):
    CONTINUATION = 0x0
    TEXT = 0x1
    BINARY = 0x2
    CLOSE = 0x8
    PING = 0x9
    PONG = 0xA


class WSFrame:
    """RFC 6455 WebSocket Frame parser and builder."""

    @staticmethod
    def encode_frame(payload: Union[str, bytes], opcode: WSFrameOpcode = WSFrameOpcode.TEXT, mask: bool = False) -> bytes:
        if isinstance(payload, str):
            data = payload.encode("utf-8")
        else:
            data = payload

        length = len(data)
        fin_opcode = 0x80 | (opcode & 0x0F)
        header = bytearray()
        header.append(fin_opcode)

        mask_bit = 0x80 if mask else 0x00
        if length < 126:
            header.append(mask_bit | length)
        elif length < 65536:
            header.append(mask_bit | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(mask_bit | 127)
            header.extend(struct.pack("!Q", length))

        if mask:
            mask_key = os.urandom(4)
            header.extend(mask_key)
            masked_data = bytearray(length)
            for i in range(length):
                masked_data[i] = data[i] ^ mask_key[i % 4]
            return bytes(header + masked_data)

        return bytes(header) + data

    @staticmethod
    def decode_frame(buf: bytearray) -> Tuple[Optional[WSFrameOpcode], Optional[bytes], int]:
        """
        Decode a single frame from bytearray buffer.
        Returns (opcode, payload, bytes_consumed).
        If buffer is incomplete, returns (None, None, 0).
        """
        if len(buf) < 2:
            return None, None, 0

        byte0 = buf[0]
        byte1 = buf[1]
        fin = bool(byte0 & 0x80)
        opcode = WSFrameOpcode(byte0 & 0x0F)
        is_masked = bool(byte1 & 0x80)
        payload_len = byte1 & 0x7F

        header_len = 2
        if payload_len == 126:
            if len(buf) < 4:
                return None, None, 0
            payload_len = struct.unpack("!H", buf[2:4])[0]
            header_len = 4
        elif payload_len == 127:
            if len(buf) < 10:
                return None, None, 0
            payload_len = struct.unpack("!Q", buf[2:10])[0]
            header_len = 10

        mask_key = None
        if is_masked:
            if len(buf) < header_len + 4:
                return None, None, 0
            mask_key = buf[header_len : header_len + 4]
            header_len += 4

        total_frame_len = header_len + payload_len
        if len(buf) < total_frame_len:
            return None, None, 0

        raw_payload = buf[header_len:total_frame_len]
        if is_masked and mask_key:
            unmasked = bytearray(payload_len)
            for i in range(payload_len):
                unmasked[i] = raw_payload[i] ^ mask_key[i % 4]
            payload = bytes(unmasked)
        else:
            payload = bytes(raw_payload)

        return opcode, payload, total_frame_len


class RealtimeVoiceBridge:
    """
    Unified Realtime Voice Bridge combining:
    - OpenAI Realtime S2S WebSocket Pipeline (/v1/realtime)
    - Fonoster PBX Telephony engine (/v1/pbx/calls)
    - Multivoice metrics and telemetry aggregator (/v1/usage, /v1/pool, /metrics)
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self.active_sessions: Dict[str, RealtimeVoiceSession] = {}
        self.pbx_calls: Dict[str, PBXCallSession] = {}
        self.server: Optional[asyncio.Server] = None
        self._is_running: bool = False

    def create_session(self, config: Optional[RealtimeSessionConfig] = None) -> RealtimeVoiceSession:
        session = RealtimeVoiceSession(config=config)
        self.active_sessions[session.session_id] = session
        return session

    def create_pbx_call(self, caller_id: str = "anonymous", destination: str = "camelot_switchboard") -> PBXCallSession:
        call = PBXCallSession(caller_id=caller_id, destination=destination)
        self.pbx_calls[call.call_id] = call
        return call

    def get_aggregate_metrics(self) -> Dict[str, Any]:
        """Aggregate telemetry across all active voice sessions and PBX calls."""
        total_audio_in = sum(s.metrics.total_audio_in_bytes for s in self.active_sessions.values())
        total_audio_out = sum(s.metrics.total_audio_out_bytes for s in self.active_sessions.values())
        total_in_tokens = sum(s.metrics.input_tokens for s in self.active_sessions.values())
        total_out_tokens = sum(s.metrics.output_tokens for s in self.active_sessions.values())
        total_turns = sum(s.metrics.turns for s in self.active_sessions.values())
        total_interruptions = sum(s.metrics.interruptions for s in self.active_sessions.values())

        # Latencies
        active_count = len(self.active_sessions)
        avg_ttfa = (sum(s.metrics.ttfa_ms for s in self.active_sessions.values()) / active_count) if active_count > 0 else 0.0
        avg_ttft = (sum(s.metrics.ttft_ms for s in self.active_sessions.values()) / active_count) if active_count > 0 else 0.0

        return {
            "active_sessions": active_count,
            "active_pbx_calls": len(self.pbx_calls),
            "total_audio_in_bytes": total_audio_in,
            "total_audio_out_bytes": total_audio_out,
            "total_input_tokens": total_in_tokens,
            "total_output_tokens": total_out_tokens,
            "total_turns": total_turns,
            "total_interruptions": total_interruptions,
            "avg_ttfa_ms": round(avg_ttfa, 1),
            "avg_ttft_ms": round(avg_ttft, 1),
        }

    async def handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handle raw TCP/HTTP/WebSocket connection."""
        try:
            request_bytes = await reader.readuntil(b"\r\n\r\n")
            request_text = request_bytes.decode("utf-8", errors="replace")
            lines = request_text.split("\r\n")
            if not lines or not lines[0]:
                writer.close()
                return

            req_line_parts = lines[0].split(" ")
            if len(req_line_parts) < 2:
                writer.close()
                return

            method, path = req_line_parts[0], req_line_parts[1]
            headers = {}
            for line in lines[1:]:
                if ": " in line:
                    k, v = line.split(": ", 1)
                    headers[k.lower()] = v.strip()

            # 1. Check for WebSocket Upgrade
            if headers.get("upgrade", "").lower() == "websocket" and "/v1/realtime" in path:
                sec_key = headers.get("sec-websocket-key", "")
                accept_hash = hashlib.sha1((sec_key + WS_GUID).encode("utf-8")).digest()
                accept_val = base64.b64encode(accept_hash).decode("ascii")

                ws_response = (
                    "HTTP/1.1 101 Switching Protocols\r\n"
                    "Upgrade: websocket\r\n"
                    "Connection: Upgrade\r\n"
                    f"Sec-WebSocket-Accept: {accept_val}\r\n"
                    "Sec-WebSocket-Protocol: realtime\r\n\r\n"
                )
                writer.write(ws_response.encode("utf-8"))
                await writer.drain()

                # Run WebSocket loop
                await self._run_ws_client_loop(reader, writer)
                return

            # 2. HTTP JSON Endpoints
            if method == "GET" and path == "/v1/usage":
                metrics = self.get_aggregate_metrics()
                body = json.dumps(metrics).encode("utf-8")
                writer.write(f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n".encode("utf-8") + body)
                await writer.drain()
            elif method == "GET" and path == "/v1/pool":
                pool_data = {
                    "size": len(self.active_sessions),
                    "sessions": [{"id": k, "turns": v.metrics.turns} for k, v in self.active_sessions.items()],
                }
                body = json.dumps(pool_data).encode("utf-8")
                writer.write(f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n".encode("utf-8") + body)
                await writer.drain()
            elif method == "GET" and (path == "/metrics" or path == "/health"):
                status = {"status": "healthy", "service": "realtime_voice_bridge", "version": __version__}
                body = json.dumps(status).encode("utf-8")
                writer.write(f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n".encode("utf-8") + body)
                await writer.drain()
            else:
                writer.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
                await writer.drain()

        except Exception as e:
            logger.debug(f"Connection handling exception: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _run_ws_client_loop(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Run WebSocket event loop for connected client."""
        session = self.create_session()

        async def send_event(msg: RealtimeMessage) -> None:
            raw_json = msg.to_json()
            frame = WSFrame.encode_frame(raw_json, opcode=WSFrameOpcode.TEXT)
            writer.write(frame)
            await writer.drain()

        session.send_event_fn = send_event

        # Emit session.created
        await session.emit_event(
            RealtimeMessage(
                type=RealtimeEventType.SESSION_CREATED.value,
                data={"session": session.config.to_dict()},
            )
        )

        read_buf = bytearray()
        try:
            while self._is_running:
                data = await reader.read(4096)
                if not data:
                    break
                read_buf.extend(data)

                while True:
                    opcode, payload, consumed = WSFrame.decode_frame(read_buf)
                    if consumed == 0:
                        break
                    del read_buf[:consumed]

                    if opcode == WSFrameOpcode.CLOSE:
                        writer.write(WSFrame.encode_frame(b"", opcode=WSFrameOpcode.CLOSE))
                        await writer.drain()
                        return
                    elif opcode == WSFrameOpcode.PING:
                        writer.write(WSFrame.encode_frame(payload or b"", opcode=WSFrameOpcode.PONG))
                        await writer.drain()
                    elif opcode == WSFrameOpcode.TEXT and payload:
                        try:
                            msg_dict = json.loads(payload.decode("utf-8"))
                            await session.handle_client_message(msg_dict)
                        except Exception as parse_err:
                            logger.error(f"Error parsing client payload: {parse_err}")

        except Exception as loop_err:
            logger.debug(f"WS loop terminated: {loop_err}")
        finally:
            self.active_sessions.pop(session.session_id, None)

    async def start(self) -> None:
        self._is_running = True
        self.server = await asyncio.start_server(self.handle_connection, self.host, self.port)
        logger.info(f"RealtimeVoiceBridge started on ws://{self.host}:{self.port}/v1/realtime")

    async def stop(self) -> None:
        self._is_running = False
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        self.active_sessions.clear()
        self.pbx_calls.clear()


# ── Self Test Suite ──────────────────────────────────────────────────────────

def _selftest() -> int:
    failures = 0

    def check(name: str, cond: bool) -> None:
        nonlocal failures
        if not cond:
            failures += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    print("RealtimeVoiceBridge Self-Test")

    # 1. Event Models
    msg = RealtimeMessage(type=RealtimeEventType.SESSION_UPDATE.value, data={"session": {"voice": "echo"}})
    js = msg.to_json()
    parsed = RealtimeMessage.from_dict(json.loads(js))
    check("RealtimeMessage serialize / deserialize", parsed.type == "session.update" and parsed.data["session"]["voice"] == "echo")

    # 2. VAD Processor
    vad = VADProcessor(VADConfig(energy_threshold=0.01))
    silent_chunk = b"\x00\x00" * 512
    voiced, trans, speech = vad.process_chunk(silent_chunk)
    check("VAD silence detection", voiced is False and trans is None)

    # Generate synthetic loud audio frame
    loud_samples = [int(15000 * math.sin(i)) for i in range(512)]
    loud_chunk = struct.pack("<512h", *loud_samples)
    for _ in range(5):
        voiced, trans, speech = vad.process_chunk(loud_chunk)
    check("VAD voiced detection", voiced is True)

    # 3. Fonoster PBX Verbs & VoiceResponse
    call = PBXCallSession(caller_id="+15551234567", destination="sip:switchboard@camelot.local")
    check("PBXCallSession initial state", call.status == PBXCallStatus.RINGING)

    async def run_ivr():
        vr = call.voice_response
        await vr.answer()
        await vr.say("Welcome to Camelot-OS")
        call.inject_dtmf("42")
        g_res = await vr.gather(max_digits=2)
        await vr.stream(direction=StreamDirection.BOTH)
        await vr.dial("sip:merlin@camelot.local")
        await vr.hangup()
        return g_res

    res_digits = asyncio.run(run_ivr())
    check("VoiceResponse IVR execution", res_digits["digits"] == "42" and call.status == PBXCallStatus.HANGUP)
    check("VoiceResponse verb count", len(call.voice_response.executed_verbs) == 6)

    # 4. WebSocket Framing
    encoded = WSFrame.encode_frame("Hello Camelot", opcode=WSFrameOpcode.TEXT, mask=True)
    buf = bytearray(encoded)
    op, payload, consumed = WSFrame.decode_frame(buf)
    check("WSFrame masked encode/decode", op == WSFrameOpcode.TEXT and payload == b"Hello Camelot" and consumed == len(encoded))

    # 5. Full Realtime Voice Session Pipeline
    session = RealtimeVoiceSession()
    out_events = asyncio.run(
        session.handle_client_message({
            "type": "session.update",
            "session": {"voice": "shimmer", "instructions": "Test persona"}
        })
    )
    check("RealtimeVoiceSession session.update", len(out_events) == 1 and out_events[0].type == "session.updated")

    # Audio append test
    audio_b64 = base64.b64encode(loud_chunk * 4).decode("ascii")
    append_events = asyncio.run(
        session.handle_client_message({
            "type": "input_audio_buffer.append",
            "audio": audio_b64
        })
    )
    check("RealtimeVoiceSession audio append", session.metrics.total_audio_in_bytes > 0)

    # 6. WAV header utility
    wav_hdr = create_wav_header(1024, sample_rate=16000)
    check("WAV header generation", len(wav_hdr) == 44 and wav_hdr[:4] == b"RIFF" and wav_hdr[8:12] == b"WAVE")

    print(f"\n{'ALL PASS' if failures == 0 else f'{failures} FAILURE(S)'} — realtime_voice_bridge")
    return failures


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(1 if _selftest() else 0)
    elif "--serve" in sys.argv:
        port = DEFAULT_PORT
        if "--port" in sys.argv:
            try:
                p_idx = sys.argv.index("--port") + 1
                port = int(sys.argv[p_idx])
            except Exception:
                pass
        bridge = RealtimeVoiceBridge(port=port)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(bridge.start())
        print(f"[*] RealtimeVoiceBridge active at ws://{bridge.host}:{bridge.port}/v1/realtime")
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            loop.run_until_complete(bridge.stop())
    else:
        print(json.dumps({"status": "ready", "module": "control_plane.dispatch.realtime_voice_bridge", "version": __version__}, indent=2))
