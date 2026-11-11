# SPDX-License-Identifier: MIT

"""Shared VPS/Hermes topology links for inference routing surfaces."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from control_plane.infra.mesh_topology import HUB_TAILSCALE_IP

VPS_NODE_ID = "vps_hub_kvm563"
VPS_PUBLIC_IP = "162.35.107.134"
# Sourced from the single mesh topology. This previously read 100.71.218.75, the
# documented address of kba-services — a *different* node, and one absent from
# `tailscale status` entirely. Do not reintroduce the literal; mesh_topology is
# reconciled against the live tailnet and tests/test_mesh_topology_single_source
# asserts this constant matches it.
VPS_TAILSCALE_IP = HUB_TAILSCALE_IP
HERMES_PRIME_UUID = "28f89cb6-5048-4b5d-9e94-376082d24744"


def build_vps_hermes_inference_links(
    *,
    public_ip: str = VPS_PUBLIC_IP,
    tailscale_ip: str = VPS_TAILSCALE_IP,
) -> dict[str, dict[str, Any]]:
    """Return non-secret inference links governed by Hermes on the VPS hub."""
    bifrost_gateway = f"http://{tailscale_ip}:3001"
    mesh_bridge = f"http://{tailscale_ip}:8095"
    return {
        "cliproxy_sie": {
            "selector": "cliproxy:default",
            "backend": "cliproxy",
            "model_tag": "auto-fallback",
            "service": "CLIProxyAPI",
            "local_base_url": "http://127.0.0.1:8080/v1",
            "bifrost_gateway": bifrost_gateway,
            "mesh_bridge": mesh_bridge,
            "bifrost_bridge": {
                "name": "Bifrost Bridge",
                "module": "control_plane/dispatch/bifrost.py",
                "gateway_url": bifrost_gateway,
                "mesh_bridge_url": mesh_bridge,
                "governed_surface": "bifrost_bridge",
                "co_governors": ["HERMES_PRIME", "SIR_HEIMDALL"],
                "auth": {
                    "token_header": "x-camelot-token",
                    "lease_header": "X-Camelot-Lease-ID",
                    "secret_values_serialized": False,
                },
            },
            "vps_public_ip": public_ip,
            "vps_node": VPS_NODE_ID,
            "governing_knight": "HERMES_PRIME",
            "hermes_prime_uuid": HERMES_PRIME_UUID,
            "co_guardian": "SIR_HEIMDALL",
            "air_gapped": False,
            "loopback_only_upstream": True,
            "credential_env": "CLIPROXY_API_KEY",
            "secret_values_serialized": False,
        },
        "vllm_deepseek_flash": {
            "selector": "vllm:deepseek-ai/DeepSeek-V4.1-Flash",
            "backend": "vllm",
            "model_tag": "deepseek-ai/DeepSeek-V4.1-Flash",
            "inference_scope": "bifrost_hub",
            "manifest_alias": "deepseek-flash",
            "service": "vLLM",
            "local_base_url": "http://127.0.0.1:8000/v1",
            "bifrost_route": "/bifrost/models/deepseek-flash",
            "bifrost_gateway": bifrost_gateway,
            "mesh_bridge": mesh_bridge,
            "vps_public_ip": public_ip,
            "vps_node": VPS_NODE_ID,
            "governing_knight": "HERMES_PRIME",
            "hermes_prime_uuid": HERMES_PRIME_UUID,
            "co_guardian": "SIR_HEIMDALL",
            "air_gapped": False,
            "secret_values_serialized": False,
        },
    }


def attach_vps_hermes_links(topology: dict[str, Any]) -> dict[str, Any]:
    """Attach Hermes-governed inference links to the VPS hub node."""
    linked = deepcopy(topology)
    node = linked.setdefault("nodes", {}).setdefault(VPS_NODE_ID, {})
    public_ip = str(node.get("public_ip") or VPS_PUBLIC_IP)
    tailscale_ip = str(node.get("tailscale_ip") or VPS_TAILSCALE_IP)
    inference_links = node.setdefault("inference_links", {})
    for key, value in build_vps_hermes_inference_links(
        public_ip=public_ip,
        tailscale_ip=tailscale_ip,
    ).items():
        inference_links.setdefault(key, value)
    return linked
