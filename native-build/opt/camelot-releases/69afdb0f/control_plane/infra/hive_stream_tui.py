# SPDX-License-Identifier: MIT

"""
Hive Stream TUI — Live multi-agent streaming display for CAMELOT-OS.

Shows concurrent output from 2-4 terminals simultaneously. Replaces the
static KnightMatrix in tui_app.py with live streamed panels.

Layout:
  ┌─────────────────────────────────────────────────────────────┐
  │  CAMELOT-OS HIVE IDE  v1.0  |  [terminal count]  [latency]  │
  ├───────────────────┬─────────────────────────────────────────┤
  │  KNIGHT MATRIX    │  STREAM A (sir_boris)                   │
  │  [health table]   │  [live output]                          │
  │                   ├─────────────────────────────────────────┤
  │                   │  STREAM B (sir_helio)                   │
  │                   │  [live output]                          │
  ├───────────────────┴─────────────────────────────────────────┤
  │  > prompt input                           [route] [target]  │
  └─────────────────────────────────────────────────────────────┘

Controls:
    Enter      — Send prompt (intent-routed)
    F2         — Direct: sir_boris (Claude)
    F3         — Direct: sir_helio (Gemini)
    F4         — Direct: sir_ghost (Local)
    F5         — Parallel: sir_boris + sir_helio
    Ctrl+C     — Quit
    Ctrl+L     — Clear streams
    Tab        — Cycle focus
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Static,
)

CAMELOT_HOME = Path(os.environ.get("CAMELOT_OS_HOME", Path.home() / "CAMELOT_OS")).resolve()

# ── Widgets ───────────────────────────────────────────────────────────────────

class KnightHealthTable(DataTable):
    """Live health status for all registered terminals."""

    COLUMNS = ("Knight", "Engine", "Status", "ms", "Cost")
    DEFAULT_CSS = """
    KnightHealthTable {
        height: 100%;
        border: solid $primary;
    }
    """

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.show_header = True
        for col in self.COLUMNS:
            self.add_column(col, key=col)
        self._refresh_data_sync()

    def _refresh_data_sync(self) -> None:
        try:
            from control_plane.switchboard import TERMINAL_REGISTRY
            self.clear()
            for t in TERMINAL_REGISTRY.values():
                status_style = {
                    "live":         "bold green",
                    "assumed_live": "green",
                    "dark":         "bold red",
                    "degraded":     "yellow",
                }.get(t.status, "dim")
                self.add_row(
                    t.id,
                    t.engine[:18],
                    Text(t.status, style=status_style),
                    f"{t.latency_ms:.0f}",
                    t.cost_tier,
                )
        except Exception as exc:
            self.add_row("error", str(exc)[:30], "dark", "0", "?")

    async def refresh_health(self) -> None:
        """Probe all terminals and update the table."""
        try:
            from control_plane.switchboard import Switchboard
            board = Switchboard()
            await board.probe_all()
        except Exception:
            pass
        self._refresh_data_sync()


class StreamPanel(RichLog):
    """A rich log panel that displays streamed agent output."""

    DEFAULT_CSS = """
    StreamPanel {
        border: solid $accent;
        height: 1fr;
        padding: 0 1;
        overflow-y: auto;
    }
    """

    def __init__(self, label: str, **kwargs):
        super().__init__(highlight=True, markup=True, **kwargs)
        self._label = label
        self.border_title = label

    def write_chunk(self, terminal_id: str, chunk: str) -> None:
        self.write(chunk, end="")

    def write_header(self, terminal_id: str, category: str = "") -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.write(
            Text.from_markup(
                f"\n[bold cyan]── {terminal_id} [{category}] @ {ts} ──[/bold cyan]\n"
            )
        )

    def write_error(self, msg: str) -> None:
        self.write(Text.from_markup(f"[bold red]{msg}[/bold red]"))

    def clear_stream(self) -> None:
        self.clear()


class RoutingBar(Static):
    """Shows last routing decision."""

    DEFAULT_CSS = """
    RoutingBar {
        background: $surface;
        color: $text-muted;
        height: 1;
        padding: 0 1;
    }
    """

    def set_route(self, terminal: str, category: str, confidence: float) -> None:
        self.update(
            f"[Route] → [bold]{terminal}[/bold]  "
            f"intent=[cyan]{category}[/cyan]  "
            f"conf={confidence:.2f}"
        )


# ── Main App ──────────────────────────────────────────────────────────────────

class HiveStreamTUI(App):
    """CAMELOT-OS Hive IDE — multi-stream live agent display."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #main-area {
        layout: horizontal;
        height: 1fr;
    }

    #left-panel {
        width: 32;
        layout: vertical;
        border-right: solid $primary-darken-2;
    }

    #left-label {
        height: 1;
        background: $primary-darken-2;
        color: $text;
        text-align: center;
        padding: 0 1;
    }

    #right-panel {
        width: 1fr;
        layout: vertical;
    }

    #streams-area {
        height: 1fr;
        layout: vertical;
    }

    #routing-bar {
        height: 1;
    }

    #input-row {
        height: 3;
        layout: horizontal;
        background: $surface-darken-1;
    }

    #prompt-input {
        width: 1fr;
    }

    #mode-label {
        width: 20;
        height: 3;
        content-align: center middle;
        background: $primary-darken-1;
        color: $text;
    }
    """

    BINDINGS = [
        Binding("ctrl+c",  "quit",            "Quit"),
        Binding("ctrl+l",  "clear_streams",    "Clear"),
        Binding("f2",      "target_boris",     "→Boris"),
        Binding("f3",      "target_helio",     "→Helio"),
        Binding("f4",      "target_ghost",     "→Ghost"),
        Binding("f5",      "parallel_mode",    "Parallel"),
        Binding("f6",      "refresh_health",   "Health"),
    ]

    _mode: reactive[str] = reactive("route")

    def __init__(self):
        super().__init__()
        self._active_tasks: list[asyncio.Task] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="main-area"):
            with Vertical(id="left-panel"):
                yield Label(" KNIGHT MATRIX", id="left-label")
                yield KnightHealthTable(id="health-table")
            with Vertical(id="right-panel"):
                with Vertical(id="streams-area"):
                    yield StreamPanel("Stream A — Primary", id="stream-a")
                    yield StreamPanel("Stream B — Secondary", id="stream-b")
                yield RoutingBar(id="routing-bar")
        with Horizontal(id="input-row"):
            yield Input(placeholder="Enter prompt...", id="prompt-input")
            yield Label(" ROUTE ", id="mode-label")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "CAMELOT-OS HIVE IDE"
        self.sub_title = "Universal Bridge — 13 Terminals"
        self.query_one("#prompt-input", Input).focus()
        self.set_interval(60, self._background_health_refresh)

    # ── Input handler ─────────────────────────────────────────────────────────

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        prompt = event.value.strip()
        if not prompt:
            return
        event.input.value = ""
        await self._dispatch_prompt(prompt)

    async def _dispatch_prompt(self, prompt: str) -> None:
        mode = self._mode

        # Cancel any running stream tasks
        for t in self._active_tasks:
            t.cancel()
        self._active_tasks.clear()

        stream_a = self.query_one("#stream-a", StreamPanel)
        stream_b = self.query_one("#stream-b", StreamPanel)

        if mode == "route":
            task = asyncio.create_task(self._stream_routed(prompt, stream_a))
            self._active_tasks.append(task)
        elif mode == "parallel":
            task = asyncio.create_task(
                self._stream_parallel(prompt, ["sir_boris", "sir_helio"], stream_a, stream_b)
            )
            self._active_tasks.append(task)
        else:
            # Direct terminal mode
            task = asyncio.create_task(self._stream_direct(prompt, mode, stream_a))
            self._active_tasks.append(task)

    async def _stream_routed(self, prompt: str, panel: StreamPanel) -> None:
        try:
            from control_plane.bifrost import Bifrost
            bf = Bifrost()
            terminal_id = "?"
            async for tid, chunk in bf.route_and_stream(prompt):
                if tid == "route":
                    # Parse routing info from the route chunk and update bar
                    self._update_routing_bar(chunk)
                    panel.write_header("routing...")
                else:
                    if tid != terminal_id:
                        terminal_id = tid
                        panel.write_header(tid, "routed")
                    panel.write_chunk(tid, chunk)
        except Exception as exc:
            panel.write_error(f"[ERROR] {exc}")

    async def _stream_direct(self, prompt: str, terminal_id: str, panel: StreamPanel) -> None:
        try:
            from control_plane.bifrost import Bifrost
            bf = Bifrost()
            panel.write_header(terminal_id, "direct")
            async for chunk in bf.stream(terminal_id, prompt):
                panel.write_chunk(terminal_id, chunk)
        except Exception as exc:
            panel.write_error(f"[ERROR] {exc}")

    async def _stream_parallel(
        self,
        prompt: str,
        terminal_ids: list[str],
        panel_a: StreamPanel,
        panel_b: StreamPanel,
    ) -> None:
        panels = [panel_a, panel_b]
        for i, tid in enumerate(terminal_ids[:2]):
            panels[i].write_header(tid, "parallel")

        try:
            from control_plane.bifrost import Bifrost
            bf = Bifrost()
            panel_map: dict[str, StreamPanel] = {
                terminal_ids[0]: panel_a,
                terminal_ids[1]: panel_b,
            }
            async for tid, chunk in bf.parallel_stream(terminal_ids, prompt):
                panel = panel_map.get(tid, panel_a)
                panel.write_chunk(tid, chunk)
        except Exception as exc:
            panel_a.write_error(f"[ERROR] {exc}")

    def _update_routing_bar(self, route_text: str) -> None:
        bar = self.query_one("#routing-bar", RoutingBar)
        bar.update(route_text.strip())

    # ── Mode actions ──────────────────────────────────────────────────────────

    def _set_mode(self, mode: str, label: str) -> None:
        self._mode = mode
        self.query_one("#mode-label", Label).update(f" {label} ")

    def action_target_boris(self) -> None:
        self._set_mode("sir_boris", "BORIS")

    def action_target_helio(self) -> None:
        self._set_mode("sir_helio", "HELIO")

    def action_target_ghost(self) -> None:
        self._set_mode("sir_ghost", "GHOST")

    def action_parallel_mode(self) -> None:
        self._set_mode("parallel", "PARALLEL")

    def action_clear_streams(self) -> None:
        for panel_id in ("#stream-a", "#stream-b"):
            try:
                self.query_one(panel_id, StreamPanel).clear_stream()
            except Exception:
                pass
        self._set_mode("route", "ROUTE")

    async def action_refresh_health(self) -> None:
        table = self.query_one("#health-table", KnightHealthTable)
        await table.refresh_health()

    async def _background_health_refresh(self) -> None:
        table = self.query_one("#health-table", KnightHealthTable)
        await table.refresh_health()

    # ── Mode label watcher ────────────────────────────────────────────────────

    def watch__mode(self, new_mode: str) -> None:
        label = {
            "route":    "ROUTE",
            "parallel": "PARALLEL",
        }.get(new_mode, new_mode.upper().replace("sir_", ""))
        try:
            self.query_one("#mode-label", Label).update(f" {label} ")
        except Exception:
            pass


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    app = HiveStreamTUI()
    app.run()


if __name__ == "__main__":
    main()
