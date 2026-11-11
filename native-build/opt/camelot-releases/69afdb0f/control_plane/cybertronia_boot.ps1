# SPDX-License-Identifier: MIT

# Cybertronia server supervisor.
# Keeps the Go daemons alive (restart-on-crash) so cybertronia is an always-on
# server. Launched at logon by the "CybertroniaServer" scheduled task.
#   - go_router        :8077  (SSE command router; public via Tailscale Funnel)
#   - bifrost_sidecar  :8011  (Bifrost bridge -> upstream :8001)
# This script never exits; it polls every 5s and relaunches any daemon that died.

$ErrorActionPreference = "Continue"
$root = "C:\Users\vizio\CAMELOT_OS"
$logDir = Join-Path $root "logs\cybertronia"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# go_router reports this as its node name in SSE events.
$env:CAMELOT_NODE = "cybertronia"
# Path to the compiled Rust RTK engine (Go -> Rust rune dispatch).
$env:CAMELOT_RTK_BIN = "$root\target\release\rtk_cli.exe"
# Cognitive service (Graphify/MemCastle/sync over HTTP) port + scheduled //sync.
# :8090 is taken by saltare_gateway, so use :8092.
$env:COGNITIVE_PORT = "8092"
$env:CAMELOT_COGNITIVE_URL = "http://127.0.0.1:8092"  # go_router /cognitive proxy target
$env:COGNITIVE_SYNC_INTERVAL = "1800"  # auto //sync every 30 min (edge-first; skips if cloud down)

$daemons = @(
  @{ Name = "go_router";       Port = 8077; Exe = "$root\control_plane\go_router\go_router.exe";              Args = @("serve", ":8077") },
  @{ Name = "bifrost_sidecar"; Port = 8011; Exe = "$root\01_KERNEL\senses\bifrost_go_sidecar\bifrost_sidecar.exe"; Args = @() },
  @{ Name = "cognitive_service"; Port = 8092; Exe = "python"; Args = @("$root\control_plane\cognitive_service.py") },
  @{ Name = "opencodex";       Port = 10100; Exe = "node"; Args = @("--max-old-space-size=256", "$root\node_modules\@bitkyc08\opencodex\bin\ocx.mjs", "start", "--port", "10100") },
  @{ Name = "omnivoice";       Port = 3002; Exe = "node"; Args = @("--max-old-space-size=256", "$root\02_FORGE\KINETIC_ARMORY\omnivoice-router\dist\omnivoice-router.js") }
)

function Test-PortListening {
  param([int]$port)
  $tcp = New-Object System.Net.Sockets.TcpClient
  try {
    $res = $tcp.BeginConnect("127.0.0.1", $port, $null, $null)
    if ($res.AsyncWaitHandle.WaitOne(400) -and $tcp.Connected) {
      $tcp.EndConnect($res)
      return $true
    }
  } catch {} finally {
    $tcp.Close()
  }
  return $false
}

$procs = @{}
"[{0}] Cybertronia Always-On supervisor online" -f (Get-Date -Format s) | Add-Content (Join-Path $logDir "supervisor.log")

while ($true) {
  foreach ($d in $daemons) {
    if (Test-Path $d.Exe) {
      $isListening = Test-PortListening -port $d.Port
      if (-not $isListening) {
        $p = $procs[$d.Name]
        if (-not $p -or $p.HasExited) {
          $log = Join-Path $logDir ($d.Name + ".log")
          $err = Join-Path $logDir ($d.Name + ".err.log")
          "[{0}] (re)starting {1} on :{2}" -f (Get-Date -Format s), $d.Name, $d.Port | Add-Content (Join-Path $logDir "supervisor.log")
          try {
            if ($d.Args.Count -gt 0) {
              $procs[$d.Name] = Start-Process -FilePath $d.Exe -ArgumentList $d.Args `
                -RedirectStandardOutput $log -RedirectStandardError $err -WindowStyle Hidden -PassThru
            } else {
              $procs[$d.Name] = Start-Process -FilePath $d.Exe `
                -RedirectStandardOutput $log -RedirectStandardError $err -WindowStyle Hidden -PassThru
            }
          } catch {
            "[{0}] FAILED to start {1}: {2}" -f (Get-Date -Format s), $d.Name, $_ | Add-Content (Join-Path $logDir "supervisor.log")
          }
        }
      }
    }
  }

  # Flush live JSON telemetry via Python Always-On supervisor
  try {
    Start-Process -FilePath "python" -ArgumentList @("-m", "control_plane.infra.cybertronia_always_on", "tick") `
      -WindowStyle Hidden -Wait -ErrorAction SilentlyContinue
  } catch {}

  Start-Sleep -Seconds 5
}
