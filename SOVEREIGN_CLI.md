# Camelot-OS Sovereign Terminal

Camelot now exposes the same operator vocabulary through two surfaces:

1. the native Node CLI (`npm run camelot`)
2. the browser `SovereignTerminalCommandCenter`

The browser workstation is mounted from `src/main.tsx` and combines:

- World Director subsystem navigation
- Battle Mode state controls
- live threat and readiness metrics
- seven defense layer controls
- threat filtering and countermeasure deployment
- an interactive terminal with command history and quick commands
- governed Bifrost realm probes and crossings
- responsive mobile tabs for Terminal / Operations / Bifrost

## Browser command grammar

The in-app terminal supports the same core grammar as the Node CLI:

```text
status
mode nominal|battle|lockdown
scene list
scene go <id|00..08>
scene explain
threat list
threat filter <type>
defense list
defense arm|disarm|toggle <id>
defense all on|off
auto on|off
counter deploy
bifrost status
bifrost probe multivoice|godseye|worldmonitor
bifrost cross multivoice|godseye|worldmonitor
clear
help
```

Keyboard behavior:

- `Ctrl/Cmd + K` focuses the browser command line
- `Arrow Up / Arrow Down` walks command history
- Enter executes the active command

## Native CLI

Launch the terminal REPL:

```bash
npm run camelot
```

One-shot usage:

```bash
npm run camelot -- status
npm run camelot -- mode lockdown
npm run camelot -- scene go defense
npm run camelot -- defense list
npm run camelot -- counter deploy
```

Validate the Node entrypoint:

```bash
npm run camelot:check
```

## Bifrost boundary

Both browser and CLI operate against the governed Bifrost gateway. No arbitrary proxy endpoint is added. Browser crossing requests use the existing `/api/bifrost/crossing` contract with allowlisted destinations and explicit transports.

## State boundary

The browser workstation owns its current React state. The native CLI persists its state to `~/.camelot/command-center-state.json` by default. They intentionally do not pretend to be synchronized yet. A future authenticated Camelot state service can unify them without changing the operator command grammar.
