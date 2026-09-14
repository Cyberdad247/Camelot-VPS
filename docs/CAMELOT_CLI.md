# Camelot Sovereign Terminal

The Camelot CLI mirrors the Battle World operating model for terminal-first usage.

## Start the interactive shell

```bash
npm run camelot
```

The shell keeps a small local operational state file at:

```text
~/.camelot/command-center-state.json
```

Override it with `CAMELOT_CLI_STATE=/path/to/state.json` when needed.

## One-shot commands

```bash
npm run camelot -- status
npm run camelot -- mode lockdown
npm run camelot -- scene list
npm run camelot -- scene go defense
npm run camelot -- scene explain ouroboros
npm run camelot -- threat filter prompt-injection
npm run camelot -- defense list
npm run camelot -- defense disarm sandbox
npm run camelot -- defense arm sandbox
npm run camelot -- defense all on
npm run camelot -- auto on
npm run camelot -- counter deploy
npm run camelot -- command "preserve current tactical state"
npm run camelot -- log 20
```

## Bifrost from the terminal

The CLI uses the existing governed Bifrost gateway. It does not expose an arbitrary proxy.

Gateway selection order:

1. `BIFROST_URL`
2. `VITE_BIFROST_URL`
3. `http://127.0.0.1:4188`

Examples:

```bash
npm run camelot -- bifrost status
npm run camelot -- bifrost probe multivoice
npm run camelot -- bifrost probe godseye
npm run camelot -- bifrost probe worldmonitor
npm run camelot -- bifrost cross multivoice bridge "open governed voice handoff"
npm run camelot -- bifrost cross godseye handoff "open spatial intelligence surface"
npm run camelot -- bifrost cross worldmonitor mcp "discover available intelligence capabilities"
```

A crossing is validated by the Bifrost server's allowlisted realm and transport policy. Some destinations return an explicit handoff URL rather than performing a remote mutation.

## Command families

### System

- `status`
- `mode nominal|battle|lockdown`
- `reset`
- `help`
- `exit`

### World Director

- `scene list`
- `scene go <id|00..08>`
- `scene explain [id]`

### Threat Matrix

- `threat list`
- `threat filter <type>`

Supported filters:

- `ddos`
- `prompt-injection`
- `data-exfiltration`
- `ai-adversary`
- `reconnaissance`

### Defense Grid

- `defense list`
- `defense arm <id>`
- `defense disarm <id>`
- `defense toggle <id>`
- `defense all on|off`

Defense IDs:

- `memcastle`
- `context`
- `firewall`
- `inference`
- `sandbox`
- `vfs`
- `physical`

### Countermeasures

- `auto on|off`
- `counter deploy`

### Command Deck

- `command <text...>`
- `log [count]`

### Bifrost

- `bifrost status`
- `bifrost probe <multivoice|godseye|worldmonitor>`
- `bifrost cross <realm> <transport> <intent...>`

Supported crossing transports are `mcp`, `bridge`, `tailscale`, `handoff`, and `auto`. The destination adapter remains authoritative about what is actually allowed.

## Validation

```bash
npm run camelot:check
npm run camelot:status
```

`camelot:check` performs a Node syntax check. The CLI is intentionally implemented with Node built-ins and has no added command-framework dependency.

## Current boundary

The CLI and browser Battle World share the same conceptual operating model, but they are not yet a real-time synchronized state bus. CLI state is persisted locally for terminal sessions; browser Battle Mode state remains React-owned. A future authenticated state service can unify them without changing the command grammar.
