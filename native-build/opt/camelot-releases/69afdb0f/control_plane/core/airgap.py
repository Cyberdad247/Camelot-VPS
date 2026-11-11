# -*- coding: utf-8 -*-
"""Air-gap enforcement for the zero-trust execution lane.

Why this module exists
----------------------
``soul_router`` gives Sir Ghost and Sir Zeroclaw ``privacy_level = 1.0``, and the
README described that as an air-gap guarantee. It was not one: ``privacy_level``
is a float in a weighted routing score. It makes the router *prefer* a knight and
binds it to a local model; it does nothing to stop a socket being opened. No
seccomp filter, network namespace, or egress rule existed anywhere in the tree —
``bwrap``/``proot``/``unshare`` appeared only as strings in a config list.

This module supplies the missing control: a launcher that runs a command inside a
network namespace with no route to anywhere, plus ``no_new_privs`` and resource
limits, and that **refuses to run at all** when it cannot establish that
isolation. A lane that silently degrades to "no isolation" is worse than one that
stops, because callers cannot tell the difference.

Scope and limits
----------------
This enforces *network* isolation and basic privilege/resource limits. It is not
a full sandbox: there is no filesystem confinement (Landlock/AppArmor), no
cgroups quota, and no read-only rootfs. Those are the next layers — see
``docs/threat-model.md`` §5.2. What it does guarantee, and what the tests assert:
an air-gapped process cannot resolve DNS, cannot open an outbound socket, and
cannot reach a cloud metadata endpoint.

Linux-only. On any other platform :func:`probe` reports unavailable and
:func:`run_airgapped` raises, which is the fail-closed answer.
"""
from __future__ import annotations

import ctypes
import errno
import os
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional, Sequence

__all__ = [
    "AirgapUnavailableError",
    "AirgapCapabilities",
    "probe",
    "run_airgapped",
    "require_airgap",
]

# Linux clone(2) namespace flags.
_CLONE_NEWUSER = 0x1000_0000
_CLONE_NEWNET = 0x4000_0000

# prctl(2) PR_SET_NO_NEW_PRIVS — once set, execve can never gain privileges.
_PR_SET_NO_NEW_PRIVS = 38

# Default ceilings for an air-gapped child. Deliberately modest: this lane is for
# local, private work, not for heavy builds.
DEFAULT_CPU_SECONDS = 120
DEFAULT_MEMORY_BYTES = 512 * 1024 * 1024
DEFAULT_WALL_TIMEOUT = 120


class AirgapUnavailableError(RuntimeError):
    """Isolation could not be established, so the lane refuses to execute.

    Raised rather than falling back to an unisolated run: the whole point of the
    lane is that "air-gapped" means something, and a silent downgrade would make
    the guarantee unfalsifiable.
    """


@dataclass(frozen=True)
class AirgapCapabilities:
    """What this host can actually enforce."""

    platform_supported: bool
    network_namespace: bool
    no_new_privs: bool
    resource_limits: bool
    details: dict[str, str] = field(default_factory=dict)

    @property
    def sufficient(self) -> bool:
        """True when the *network* guarantee can be honoured.

        Network isolation is the load-bearing property of this lane. no_new_privs
        and rlimits are hardening; their absence is reported but does not by
        itself disable the lane.
        """
        return self.platform_supported and self.network_namespace

    def render(self) -> str:
        mark = lambda ok: "yes" if ok else "NO"  # noqa: E731
        lines = [
            f"  platform supported : {mark(self.platform_supported)}",
            f"  network namespace  : {mark(self.network_namespace)}",
            f"  no_new_privs       : {mark(self.no_new_privs)}",
            f"  resource limits    : {mark(self.resource_limits)}",
        ]
        for key, value in sorted(self.details.items()):
            lines.append(f"  {key}: {value}")
        return "\n".join(lines)


def _libc() -> Optional[ctypes.CDLL]:
    try:
        return ctypes.CDLL("libc.so.6", use_errno=True)
    except OSError:
        return None


def _unshare_network(libc: ctypes.CDLL) -> None:
    """Enter a fresh network namespace, raising OSError on failure.

    Tries the plain network namespace first (works when running as root), then
    falls back to creating a user namespace alongside it, which is how an
    unprivileged process gets CAP_NET_ADMIN over its own new namespace.
    """
    if libc.unshare(_CLONE_NEWNET) == 0:
        return
    first = ctypes.get_errno()

    if libc.unshare(_CLONE_NEWUSER | _CLONE_NEWNET) == 0:
        return
    second = ctypes.get_errno()

    raise OSError(
        second,
        f"unshare(CLONE_NEWNET) failed with {errno.errorcode.get(first, first)}; "
        f"unshare(CLONE_NEWUSER|CLONE_NEWNET) failed with "
        f"{errno.errorcode.get(second, second)}",
    )


def probe() -> AirgapCapabilities:
    """Report which isolation primitives this host provides.

    Performs the namespace check in a throwaway child so the calling process is
    never moved into a namespace as a side effect of asking.
    """
    details: dict[str, str] = {}

    if platform.system() != "Linux":
        details["reason"] = f"{platform.system()} has no equivalent of CLONE_NEWNET"
        return AirgapCapabilities(False, False, False, False, details)

    libc = _libc()
    if libc is None:
        details["reason"] = "libc.so.6 could not be loaded; cannot call unshare(2)"
        return AirgapCapabilities(True, False, False, False, details)

    # Probe in a child: unshare is irreversible for the caller.
    probe_src = (
        "import ctypes,sys\n"
        "libc=ctypes.CDLL('libc.so.6',use_errno=True)\n"
        f"ok = libc.unshare({_CLONE_NEWNET})==0 or "
        f"libc.unshare({_CLONE_NEWUSER | _CLONE_NEWNET})==0\n"
        "sys.exit(0 if ok else 1)\n"
    )
    try:
        completed = subprocess.run(
            [sys.executable, "-c", probe_src],
            capture_output=True, timeout=20, check=False,
        )
        netns = completed.returncode == 0
        if not netns:
            details["netns_error"] = (
                completed.stderr.decode("utf-8", "replace").strip()[:200]
                or "unshare returned non-zero"
            )
    except (OSError, subprocess.SubprocessError) as err:
        netns = False
        details["netns_error"] = str(err)[:200]

    nnp = hasattr(libc, "prctl")
    try:
        import resource  # noqa: F401
        rlimits = True
    except ImportError:
        rlimits = False

    return AirgapCapabilities(True, netns, nnp, rlimits, details)


def _child_setup(cpu_seconds: int, memory_bytes: int) -> None:
    """Runs in the forked child, before exec. Must not raise silently.

    Any exception here propagates to the parent as a failed Popen, which is the
    fail-closed outcome: the command never runs unisolated.
    """
    libc = _libc()
    if libc is None:
        raise AirgapUnavailableError("libc unavailable in child; cannot isolate")

    _unshare_network(libc)

    # Best-effort hardening. no_new_privs cannot fail open in a way that matters
    # here (the namespace is already established), so a failure is not fatal.
    try:
        libc.prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)
    except Exception:  # pragma: no cover - platform-dependent
        pass

    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    except Exception:  # pragma: no cover - platform-dependent
        pass


def require_airgap() -> AirgapCapabilities:
    """Return capabilities, or raise if the air-gap cannot be enforced."""
    caps = probe()
    if not caps.sufficient:
        raise AirgapUnavailableError(
            "air-gapped execution requested but network isolation is "
            "unavailable on this host, so the lane cannot honour its guarantee. "
            "Refusing to run unisolated.\n" + caps.render()
        )
    return caps


def run_airgapped(
    argv: Sequence[str],
    *,
    cwd: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
    timeout: int = DEFAULT_WALL_TIMEOUT,
    cpu_seconds: int = DEFAULT_CPU_SECONDS,
    memory_bytes: int = DEFAULT_MEMORY_BYTES,
) -> subprocess.CompletedProcess:
    """Run ``argv`` with no network access.

    The child is placed in a fresh network namespace whose only interface is a
    down loopback, so every outbound connection fails with ENETUNREACH and DNS
    cannot resolve. It also gets ``no_new_privs`` and CPU/address-space limits.

    Raises :class:`AirgapUnavailableError` if isolation cannot be established.
    The command is never executed without it.
    """
    require_airgap()

    # Minimal environment by default: inherited env is a common exfiltration
    # path (proxy variables, tokens) and is not needed by a local-only task.
    child_env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": os.environ.get("HOME", "/tmp"),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "CAMELOT_AIRGAPPED": "1",
    }
    if env:
        child_env.update(env)

    try:
        return subprocess.run(
            list(argv),
            cwd=cwd,
            env=child_env,
            capture_output=True,
            timeout=timeout,
            check=False,
            preexec_fn=lambda: _child_setup(cpu_seconds, memory_bytes),
        )
    except OSError as err:
        raise AirgapUnavailableError(
            f"failed to launch {argv[0]!r} inside a network namespace: {err}"
        ) from err


# ── Self-test ────────────────────────────────────────────────────────────────

def _selftest() -> int:
    caps = probe()
    print("Air-gap capability probe")
    print(caps.render())

    if not caps.sufficient:
        print("\n[FAIL] network isolation unavailable — the lane would refuse to run")
        return 1

    checks = [
        ("outbound TCP blocked",
         "import socket,sys\n"
         "try:\n"
         "    socket.create_connection(('1.1.1.1',53),timeout=3); sys.exit(1)\n"
         "except OSError: sys.exit(0)\n"),
        ("DNS resolution blocked",
         "import socket,sys\n"
         "try:\n"
         "    socket.getaddrinfo('example.com',80); sys.exit(1)\n"
         "except OSError: sys.exit(0)\n"),
        ("cloud metadata unreachable",
         "import socket,sys\n"
         "try:\n"
         "    socket.create_connection(('169.254.169.254',80),timeout=3); sys.exit(1)\n"
         "except OSError: sys.exit(0)\n"),
    ]

    failures = 0
    print()
    for name, src in checks:
        result = run_airgapped([sys.executable, "-c", src])
        ok = result.returncode == 0
        failures += not ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")

    # Control: the same probe must SUCCEED without the air-gap, otherwise the
    # test proves nothing (a host with no network would pass trivially).
    control = subprocess.run(
        [sys.executable, "-c", checks[1][1]], capture_output=True, timeout=30, check=False
    )
    if control.returncode == 0:
        print("  [WARN] DNS also fails outside the air-gap — result is not conclusive")

    print("\n" + ("ALL PASS — airgap" if not failures else f"{failures} FAILED"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
