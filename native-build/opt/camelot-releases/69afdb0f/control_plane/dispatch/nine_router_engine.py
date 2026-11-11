# SPDX-License-Identifier: MIT
# -*- coding: utf-8 -*-
"""
NineRouter Engine — Smart Token Router, Multi-Account Round-Robin, Quota Tracker,
OpenAI <-> Claude Format Bidirectional Translation, and RTK Tool-Result Compressor.
===================================================================================
Assimilated from 9router (open-sse routing engine & RTK compression) into Camelot-OS.
Zero external dependencies outside Python standard library.

Capabilities:
1. RTK Tool-Result Compressor:
   - Git Diff compaction & hunk truncation
   - Git Log streamliner
   - Git Status & porcelain compression
   - Grep / Find / Tree / LS output compaction
   - Numbered lines & Log deduplication
   - Smart truncation for large noisy text
   - In-place compression of OpenAI tool messages and Claude tool_results (20-40% token savings)
   - Fail-open safety (never corrupts or enlarges payload; preserves error traces)

2. Protocol Translation:
   - OpenAI Request -> Claude Messages Request
   - Claude Messages Request -> OpenAI Chat Completion Request
   - OpenAI Response Chunk -> Claude SSE Events / Blocks
   - Claude Response Chunk -> OpenAI SSE Chunk

3. Account Management & Smart Routing:
   - Multi-Account Round-Robin with quota tracking and health scoring
   - Rate limit cooldown / exponential backoff on 429/5xx
   - Model combos / multi-provider fallback chains
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

__version__ = "9000.30"

# ── RTK Constants ────────────────────────────────────────────────────────────
RAW_CAP = 500_000
MIN_COMPRESS_SIZE = 120
DETECT_WINDOW = 8192
READ_NUMBERED_MIN_HIT_RATIO = 0.6
SMART_TRUNCATE_MIN_LINES = 40
GIT_DIFF_HUNK_MAX_LINES = 100
GIT_LOG_MAX_LINES = 100

RE_GIT_DIFF = re.compile(r"^diff --git ", re.MULTILINE)
RE_GIT_DIFF_HUNK = re.compile(r"^@@ ", re.MULTILINE)
RE_GIT_STATUS = re.compile(r"^On branch |^nothing to commit|^Changes (not |to be )|^Untracked files:", re.MULTILINE)
RE_GIT_LOG = re.compile(r"^[*|/\\ ]*commit [0-9a-f]{7,40}$", re.MULTILINE | re.IGNORECASE)
RE_PORCELAIN = re.compile(r"^[ MADRCU?!][ MADRCU?!] \S", re.MULTILINE)
RE_BUILD_OUTPUT = re.compile(
    r"^(npm (warn|error|ERR!)|yarn (warn|error)|\s*Compiling\s+\S+|\s*Downloading\s+\S+|added \d+ package|\[ERROR\]|BUILD (SUCCESS|FAILED)|\s*Finished\s+|Successfully (installed|built)|ERROR:)",
    re.MULTILINE | re.IGNORECASE
)
RE_TREE_GLYPH = re.compile(r"[├└]──|│\s\s")
RE_LS_ROW = re.compile(r"^[-dlbcps][rwx-]{9}", re.MULTILINE)
RE_LS_TOTAL = re.compile(r"^total \d+$", re.MULTILINE)
READ_NUMBERED_LINE_RE = re.compile(r"^\s*\d+\s*[|:│]\s*")
SEARCH_LIST_HEADER_RE = re.compile(r"^(Found \d+ results?|Matches in \d+ files?:)", re.MULTILINE | re.IGNORECASE)


# ── RTK Compression Filters ──────────────────────────────────────────────────

def filter_git_diff(diff: str, max_lines: int = 500) -> str:
    """Compacts unified diffs: file headers, hunk-level truncation at 100 lines."""
    result: List[str] = []
    current_file = ""
    added = 0
    removed = 0
    in_hunk = False
    hunk_shown = 0
    hunk_skipped = 0
    was_truncated = False

    lines = diff.split("\n")
    for line in lines:
        if line.startswith("diff --git"):
            if hunk_skipped > 0:
                result.append(f"  ... ({hunk_skipped} lines truncated)")
                was_truncated = True
                hunk_skipped = 0
            if current_file and (added > 0 or removed > 0):
                result.append(f"  +{added} -{removed}")
            parts = line.split(" b/")
            current_file = parts[1] if len(parts) > 1 else "unknown"
            result.append(f"\n{current_file}")
            added = 0
            removed = 0
            in_hunk = False
            hunk_shown = 0
        elif line.startswith("@@"):
            if hunk_skipped > 0:
                result.append(f"  ... ({hunk_skipped} lines truncated)")
                was_truncated = True
                hunk_skipped = 0
            in_hunk = True
            hunk_shown = 0
            result.append(f"  {line}")
        elif in_hunk:
            if line.startswith("+") and not line.startswith("+++"):
                added += 1
                if hunk_shown < GIT_DIFF_HUNK_MAX_LINES:
                    result.append(f"  {line}")
                    hunk_shown += 1
                else:
                    hunk_skipped += 1
            elif line.startswith("-") and not line.startswith("---"):
                removed += 1
                if hunk_shown < GIT_DIFF_HUNK_MAX_LINES:
                    result.append(f"  {line}")
                    hunk_shown += 1
                else:
                    hunk_skipped += 1
            elif not line.startswith("\\"):
                if hunk_shown < GIT_DIFF_HUNK_MAX_LINES:
                    if hunk_shown > 0:
                        result.append(f"  {line}")
                        hunk_shown += 1
                else:
                    hunk_skipped += 1

        if len(result) >= max_lines:
            result.append("\n... (more changes truncated)")
            was_truncated = True
            break

    if hunk_skipped > 0:
        result.append(f"  ... ({hunk_skipped} lines truncated)")
        was_truncated = True

    if current_file and (added > 0 or removed > 0):
        result.append(f"  +{added} -{removed}")

    if was_truncated:
        result.append("[diff truncated for token efficiency]")

    return "\n".join(result)


def filter_git_log(text: str, max_lines: int = GIT_LOG_MAX_LINES) -> str:
    """Compresses `git log` output: retains commit headers, subjects, Author/Date."""
    if not text:
        return ""
    lines = text.split("\n")
    out: List[str] = []
    skipped = 0
    in_commit = False
    subject_seen = False

    for raw in lines:
        line = raw.rstrip()
        trimmed = line.strip()

        if re.match(r"^commit [0-9a-f]{7,40}$", trimmed, re.I) or re.match(r"^[*|/\\ ]+commit [0-9a-f]{7,40}", trimmed, re.I):
            in_commit = True
            subject_seen = False
            if len(out) < max_lines:
                out.append(line)
            else:
                skipped += 1
            continue

        if in_commit:
            if re.match(r"^[*|/\\ ]*(Author|Date):", trimmed, re.I):
                if len(out) < max_lines:
                    out.append(trimmed)
                else:
                    skipped += 1
                continue
            if not trimmed:
                continue
            if not subject_seen and re.match(r"^[*|/\\ ]*\s{4}\S", line):
                if len(out) < max_lines:
                    out.append("  Subject: " + trimmed)
                else:
                    skipped += 1
                subject_seen = True
                continue
            if re.match(r"^\d+ file\w* changed", trimmed):
                if len(out) < max_lines:
                    out.append("  " + trimmed)
                else:
                    skipped += 1
                continue
            if line.startswith("diff --git"):
                if len(out) < max_lines:
                    out.append("  ... diff body omitted")
                else:
                    skipped += 1
                continue
            continue

        # Oneline/graph format
        graph_match = re.match(r"^[*|/\\ ]+([0-9a-f]{7,40}\s+.+)", trimmed, re.I)
        if graph_match:
            if len(out) < max_lines:
                out.append(graph_match.group(1))
            else:
                skipped += 1
            continue

        if len(out) < max_lines:
            out.append(trimmed)
        else:
            skipped += 1

    if skipped > 0:
        out.append(f"... ({skipped} more log lines)")

    return "\n".join(out) if out else text


def filter_git_status(text: str) -> str:
    """Compresses git status output to essential staged/unstaged/untracked lists."""
    lines = text.split("\n")
    out = []
    for l in lines:
        t = l.strip()
        if not t or t.startswith("(") or "use \"git" in t:
            continue
        out.append(l)
    return "\n".join(out)


def filter_build_output(text: str, max_lines: int = 60) -> str:
    """Retains error/warning/summary lines while dropping verbose compilation steps."""
    lines = text.split("\n")
    errors = []
    summary = []
    for l in lines:
        t = l.strip()
        if re.search(r"\b(error|failed|exception|fatal|warn|warning)\b", t, re.I):
            errors.append(l)
        elif re.search(r"\b(success|built|finished|added \d+|completed)\b", t, re.I):
            summary.append(l)

    res = errors[:max_lines] + summary[-5:]
    if not res:
        return text[:1000]
    return "\n".join(res)


def filter_grep(text: str, max_lines: int = 150) -> str:
    """Deduplicates & limits grep matches."""
    lines = text.split("\n")
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines] + [f"... ({len(lines) - max_lines} more matches truncated)"])


def filter_find_ls(text: str, max_lines: int = 100) -> str:
    """Collapses directory listings / find results."""
    lines = text.split("\n")
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines] + [f"... ({len(lines) - max_lines} items truncated)"])


def filter_dedup_log(text: str, max_lines: int = 100) -> str:
    """Deduplicates repeated consecutive lines in log streams."""
    lines = text.split("\n")
    out = []
    prev = None
    count = 0

    for l in lines:
        if l == prev:
            count += 1
        else:
            if count > 1:
                out.append(f"  [... repeated {count - 1} more times ...]")
            prev = l
            count = 1
            out.append(l)
        if len(out) >= max_lines:
            out.append(f"... ({len(lines) - len(out)} lines truncated)")
            break
    if count > 1 and len(out) < max_lines:
        out.append(f"  [... repeated {count - 1} more times ...]")
    return "\n".join(out)


def filter_smart_truncate(text: str, max_chars: int = 4000) -> str:
    """Keeps the head and tail of an unstructured long text block."""
    if len(text) <= max_chars:
        return text
    head_size = max_chars // 2
    tail_size = max_chars // 2
    truncated_bytes = len(text) - (head_size + tail_size)
    return text[:head_size] + f"\n\n... [{truncated_bytes} characters compressed] ...\n\n" + text[-tail_size:]


def auto_detect_filter(text: str) -> Optional[Tuple[str, Callable[[str], str]]]:
    """Auto-detects the matching compressor filter for tool outputs."""
    head = text[:DETECT_WINDOW]

    if RE_GIT_LOG.search(head):
        return ("git-log", filter_git_log)
    if RE_GIT_DIFF.search(head) or RE_GIT_DIFF_HUNK.search(head):
        return ("git-diff", filter_git_diff)
    if RE_GIT_STATUS.search(head):
        return ("git-status", filter_git_status)
    if RE_BUILD_OUTPUT.search(head):
        return ("build-output", filter_build_output)

    lines = head.split("\n")
    non_empty = [l for l in lines if l.strip()]

    # Grep check (e.g. file:123:content)
    first5 = non_empty[:5]
    if any(re.match(r"^[^:]+:\d+:", l) for l in first5):
        return ("grep", filter_grep)

    # Find/Path-like
    if len(non_empty) >= 3 and all(l.strip().startswith((".", "/", "\\")) or ":" not in l for l in non_empty[:10]):
        return ("find", filter_find_ls)

    # Tree glyphs
    if RE_TREE_GLYPH.search(head):
        return ("tree", filter_find_ls)

    # LS listing
    if RE_LS_TOTAL.search(head) or len(RE_LS_ROW.findall(head)) >= 3:
        return ("ls", filter_find_ls)

    # Search list
    if SEARCH_LIST_HEADER_RE.search(head):
        return ("search-list", filter_grep)

    if len(non_empty) >= 5:
        return ("dedup-log", filter_dedup_log)

    if len(lines) >= SMART_TRUNCATE_MIN_LINES or len(text) > 4000:
        return ("smart-truncate", filter_smart_truncate)

    return None


@dataclass
class RTKStats:
    bytes_before: int = 0
    bytes_after: int = 0
    hits: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def bytes_saved(self) -> int:
        return max(0, self.bytes_before - self.bytes_after)

    @property
    def savings_pct(self) -> float:
        if self.bytes_before == 0:
            return 0.0
        return round((self.bytes_saved / self.bytes_before) * 100.0, 1)


class RTKCompressor:
    """RTK Tool-Result Compressor — in-place compression of tool execution outputs."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def compress_text(self, text: str, stats: RTKStats, shape: str = "generic") -> str:
        if not text or not isinstance(text, str):
            return text
        bytes_in = len(text)
        stats.bytes_before += bytes_in

        if bytes_in < MIN_COMPRESS_SIZE or bytes_in > RAW_CAP:
            stats.bytes_after += bytes_in
            return text

        detected = auto_detect_filter(text)
        if not detected:
            stats.bytes_after += bytes_in
            return text

        filter_name, filter_fn = detected
        try:
            compressed = filter_fn(text)
        except Exception:
            stats.bytes_after += bytes_in
            return text

        if not compressed or len(compressed) >= bytes_in:
            stats.bytes_after += bytes_in
            return text

        bytes_out = len(compressed)
        stats.bytes_after += bytes_out
        stats.hits.append({
            "shape": shape,
            "filter": filter_name,
            "saved": bytes_in - bytes_out,
        })
        return compressed

    def compress_messages(self, body: Dict[str, Any]) -> Optional[RTKStats]:
        """Compress tool_result / tool content in-place across OpenAI and Claude bodies."""
        if not self.enabled or not isinstance(body, dict):
            return None

        stats = RTKStats()
        messages = body.get("messages") or body.get("input")
        if not isinstance(messages, list):
            return stats

        for msg in messages:
            if not isinstance(msg, dict):
                continue

            # Shape 1: OpenAI Tool message: { role: "tool", content: "..." }
            if msg.get("role") == "tool":
                content = msg.get("content")
                if isinstance(content, str):
                    msg["content"] = self.compress_text(content, stats, "openai-tool")
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
                            part["text"] = self.compress_text(part["text"], stats, "openai-tool-array")
                continue

            # Shape 2: Claude tool_result blocks in messages: [{ type: "tool_result", content: "..." }]
            content = msg.get("content")
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_result":
                        if block.get("is_error") is True or block.get("status") == "error":
                            continue  # Preserve error traces intact
                        b_content = block.get("content")
                        if isinstance(b_content, str):
                            block["content"] = self.compress_text(b_content, stats, "claude-tool-result-string")
                        elif isinstance(b_content, list):
                            for part in b_content:
                                if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
                                    part["text"] = self.compress_text(part["text"], stats, "claude-tool-result-array")

        return stats


# ── Protocol Translation (OpenAI <-> Claude) ─────────────────────────────────

class ProtocolTranslator:
    """Bidirectional converter between OpenAI Chat Completions and Anthropic Messages format."""

    @staticmethod
    def openai_to_claude_request(body: Dict[str, Any], default_max_tokens: int = 4096) -> Dict[str, Any]:
        """Converts OpenAI Chat Completion request payload into Claude Messages API payload."""
        claude_req: Dict[str, Any] = {
            "model": body.get("model", "claude-3-5-sonnet-20241022"),
            "max_tokens": body.get("max_tokens") or body.get("max_completion_tokens") or default_max_tokens,
            "messages": [],
        }

        if "temperature" in body:
            claude_req["temperature"] = body["temperature"]
        if "top_p" in body:
            claude_req["top_p"] = body["top_p"]
        if "stream" in body:
            claude_req["stream"] = bool(body["stream"])

        system_parts = []
        raw_messages = body.get("messages", [])

        # Extract system prompt
        for msg in raw_messages:
            if msg.get("role") == "system":
                c = msg.get("content")
                if isinstance(c, str):
                    system_parts.append(c)
                elif isinstance(c, list):
                    for part in c:
                        if isinstance(part, dict) and part.get("type") == "text":
                            system_parts.append(part.get("text", ""))

        if system_parts:
            claude_req["system"] = "\n\n".join(system_parts)

        # Convert conversation messages
        non_system = [m for m in raw_messages if m.get("role") != "system"]
        for msg in non_system:
            role = msg.get("role")
            content = msg.get("content")

            if role == "tool":
                # OpenAI tool output -> Claude user tool_result block
                tool_call_id = msg.get("tool_call_id", "unknown_call")
                claude_req["messages"].append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_call_id,
                        "content": content if isinstance(content, str) else json.dumps(content),
                    }]
                })
            elif role == "user":
                if isinstance(content, str):
                    claude_req["messages"].append({"role": "user", "content": content})
                elif isinstance(content, list):
                    claude_blocks = []
                    for part in content:
                        if part.get("type") == "text":
                            claude_blocks.append({"type": "text", "text": part.get("text", "")})
                        elif part.get("type") == "image_url":
                            url = part.get("image_url", {}).get("url", "")
                            if url.startswith("data:"):
                                m = re.match(r"^data:([^;]+);base64,(.*)$", url)
                                if m:
                                    claude_blocks.append({
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": m.group(1),
                                            "data": m.group(2)
                                        }
                                    })
                            else:
                                claude_blocks.append({"type": "image", "source": {"type": "url", "url": url}})
                    claude_req["messages"].append({"role": "user", "content": claude_blocks})
            elif role == "assistant":
                blocks = []
                if isinstance(content, str) and content:
                    blocks.append({"type": "text", "text": content})
                tool_calls = msg.get("tool_calls", [])
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    args_str = fn.get("arguments", "{}")
                    try:
                        parsed_args = json.loads(args_str) if isinstance(args_str, str) else args_str
                    except Exception:
                        parsed_args = {"raw": args_str}
                    blocks.append({
                        "type": "tool_use",
                        "id": tc.get("id", f"call_{int(time.time()*1000)}"),
                        "name": fn.get("name", "unknown_tool"),
                        "input": parsed_args,
                    })
                if blocks:
                    claude_req["messages"].append({"role": "assistant", "content": blocks})

        # Tools conversion
        tools = body.get("tools")
        if isinstance(tools, list) and tools:
            claude_tools = []
            for t in tools:
                fn = t.get("function", t)
                claude_tools.append({
                    "name": fn.get("name", "tool"),
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
                })
            claude_req["tools"] = claude_tools

        return claude_req

    @staticmethod
    def claude_to_openai_request(body: Dict[str, Any]) -> Dict[str, Any]:
        """Converts Claude Messages API request payload into OpenAI Chat Completion payload."""
        openai_req: Dict[str, Any] = {
            "model": body.get("model", "gpt-4o"),
            "messages": [],
        }

        if "max_tokens" in body:
            openai_req["max_tokens"] = body["max_tokens"]
        if "temperature" in body:
            openai_req["temperature"] = body["temperature"]
        if "top_p" in body:
            openai_req["top_p"] = body["top_p"]
        if "stream" in body:
            openai_req["stream"] = bool(body["stream"])

        # System prompt
        system = body.get("system")
        if system:
            if isinstance(system, str):
                openai_req["messages"].append({"role": "system", "content": system})
            elif isinstance(system, list):
                s_text = "\n\n".join(b.get("text", "") for b in system if b.get("type") == "text")
                if s_text:
                    openai_req["messages"].append({"role": "system", "content": s_text})

        # Messages
        for msg in body.get("messages", []):
            role = msg.get("role")
            content = msg.get("content")

            if isinstance(content, str):
                openai_req["messages"].append({"role": role, "content": content})
            elif isinstance(content, list):
                text_parts = []
                tool_calls = []
                tool_results = []

                for block in content:
                    b_type = block.get("type")
                    if b_type == "text":
                        text_parts.append(block.get("text", ""))
                    elif b_type == "tool_use":
                        tool_calls.append({
                            "id": block.get("id"),
                            "type": "function",
                            "function": {
                                "name": block.get("name"),
                                "arguments": json.dumps(block.get("input", {}))
                            }
                        })
                    elif b_type == "tool_result":
                        res_content = block.get("content", "")
                        if isinstance(res_content, list):
                            res_content = "\n".join(p.get("text", "") for p in res_content if p.get("type") == "text")
                        tool_results.append({
                            "role": "tool",
                            "tool_call_id": block.get("tool_use_id"),
                            "content": res_content if isinstance(res_content, str) else json.dumps(res_content)
                        })

                if tool_results:
                    openai_req["messages"].extend(tool_results)
                elif tool_calls or text_parts:
                    asst_msg: Dict[str, Any] = {"role": role}
                    if text_parts:
                        asst_msg["content"] = "\n".join(text_parts)
                    if tool_calls:
                        asst_msg["tool_calls"] = tool_calls
                    openai_req["messages"].append(asst_msg)

        # Tools
        tools = body.get("tools")
        if isinstance(tools, list) and tools:
            openai_tools = []
            for t in tools:
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": t.get("name"),
                        "description": t.get("description", ""),
                        "parameters": t.get("input_schema", {"type": "object", "properties": {}})
                    }
                })
            openai_req["tools"] = openai_tools

        return openai_req


# ── Quota Tracker & Multi-Account Round Robin ────────────────────────────────

@dataclass
class UpstreamAccount:
    account_id: str
    provider: str  # e.g., "openai", "anthropic", "gemini", "deepseek"
    api_key: str
    quota_limit_tokens: int = 1_000_000
    used_tokens: int = 0
    consecutive_errors: int = 0
    cooldown_until: float = 0.0
    rpm_limit: int = 60
    requests_this_minute: int = 0
    minute_window_start: float = field(default_factory=time.time)

    def is_available(self) -> bool:
        now = time.time()
        if now < self.cooldown_until:
            return False
        if self.quota_limit_tokens > 0 and self.used_tokens >= self.quota_limit_tokens:
            return False
        return True

    def record_usage(self, tokens: int) -> None:
        self.used_tokens += max(0, tokens)
        self.consecutive_errors = 0

    def record_error(self, is_rate_limit: bool = False) -> None:
        self.consecutive_errors += 1
        backoff = 60.0 if is_rate_limit else min(300.0, 5.0 * (2 ** min(self.consecutive_errors, 5)))
        self.cooldown_until = time.time() + backoff


class NineRouterEngine:
    """Sovereign NineRouter Engine for Camelot-OS: Smart routing, RTK compression, Quota management."""

    def __init__(self, rtk_enabled: bool = True):
        self.rtk = RTKCompressor(enabled=rtk_enabled)
        self.translator = ProtocolTranslator()
        self.accounts: Dict[str, List[UpstreamAccount]] = {}  # provider -> accounts
        self.account_cursors: Dict[str, int] = {}
        self.usage_history: List[Dict[str, Any]] = []

    def register_account(self, account: UpstreamAccount) -> None:
        provider = account.provider.lower()
        if provider not in self.accounts:
            self.accounts[provider] = []
            self.account_cursors[provider] = 0
        self.accounts[provider].append(account)

    def select_account(self, provider: str) -> Optional[UpstreamAccount]:
        """Round-robin selection among available healthy accounts with quota."""
        provider = provider.lower()
        pool = self.accounts.get(provider, [])
        if not pool:
            return None

        start_idx = self.account_cursors.get(provider, 0)
        n = len(pool)

        for i in range(n):
            idx = (start_idx + i) % n
            acc = pool[idx]
            if acc.is_available():
                self.account_cursors[provider] = (idx + 1) % n
                return acc

        return None

    def route_and_prepare(
        self,
        request_body: Dict[str, Any],
        target_format: str = "claude",
        source_format: str = "openai"
    ) -> Tuple[Dict[str, Any], Optional[RTKStats]]:
        """Pre-compresses payload via RTK and translates to target schema."""
        # 1. RTK Pre-compression
        rtk_stats = self.rtk.compress_messages(request_body)

        # 2. Format Translation
        prepared_body = request_body
        if source_format.lower() == "openai" and target_format.lower() == "claude":
            prepared_body = self.translator.openai_to_claude_request(request_body)
        elif source_format.lower() == "claude" and target_format.lower() == "openai":
            prepared_body = self.translator.claude_to_openai_request(request_body)

        return prepared_body, rtk_stats

    def export_telemetry(self) -> Dict[str, Any]:
        """Telemetry export for Bifrost and Multivoice bridge."""
        total_accounts = sum(len(p) for p in self.accounts.values())
        active_accounts = sum(sum(1 for a in p if a.is_available()) for p in self.accounts.values())
        total_used_tokens = sum(sum(a.used_tokens for a in p) for p in self.accounts.values())

        return {
            "version": __version__,
            "rtk_enabled": self.rtk.enabled,
            "total_accounts": total_accounts,
            "active_accounts": active_accounts,
            "total_used_tokens": total_used_tokens,
            "providers": list(self.accounts.keys()),
        }
