# Copyright (c) 2026 Invisioned Marketing inc. All Rights Reserved.
"""
Camelot-OS Ultimate Lattice HUD v3.0
=====================================
The Comprehensive Master Command Center.
Integrates 22-Knight Swarm, OmniRoute Telemetry, and Workflow Navigation.
"""


from rich.panel import Panel
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Grid, Vertical
from textual.reactive import reactive
from textual.widgets import DataTable, Footer, Header, Input, Label, Log, Markdown, Static, TabbedContent, TabPane, Tree


class KnightMatrix(DataTable):
    """Real-time grid showing 22 Knights and their OmniRoute providers."""
    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.add_columns("Knight ID", "Engine / Provider", "Status", "Load")
        self.add_rows([
            ("sir_boris", "Kiro (Claude 3.5)", "ORCHESTRATING", "12%"),
            ("sir_alex", "Claude Opus", "COGNITIVE_GOVERNOR", "9%"),
            ("sir_helio", "LongCat (Flash)", "CONTEXT_SYNC", "5%"),
            ("sir_syntax", "Qoder (DeepSeek)", "CODE_GEN", "45%"),
            ("sir_forge", "Groq (Llama3)", "KINETIC_STRIKE", "88%"),
            ("lady_apis", "Scaleway (Qwen)", "FORAGING", "22%"),
            ("sir_link", "OmniRoute (A2A)", "HANDSHAKING", "10%"),
            ("sir_gareth", "Treasurer (Free)", "BUDGET_GUARD", "0%")
        ])

class WorkflowNavigator(Tree):
    """Searchable tree of Runes, Phials, and Cartridges."""
    def on_mount(self) -> None:
        self.root.expand()
        runes = self.root.add("📜 RUNIC COMMANDS", expand=True)
        runes.add_leaf("//PLAN : Architect")
        runes.add_leaf("//FORGE: Execute")
        runes.add_leaf("//FLEET: Swarm")
        
        cartridges = self.root.add("🧪 CARTRIDGES", expand=True)
        cartridges.add_leaf("AETHER_ROUTING")
        cartridges.add_leaf("KINETIC_STACK")
        
        phials = self.root.add("⚗️ PHIALS", expand=True)
        phials.add_leaf("shopify_ingest.exe")
        phials.add_leaf("vault_audit.exe")

class OmniTelemetry(Static):
    """Live Counter for Capital Ceiling and Provider Health."""
    spent = reactive(0.00)
    health = reactive(100)

    def render(self) -> Panel:
        return Panel(
            Text.assemble(
                (" [CAPITAL: $", "white"), (f"{self.spent:.2f}", "bold green"), (" SPENT] ", "white"),
                (f" [O-ROUTE: {self.health}% HEALTH] ", "bold cyan")
            ),
            title="[bold yellow]OmniRoute Telemetry[/]",
            border_style="yellow"
        )

class SovereignApp(App):
    """The Ultimate Master Command Center for Camelot-OS."""
    CSS = """
    Screen {
        background: #00081a;
    }
    #top_grid {
        height: 12;
        grid-size: 3 1;
        margin: 1 0;
    }
    #main_grid {
        grid-size: 2 1;
        height: 1fr;
    }
    .panel {
        border: double cyan;
        background: #00122e;
        padding: 1;
    }
    .label {
        color: cyan;
        text-style: bold;
    }
    #intent_box {
        dock: bottom;
        height: 3;
        border: tall magenta;
    }
    """

    BINDINGS = [
        ("f1", "switch_tab('control')", "Control"),
        ("f2", "switch_tab('ledger')", "Ledger"),
        ("f3", "switch_tab('swarm')", "Swarm"),
        ("ctrl+space", "command_palette", "Command Palette"),
        ("q", "quit", "Exit Spire")
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        
        with Grid(id="top_grid"):
            yield Static(Panel("[bold cyan]L7: ETHEREAL[/]\nStatus: RADIANT\nEngine: APEE v6.5", border_style="cyan"))
            yield OmniTelemetry()
            yield Static(Panel("[bold green]L2: KINETIC[/]\nStatus: PURE\nEngine: Lukas Omega", border_style="green"))

        with Grid(id="main_grid"):
            with Vertical(classes="panel"):
                yield Label("⚔️ KNIGHT MATRIX", classes="label")
                yield KnightMatrix()
            
            with TabbedContent():
                with TabPane("The S.I.T. Loop", id="control"):
                    yield Label("🌀 NEURAL STREAM", classes="label")
                    yield Log(id="sit_log")
                with TabPane("Workflow Nav", id="workflows"):
                    yield WorkflowNavigator("Sovereign Assets")
                with TabPane("Swarm Horde", id="swarm"):
                    yield Log(id="swarm_log")
                with TabPane("Governance", id="ledger"):
                    yield Markdown("# Titanium Law Enforcement\n1. Kinetic Purity\n2. Ledger is Law\n3. Iron Gate HITL")

        yield Input(placeholder="Input Sovereign Intent (e.g., //PLAN build phial)...", id="intent_box")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Camelot-OS | OBSIDIAN SPIRE v3.0"
        self.query_one("#sit_log").write("SYSTEM_BOOT: Singularity Lattice v400.1.0... RADIANT")
        self.query_one("#swarm_log").write("[19:30] [L5] Paladin: Swarm idle. Awaiting strike.")

    def action_switch_tab(self, tab_id: str) -> None:
        self.query_one(TabbedContent).active_pane = tab_id

if __name__ == "__main__":
    app = SovereignApp()
    app.run()
