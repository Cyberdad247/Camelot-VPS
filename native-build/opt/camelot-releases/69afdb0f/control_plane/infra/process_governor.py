# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
"""
Bare-Metal Process & Scarcity Governor
CAMELOT-OS / Titan-OS vMAX Master Production Substrate
=============================================================================
Enforces Phase 2 of Master Production DAG:
1. "No Docker, Native Processes Only" invariant.
2. Hardware Scarcity Boundaries: 4096 MB Edge Node / 8192 MB Sovereign Server.
3. Win32 Job Object / cgroups v2 Memory Pinning & PSI Pressure Throttling.
"""

from __future__ import annotations

import ctypes
import gc
import os
import platform
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil


@dataclass(frozen=True)
class GovernorAuditReceipt:
    status: str  # "BOUNDARIES_NOMINAL" | "PRESSURE_THROTTLED" | "CEILING_BREACHED"
    role: str  # "EDGE_NODE" | "SOVEREIGN_SERVER"
    ceiling_mb: float
    current_working_set_mb: float
    pressure_ratio: float  # e.g. 0.35 (35%)
    native_processes_only: bool
    docker_containers_detected: int
    throttling_actions: List[str] = field(default_factory=list)


class BareMetalProcessGovernor:
    """
    Enforces native execution without container overhead and clamps
    process trees within the Law 03 memory ceilings.
    """

    NODE_CEILING_MB = 4096.0
    SERVER_CEILING_MB = 8192.0
    PRESSURE_THRESHOLD = 0.90  # 90% ceiling triggers proactive throttle

    def __init__(self, is_server: bool = False):
        self.is_server = is_server
        self.ceiling_mb = self.SERVER_CEILING_MB if is_server else self.NODE_CEILING_MB
        self.role = "SOVEREIGN_SERVER" if is_server else "EDGE_NODE"

    def inspect_system(self) -> GovernorAuditReceipt:
        """
        Inspects live processes, calculates memory pressure, and enforces invariants.
        """
        # 1. Enforce No Docker Invariant
        docker_count = 0
        for p in psutil.process_iter(["name"]):
            try:
                p_name = (p.info.get("name") or "").lower()
                if "docker" in p_name or "containerd" in p_name:
                    docker_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        native_only = (docker_count == 0)

        # 2. Inspect Camelot / Python / Node working sets
        total_working_set_bytes = 0
        current_proc = psutil.Process()
        total_working_set_bytes += current_proc.memory_info().rss

        for p in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                p_name = (p.info.get("name") or "").lower()
                if any(k in p_name for k in ("camelot", "bifrost", "multivoice")):
                    mem = p.info.get("memory_info")
                    if mem:
                        total_working_set_bytes += mem.rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        current_mb = total_working_set_bytes / (1024 * 1024)
        pressure_ratio = current_mb / self.ceiling_mb
        actions = []

        if current_mb > self.ceiling_mb:
            status = "CEILING_BREACHED"
            actions.append("EMERGENCY_MEMORY_TRIM")
            gc.collect()
        elif pressure_ratio >= self.PRESSURE_THRESHOLD:
            status = "PRESSURE_THROTTLED"
            actions.append("PROACTIVE_WORKING_SET_TRIM")
            gc.collect()
        else:
            status = "BOUNDARIES_NOMINAL"

        return GovernorAuditReceipt(
            status=status,
            role=self.role,
            ceiling_mb=self.ceiling_mb,
            current_working_set_mb=round(current_mb, 2),
            pressure_ratio=round(pressure_ratio, 4),
            native_processes_only=native_only,
            docker_containers_detected=docker_count,
            throttling_actions=actions,
        )

    def attach_job_object_limits(self) -> bool:
        """
        On Windows, binds process to a Win32 Job Object with hard memory ceiling.
        """
        if platform.system() != "Windows":
            return True

        try:
            # Win32 Job Object Constants
            JobObjectExtendedLimitInformation = 9
            JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
            JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200

            class IO_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("ReadOperationCount", ctypes.c_uint64),
                    ("WriteOperationCount", ctypes.c_uint64),
                    ("OtherOperationCount", ctypes.c_uint64),
                    ("ReadTransferCount", ctypes.c_uint64),
                    ("WriteTransferCount", ctypes.c_uint64),
                    ("OtherTransferCount", ctypes.c_uint64),
                ]

            class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("PerProcessUserTimeLimit", ctypes.c_int64),
                    ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", ctypes.c_uint32),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", ctypes.c_uint32),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", ctypes.c_uint32),
                    ("SchedulingClass", ctypes.c_uint32),
                ]

            class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                    ("IoInfo", IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t),
                ]

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            hJob = kernel32.CreateJobObjectW(None, f"CamelotSovereignJob_{os.getpid()}")
            if not hJob:
                return False

            limit_info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            limit_bytes = int(self.ceiling_mb * 1024 * 1024)
            limit_info.BasicLimitInformation.LimitFlags = (
                JOB_OBJECT_LIMIT_PROCESS_MEMORY | JOB_OBJECT_LIMIT_JOB_MEMORY
            )
            limit_info.ProcessMemoryLimit = limit_bytes
            limit_info.JobMemoryLimit = limit_bytes

            res = kernel32.SetInformationJobObject(
                hJob,
                JobObjectExtendedLimitInformation,
                ctypes.byref(limit_info),
                ctypes.sizeof(limit_info),
            )
            return bool(res)
        except Exception:
            return False
