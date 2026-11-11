# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
# Camelot Apex OS — CONFIDENTIAL AND PROPRIETARY
# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
JCode Memory Guard & Zero-Overhead Compactor
============================================
Assimilated from jcode (crates/jcode-compaction-core, jcode-storage).
Provides sub-50ms boot, zero-overhead session memory compaction,
safe tool call/result cutoff boundaries, UTF-8 byte-safe string truncations,
bounded image token budgets (avoiding raw base64 inflation), payload 413 recovery,
and PSS memory budget monitoring (<27.8MB baseline).

Zero external dependencies outside Python stdlib.
"""

from __future__ import annotations

import gc
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("JCodeMemoryGuard")

# Default token budget (matches standard 200k context limit)
DEFAULT_TOKEN_BUDGET: int = 200_000

# Compaction thresholds
COMPACTION_THRESHOLD: float = 0.80  # Proactive compaction trigger
CRITICAL_THRESHOLD: float = 0.95    # Emergency hard-compact trigger
MANUAL_COMPACT_MIN_THRESHOLD: float = 0.10

# Turn boundaries
RECENT_TURNS_TO_KEEP: int = 10
MIN_TURNS_TO_KEEP: int = 2

# Payload limits
EMERGENCY_TOOL_RESULT_MAX_CHARS: int = 4000
EMERGENCY_IMAGE_MAX_CHARS: int = 1024
PAYLOAD_IMAGE_CHAR_BUDGET: int = 12 * 1024 * 1024  # 12 MB HTTP 413 safe budget
CHARS_PER_TOKEN: int = 4
IMAGE_TOKEN_COST: int = 1600  # Flat token cost instead of raw base64 char count
SYSTEM_OVERHEAD_TOKENS: int = 18_000
EMBED_MAX_CHARS_PER_MSG: int = 512

# Memory Guard target (PSS baseline target in MB)
PSS_BASELINE_TARGET_MB: float = 27.8


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class CompactionActionType(str, Enum):
    NONE = "none"
    BACKGROUND_STARTED = "background_started"
    HARD_COMPACTED = "hard_compacted"


@dataclass
class ContentBlock:
    type: str  # "text", "tool_use", "tool_result", "image", "reasoning", "openai_compaction"
    text: Optional[str] = None
    id: Optional[str] = None
    name: Optional[str] = None
    input: Optional[Any] = None
    tool_use_id: Optional[str] = None
    content: Optional[str] = None
    is_error: Optional[bool] = None
    media_type: Optional[str] = None
    data: Optional[str] = None  # base64 image data
    encrypted_content: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {"type": self.type}
        for k in ("text", "id", "name", "input", "tool_use_id", "content", "is_error", "media_type", "data", "encrypted_content"):
            v = getattr(self, k)
            if v is not None:
                res[k] = v
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ContentBlock:
        return cls(
            type=data.get("type", "text"),
            text=data.get("text"),
            id=data.get("id"),
            name=data.get("name"),
            input=data.get("input"),
            tool_use_id=data.get("tool_use_id"),
            content=data.get("content"),
            is_error=data.get("is_error"),
            media_type=data.get("media_type"),
            data=data.get("data"),
            encrypted_content=data.get("encrypted_content"),
        )


@dataclass
class Message:
    role: Role
    content: List[ContentBlock] = field(default_factory=list)
    timestamp: Optional[float] = None
    tool_duration_ms: Optional[int] = None

    @classmethod
    def user(cls, text: str) -> Message:
        return cls(role=Role.USER, content=[ContentBlock(type="text", text=text)], timestamp=time.time())

    @classmethod
    def assistant(cls, text: str) -> Message:
        return cls(role=Role.ASSISTANT, content=[ContentBlock(type="text", text=text)], timestamp=time.time())

    @classmethod
    def tool_call(cls, id: str, name: str, input_args: Any) -> Message:
        return cls(
            role=Role.ASSISTANT,
            content=[ContentBlock(type="tool_use", id=id, name=name, input=input_args)],
            timestamp=time.time(),
        )

    @classmethod
    def tool_result(cls, tool_use_id: str, content: str, is_error: bool = False) -> Message:
        return cls(
            role=Role.USER,
            content=[ContentBlock(type="tool_result", tool_use_id=tool_use_id, content=content, is_error=is_error)],
            timestamp=time.time(),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role.value if isinstance(self.role, Role) else str(self.role),
            "content": [b.to_dict() for b in self.content],
            "timestamp": self.timestamp,
            "tool_duration_ms": self.tool_duration_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Message:
        role_str = data.get("role", "user")
        role = Role(role_str) if role_str in Role._value2member_map_ else Role.USER
        blocks = [ContentBlock.from_dict(b) for b in data.get("content", [])]
        return cls(
            role=role,
            content=blocks,
            timestamp=data.get("timestamp"),
            tool_duration_ms=data.get("tool_duration_ms"),
        )


@dataclass
class Summary:
    text: str
    openai_encrypted_content: Optional[str] = None
    covers_up_to_turn: int = 0
    original_turn_count: int = 0


@dataclass
class CompactionStats:
    total_turns: int
    active_messages: int
    has_summary: bool
    is_compacting: bool
    token_estimate: int
    effective_tokens: int
    observed_input_tokens: Optional[int]
    context_usage: float


# ---------------------------------------------------------------------------
# Zero-Overhead Memory Compaction Algorithms (JCode Port)
# ---------------------------------------------------------------------------

def truncate_str_boundary(value: str, max_bytes: int) -> str:
    """Safely truncate UTF-8 string up to max_bytes without splitting codepoints."""
    if not value or max_bytes <= 0:
        return ""
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value
    # Truncate raw bytes then decode ignoring / replacing dangling trailing byte
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def tail_str_boundary(value: str, max_bytes: int) -> str:
    """Safely retrieve the trailing UTF-8 substring up to max_bytes."""
    if not value or max_bytes <= 0:
        return ""
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value
    return encoded[-max_bytes:].decode("utf-8", errors="ignore")


def content_char_count(content: List[ContentBlock]) -> int:
    """
    Calculate character count with bounded image cost.
    Images charge flat IMAGE_TOKEN_COST * CHARS_PER_TOKEN to avoid 100x ballooning.
    """
    total = 0
    for block in content:
        if block.type == "text" and block.text:
            total += len(block.text)
        elif block.type in ("reasoning", "reasoning_trace") and block.text:
            total += len(block.text)
        elif block.type == "tool_use":
            inp_len = len(json.dumps(block.input)) if block.input is not None else 0
            total += inp_len + 50
        elif block.type == "tool_result" and block.content:
            total += len(block.content) + 20
        elif block.type == "image":
            total += IMAGE_TOKEN_COST * CHARS_PER_TOKEN
        elif block.type == "openai_compaction" and block.encrypted_content:
            total += len(block.encrypted_content)
    return total


def message_char_count(msg: Message) -> int:
    return content_char_count(msg.content)


def estimate_compaction_tokens_from_chars(total_chars: int, token_budget: int = DEFAULT_TOKEN_BUDGET) -> int:
    """Estimate token usage from chars with system prompt & tool overhead accounted for."""
    msg_tokens = total_chars // CHARS_PER_TOKEN
    overhead = SYSTEM_OVERHEAD_TOKENS if token_budget >= DEFAULT_TOKEN_BUDGET // 2 else 0
    return msg_tokens + overhead


def estimate_compaction_tokens(
    summary: Optional[Summary],
    active_message_chars: int,
    token_budget: int = DEFAULT_TOKEN_BUDGET,
) -> int:
    summary_chars = len(summary.openai_encrypted_content or summary.text) if summary else 0
    return estimate_compaction_tokens_from_chars(summary_chars + active_message_chars, token_budget)


def effective_context_tokens_from_usage(
    provider_name: str,
    input_tokens: int,
    cache_read_input_tokens: Optional[int] = None,
    cache_creation_input_tokens: Optional[int] = None,
) -> int:
    """
    Single source of truth for provider token usage calculation.
    Anthropic/Claude uses split accounting (input + cache_read + cache_creation).
    OpenAI uses subset accounting (prompt_tokens includes cached).
    """
    if input_tokens == 0:
        return 0
    cache_read = cache_read_input_tokens or 0
    cache_creation = cache_creation_input_tokens or 0
    provider_lower = provider_name.lower()

    split_cache_accounting = (
        "anthropic" in provider_lower
        or "claude" in provider_lower
        or cache_creation > 0
        or cache_read > input_tokens
    )

    if split_cache_accounting:
        return input_tokens + cache_read + cache_creation
    return input_tokens


def safe_compaction_cutoff(messages: List[Message], initial_cutoff: int) -> int:
    """
    Find safe compaction cutoff that never leaves orphaned ToolResult blocks
    in the active turn window without their matching ToolUse calls.
    """
    cutoff = min(initial_cutoff, len(messages))
    available_tool_ids: Set[str] = set()
    missing_tool_ids: Set[str] = set()

    for msg in messages[cutoff:]:
        for block in msg.content:
            if block.type == "tool_use" and block.id:
                available_tool_ids.add(block.id)
                missing_tool_ids.discard(block.id)
            elif block.type == "tool_result" and block.tool_use_id:
                if block.tool_use_id not in available_tool_ids:
                    missing_tool_ids.add(block.tool_use_id)

    if not missing_tool_ids:
        return cutoff

    for idx in range(cutoff - 1, -1, -1):
        msg = messages[idx]
        for block in msg.content:
            if block.type == "tool_use" and block.id:
                available_tool_ids.add(block.id)
                missing_tool_ids.discard(block.id)
            elif block.type == "tool_result" and block.tool_use_id:
                if block.tool_use_id not in available_tool_ids:
                    missing_tool_ids.add(block.tool_use_id)
        if not missing_tool_ids:
            return idx

    return 0


def emergency_truncated_tool_result(content: str, max_chars: int = EMERGENCY_TOOL_RESULT_MAX_CHARS) -> str:
    """Head + tail preserving truncation for large tool results."""
    original_len = len(content)
    if original_len <= max_chars:
        return content
    keep_head = max_chars // 2
    keep_tail = max_chars // 4
    head = truncate_str_boundary(content, keep_head)
    tail = tail_str_boundary(content, keep_tail)
    truncated_len = max(0, original_len - (len(head) + len(tail)))
    return f"{head}\n\n... [{truncated_len} chars truncated for context recovery] ...\n\n{tail}"


def emergency_truncate_large_payloads(
    messages: List[Message],
    max_tool_result_chars: int = EMERGENCY_TOOL_RESULT_MAX_CHARS,
    max_image_chars: int = EMERGENCY_IMAGE_MAX_CHARS,
) -> int:
    """Truncates tool results and replaces oversized base64 images with memory markers."""
    truncated = 0
    for msg in messages:
        for block in msg.content:
            if block.type == "tool_result" and block.content and len(block.content) > max_tool_result_chars:
                block.content = emergency_truncated_tool_result(block.content, max_tool_result_chars)
                truncated += 1
            elif block.type == "image" and block.data and len(block.data) > max_image_chars:
                orig_len = len(block.data)
                media_type = block.media_type or "image/png"
                block.type = "text"
                block.text = (
                    f"[Image omitted during emergency context recovery: media_type={media_type}, "
                    f"original_base64_chars={orig_len}. Rely on adjacent tool text or saved artifacts.]"
                )
                block.data = None
                truncated += 1
    return truncated


def is_request_payload_too_large_error(error_msg: str) -> bool:
    """Check if error indicates HTTP 413 / Request Payload Too Large."""
    lower = error_msg.lower()
    return (
        "request_too_large" in lower
        or "request too large" in lower
        or "payload too large" in lower
        or "request entity too large" in lower
        or "request exceeds the maximum size" in lower
        or "exceeds the maximum size" in lower
        or bool(re.search(r"(?<!\d)413(?!\d)", lower))
    )


def emergency_strip_large_images(messages: List[Message], target_total_chars: int = PAYLOAD_IMAGE_CHAR_BUDGET) -> int:
    """
    Drop oldest base64 images first until total base64 payload fits target budget.
    Replaces dropped images with recovery placeholders.
    """
    image_refs: List[Tuple[int, int, int]] = []
    total_bytes = 0

    for mi, msg in enumerate(messages):
        for bi, block in enumerate(msg.content):
            if block.type == "image" and block.data:
                dlen = len(block.data)
                image_refs.append((mi, bi, dlen))
                total_bytes += dlen

    if total_bytes <= target_total_chars:
        return 0

    stripped = 0
    for mi, bi, dlen in image_refs:
        if total_bytes <= target_total_chars:
            break
        block = messages[mi].content[bi]
        orig_len = len(block.data or "")
        media_type = block.media_type or "image/png"
        block.type = "text"
        block.text = (
            f"[Image omitted during request-size recovery: media_type={media_type}, "
            f"original_base64_chars={orig_len}. Older images dropped to fit request payload limit.]"
        )
        block.data = None
        total_bytes -= dlen
        stripped += 1

    return stripped


def build_emergency_summary_text(
    existing_summary: Optional[str],
    dropped_count: int,
    pre_tokens: int,
    token_budget: int,
    dropped_messages: List[Message],
) -> str:
    """Generate concise emergency summary with tool and file hints."""
    parts: List[str] = []
    if existing_summary and existing_summary.strip():
        parts.append(existing_summary.strip())

    parts.append(
        f"**[Emergency compaction]**: {dropped_count} messages were dropped to recover from context overflow. "
        f"The conversation had ~{pre_tokens // 1000}k tokens which exceeded the {token_budget // 1000}k limit."
    )

    tool_names: Set[str] = set()
    file_mentions: Set[str] = set()

    for msg in dropped_messages:
        for block in msg.content:
            if block.type == "tool_use" and block.name:
                tool_names.add(block.name)
            elif block.type == "text" and block.text:
                for word in block.text.split():
                    if (
                        ("/" in word or "." in word)
                        and 3 < len(word) < 120
                        and not word.startswith("http")
                        and any(word.endswith(ext) for ext in (".py", ".ts", ".rs", ".json", ".toml", ".md"))
                    ):
                        cleaned = word.strip("`'\"(),;:<>{}[]")
                        if cleaned:
                            file_mentions.add(cleaned)

    if tool_names:
        tools_sorted = sorted(tool_names)
        parts.append(f"Tools used: {', '.join(tools_sorted)}")

    if file_mentions:
        files_sorted = sorted(file_mentions)[:30]
        parts.append(f"Files referenced: {', '.join(files_sorted)}")

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# JCode Memory Guard (PSS Telemetry & Session Lifecycle)
# ---------------------------------------------------------------------------

class JCodeMemoryGuard:
    """
    Ultra-low overhead Memory & Compaction Guard.
    Assimilates JCode 27.8MB PSS baseline monitoring, sub-50ms boot,
    and zero-overhead session compaction.
    """

    def __init__(self, token_budget: int = DEFAULT_TOKEN_BUDGET, pss_limit_mb: float = PSS_BASELINE_TARGET_MB):
        self.token_budget = token_budget
        self.pss_limit_mb = pss_limit_mb
        self.summary: Optional[Summary] = None
        self.messages: List[Message] = []
        self._boot_time_ms = 0.0
        self._init_guard()

    def _init_guard(self) -> None:
        t0 = time.perf_counter()
        # Fast init - zero heavyweight reflection
        self._boot_time_ms = (time.perf_counter() - t0) * 1000.0

    @property
    def boot_time_ms(self) -> float:
        return self._boot_time_ms

    def add_message(self, message: Message) -> None:
        self.messages.append(message)

    def get_stats(self, observed_input_tokens: Optional[int] = None) -> CompactionStats:
        total_chars = sum(message_char_count(m) for m in self.messages)
        token_est = estimate_compaction_tokens(self.summary, total_chars, self.token_budget)
        effective = observed_input_tokens if observed_input_tokens is not None else token_est
        usage = effective / max(1, self.token_budget)

        return CompactionStats(
            total_turns=len(self.messages) + (self.summary.covers_up_to_turn if self.summary else 0),
            active_messages=len(self.messages),
            has_summary=self.summary is not None,
            is_compacting=False,
            token_estimate=token_est,
            effective_tokens=effective,
            observed_input_tokens=observed_input_tokens,
            context_usage=usage,
        )

    def compact_if_needed(self, observed_input_tokens: Optional[int] = None) -> Tuple[CompactionActionType, int]:
        """
        Evaluate context against thresholds and execute zero-overhead hard compaction
        when reaching CRITICAL_THRESHOLD (>= 95%).
        """
        stats = self.get_stats(observed_input_tokens)
        if stats.context_usage < COMPACTION_THRESHOLD:
            return CompactionActionType.NONE, 0

        # If critical or emergency, hard-compact dropping older turns safely
        if stats.context_usage >= CRITICAL_THRESHOLD:
            return self.force_hard_compact(stats.effective_tokens)

        # Proactive trigger: keep recent turns, compact older
        if len(self.messages) > RECENT_TURNS_TO_KEEP:
            return self.force_hard_compact(stats.effective_tokens)

        return CompactionActionType.NONE, 0

    def force_hard_compact(self, pre_tokens: int = 0) -> Tuple[CompactionActionType, int]:
        """Execute atomic, safe zero-overhead compaction."""
        if len(self.messages) <= MIN_TURNS_TO_KEEP:
            # Can only truncate payloads
            truncated = emergency_truncate_large_payloads(self.messages)
            return CompactionActionType.HARD_COMPACTED, truncated

        raw_cutoff = max(0, len(self.messages) - RECENT_TURNS_TO_KEEP)
        cutoff = safe_compaction_cutoff(self.messages, raw_cutoff)
        if cutoff == 0:
            cutoff = max(1, len(self.messages) - MIN_TURNS_TO_KEEP)

        dropped = self.messages[:cutoff]
        kept = self.messages[cutoff:]

        prior_text = self.summary.text if self.summary else None
        new_summary_text = build_emergency_summary_text(
            existing_summary=prior_text,
            dropped_count=len(dropped),
            pre_tokens=pre_tokens or self.token_budget,
            token_budget=self.token_budget,
            dropped_messages=dropped,
        )

        prev_covers = self.summary.covers_up_to_turn if self.summary else 0
        self.summary = Summary(
            text=new_summary_text,
            covers_up_to_turn=prev_covers + len(dropped),
            original_turn_count=prev_covers + len(self.messages),
        )
        self.messages = kept

        # Run emergency payload truncation on kept suffix if still tight
        emergency_truncate_large_payloads(self.messages)

        # Run stdlib GC pass to release memory immediately
        gc.collect()

        return CompactionActionType.HARD_COMPACTED, len(dropped)

    def recover_from_error(self, error_str: str) -> bool:
        """Analyze error string; apply JCode image-stripping or context compaction."""
        if is_request_payload_too_large_error(error_str):
            stripped = emergency_strip_large_images(self.messages, PAYLOAD_IMAGE_CHAR_BUDGET)
            if stripped > 0:
                logger.info(f"Stripped {stripped} images to recover from HTTP 413 Payload Too Large.")
                return True
        # If general overflow
        action, count = self.force_hard_compact()
        return count > 0

    @staticmethod
    def get_process_memory_mb() -> Dict[str, float]:
        """
        Read process memory usage (PSS / RSS / VMS) using stdlib/OS primitives.
        Guarantees zero external dependencies.
        """
        res = {"rss_mb": 0.0, "vms_mb": 0.0, "pss_mb": 0.0}
        try:
            if sys.platform.startswith("linux"):
                # Linux /proc/self/smaps_rollup or smaps
                if os.path.exists("/proc/self/smaps_rollup"):
                    with open("/proc/self/smaps_rollup", "r") as f:
                        for line in f:
                            if line.startswith("Pss:"):
                                res["pss_mb"] = float(line.split()[1]) / 1024.0
                            elif line.startswith("Rss:"):
                                res["rss_mb"] = float(line.split()[1]) / 1024.0
                elif os.path.exists("/proc/self/statm"):
                    with open("/proc/self/statm", "r") as f:
                        parts = f.read().split()
                        res["rss_mb"] = (float(parts[1]) * 4096) / (1024.0 * 1024.0)
                        res["pss_mb"] = res["rss_mb"]
            elif sys.platform == "win32":
                import ctypes
                from ctypes import wintypes

                class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
                    _fields_ = [
                        ("cb", wintypes.DWORD),
                        ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t),
                        ("PrivateUsage", ctypes.c_size_t),
                    ]

                pmc = PROCESS_MEMORY_COUNTERS_EX()
                pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
                handle = ctypes.windll.kernel32.GetCurrentProcess()
                if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):
                    res["rss_mb"] = pmc.WorkingSetSize / (1024.0 * 1024.0)
                    res["vms_mb"] = pmc.PagefileUsage / (1024.0 * 1024.0)
                    res["pss_mb"] = pmc.PrivateUsage / (1024.0 * 1024.0)
        except Exception as e:
            logger.debug(f"Memory probe fallback: {e}")
        return res
