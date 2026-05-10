#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
action_server.py - SDN Action Executor API (runs inside Mininet VM)
====================================================================
Start inside the Mininet VM (.venv):
    cd ~/scripts
    .venv/bin/uvicorn action_server:app --host 0.0.0.0 --port 8000

Uses the same tc/netem mechanism as traffic_gen.py to reduce packet loss.
"""

import re
import subprocess
from typing import Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="QoSentry SDN Action Executor", version="1.0")


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class SDNAction(BaseModel):
    action: str
    device: Optional[str] = "s1"
    path: Optional[str] = None
    interface: Optional[str] = None
    rate_limit_mbps: Optional[float] = None
    profile: Optional[str] = None
    segment: Optional[str] = None
    reason: Optional[str] = None


class ScenarioRequest(BaseModel):
    scenario: str  # CALL_DROP | POOR_VOICE_QUALITY | LOW_THROUGHPUT | HIGH_LATENCY | CAPACITY_EXHAUSTED | NORMAL


# ---------------------------------------------------------------------------
# Topology constants (mirrors traffic_gen.py)
# ---------------------------------------------------------------------------

BASELINE = {
    "s1-eth1": {"loss": 2,  "delay": 5,  "jitter": 2},
    "s1-eth2": {"loss": 8,  "delay": 15, "jitter": 5},
    "s1-eth3": {"loss": 1,  "delay": 2,  "jitter": 1},
    "s1-eth4": {"loss": 2,  "delay": 20, "jitter": 3},
}

SEGMENT_TO_IFACE = {
    "OUTDOOR_RAN": "s1-eth1",
    "INDOOR_RAN":  "s1-eth2",
    "IMS_CDN":     "s1-eth3",
    "INTERNET":    "s1-eth4",
}

DEVICE_ALIASES = {
    "switch-core-01": "s1",
    "core": "s1",
    "s1": "s1",
}

# Scenario definitions — (iface, loss%, delay_ms, jitter_ms)
SCENARIO_PARAMS: Dict[str, List[Tuple[str, float, float, float]]] = {
    "CALL_DROP":          [("s1-eth1", 70, 5,   2), ("s1-eth2", 75, 15,  5)],
    "POOR_VOICE_QUALITY": [("s1-eth2", 15, 80,  10)],
    "LOW_THROUGHPUT":     [("s1-eth3", 30, 2,   1)],
    "HIGH_LATENCY":       [("s1-eth1", 2,  250, 30), ("s1-eth2", 8, 300, 40)],
    "CAPACITY_EXHAUSTED": [("s1-eth1", 25, 5,   2), ("s1-eth2", 30, 15, 5),
                           ("s1-eth3", 20, 2,   1), ("s1-eth4", 25, 20, 3)],
    "NORMAL":             [],  # restore all to baseline
}


# ---------------------------------------------------------------------------
# TC/netem helpers (ported from traffic_gen.py)
# ---------------------------------------------------------------------------

def _tc_show(iface: str) -> str:
    try:
        return subprocess.check_output(
            ["tc", "-s", "qdisc", "show", "dev", iface],
            stderr=subprocess.DEVNULL,
        ).decode()
    except subprocess.CalledProcessError:
        return ""


def _get_tc_qdisc_info(iface: str) -> Optional[dict]:
    out = _tc_show(iface)
    htb_root = re.search(r"qdisc htb (\w+): root", out)
    netem_child = re.search(r"qdisc netem (\w+): parent (\S+)", out)
    if htb_root and netem_child:
        return {
            "type": "htb+netem",
            "parent": netem_child.group(2),
        }
    netem_root = re.search(r"qdisc netem (\w+): root", out)
    if netem_root:
        return {"type": "netem-root"}
    return None


def _set_netem(iface: str, loss_pct: float, delay_ms: float, jitter_ms: float) -> dict:
    """Apply tc netem parameters on iface — same mechanism as traffic_gen.py set_netem()."""
    info = _get_tc_qdisc_info(iface)
    if not info:
        return {"ok": False, "cmd": "", "stderr": f"No netem qdisc found on {iface}"}

    delay_args = [f"{delay_ms}ms"]
    if jitter_ms > 0:
        delay_args += [f"{jitter_ms}ms", "distribution", "normal"]

    loss_args = ["loss", f"{loss_pct}%"] if loss_pct > 0 else []

    cmd_parts = ["sudo", "tc", "qdisc", "change", "dev", iface]
    if info["type"] == "htb+netem":
        cmd_parts += ["parent", info["parent"]]
    else:
        cmd_parts += ["root"]
    cmd_parts += ["netem", "delay"] + delay_args + loss_args

    cmd = " ".join(cmd_parts)
    print(f"[TC] {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    ok = result.returncode == 0
    if not ok:
        print(f"[TC] ERROR on {iface}: {result.stderr.strip()}")
    else:
        print(f"[TC] {iface}: loss={loss_pct}% delay={delay_ms}ms jitter={jitter_ms}ms")
    return {
        "ok": ok,
        "cmd": cmd,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def _restore_baseline(iface: str) -> dict:
    """Restore netem to traffic_gen baseline values for this interface."""
    b = BASELINE.get(iface)
    if not b:
        return {"ok": False, "stderr": f"No baseline for {iface}"}
    return _set_netem(iface, b["loss"], b["delay"], b["jitter"])


# ---------------------------------------------------------------------------
# Resolvers
# ---------------------------------------------------------------------------

def _resolve_device(name: str) -> str:
    return DEVICE_ALIASES.get(name or "s1", "s1")


def _resolve_iface(raw: str) -> str:
    if re.match(r"^s\d+-eth\d+$", raw or ""):
        return raw
    if raw in SEGMENT_TO_IFACE:
        return SEGMENT_TO_IFACE[raw]
    m = re.search(r"eth(\d+)", raw or "")
    if m:
        return f"s1-eth{m.group(1)}"
    return "s1-eth1"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/scenario")
def inject_scenario(req: ScenarioRequest):
    """Inject a named degradation scenario via tc/netem."""
    name = req.scenario.upper()
    if name not in SCENARIO_PARAMS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scenario: {name!r}. Valid: {list(SCENARIO_PARAMS)}"
        )

    results = []
    if name == "NORMAL":
        for iface in BASELINE:
            results.append(_restore_baseline(iface))
        print(f"[SCENARIO] NORMAL -> all interfaces restored to baseline")
    else:
        for (iface, loss, delay, jitter) in SCENARIO_PARAMS[name]:
            results.append(_set_netem(iface, loss, delay, jitter))
        print(f"[SCENARIO] {name} -> injected on {[t[0] for t in SCENARIO_PARAMS[name]]}")

    all_ok = all(r.get("ok", False) for r in results)
    return {
        "status": "ok" if all_ok else "partial_error",
        "scenario": name,
        "interfaces_affected": [t[0] for t in SCENARIO_PARAMS.get(name, [])] or list(BASELINE.keys()),
        "results": results,
    }


@app.post("/action")
def execute_action(action: SDNAction):
    bridge = _resolve_device(action.device)
    results = []

    if action.action == "reroute_traffic":
        iface = _resolve_iface(action.path or "s1-eth2")
        b = BASELINE.get(iface, {"delay": 5, "jitter": 2})
        results.append(_set_netem(iface, loss_pct=0.5, delay_ms=b["delay"], jitter_ms=b["jitter"]))
        print(f"[ACTION] reroute_traffic -> loss reduced on {iface}")

    elif action.action == "throttle_link":
        iface = _resolve_iface(action.interface or "s1-eth1")
        b = BASELINE.get(iface, {"delay": 5, "jitter": 2})
        results.append(_set_netem(iface, loss_pct=b["loss"], delay_ms=b["delay"], jitter_ms=b["jitter"]))
        print(f"[ACTION] throttle_link -> restored baseline loss on {iface}")

    elif action.action == "restart_interface":
        iface = _resolve_iface(action.interface or "s1-eth1")
        results.append(_restore_baseline(iface))
        print(f"[ACTION] restart_interface -> netem reset on {iface}")

    elif action.action == "apply_qos_profile":
        profile = action.profile or ""
        if "voice" in profile or "video" in profile:
            results.append(_set_netem("s1-eth1", loss_pct=0.5, delay_ms=5,  jitter_ms=1))
            results.append(_set_netem("s1-eth2", loss_pct=1.0, delay_ms=15, jitter_ms=3))
            results.append(_set_netem("s1-eth3", loss_pct=0.5, delay_ms=2,  jitter_ms=1))
            results.append(_set_netem("s1-eth4", loss_pct=1.0, delay_ms=20, jitter_ms=2))
        else:
            for iface in BASELINE:
                results.append(_restore_baseline(iface))
        print(f"[ACTION] apply_qos_profile '{profile}' -> loss reduced on all s1 interfaces")

    elif action.action == "monitor_only":
        print(f"[ACTION] monitor_only - {action.reason or 'no change'}")
        return {"status": "ok", "action": "monitor_only", "results": []}

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action.action!r}")

    all_ok = all(r["ok"] for r in results)
    return {
        "status": "ok" if all_ok else "partial_error",
        "action": action.action,
        "device": bridge,
        "results": results,
    }
