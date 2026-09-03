"""Thin, safe wrapper around the `warp-cli` command-line tool.

Every method shells out to `warp-cli`, parses the result and returns plain
Python data structures. Nothing here touches Qt, so the module can be tested or
reused on its own. All commands run unprivileged — `warp-cli` talks to the
`warp-svc` daemon over a local socket, so no `sudo` is required.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.request
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Static option tables (mirrors `warp-cli mode --help`, tunnel/dns help output)
# ---------------------------------------------------------------------------

# (value passed to warp-cli, human label, tooltip/description)
MODES = [
    ("warp", "WARP", "Establish a tunnel and use normal UDP DNS proxying"),
    ("doh", "DNS only (DoH)", "No tunnel. Only proxy DNS over HTTPS"),
    ("warp+doh", "WARP + DoH", "Establish a tunnel and use DoH for DNS"),
    ("dot", "DNS only (DoT)", "No tunnel. Only proxy DNS over TLS"),
    ("warp+dot", "WARP + DoT", "Establish a tunnel and use DoT for DNS"),
    ("proxy", "Proxy (SOCKS5)", "Establish a tunnel for use in a SOCKS5 proxy"),
    ("tunnel_only", "Tunnel only", "Establish a tunnel and do not proxy DNS"),
]

# warp-cli expects these exact (case-sensitive) protocol names.
PROTOCOLS = [
    ("MASQUE", "MASQUE", "Default modern protocol"),
    ("WireGuard", "WireGuard", "Legacy protocol"),
]

# Consumer "Families" content-filtering modes.
FAMILIES = [
    ("off", "Off", "No content filtering (1.1.1.1)"),
    ("malware", "Malware", "Block known malware (1.1.1.2)"),
    ("full", "Malware + Adult", "Block malware and adult content (1.1.1.3)"),
]

TRACE_URL = "https://www.cloudflare.com/cdn-cgi/trace"


class WarpError(Exception):
    """Raised for any failure while talking to warp-cli."""


@dataclass
class Result:
    """Outcome of an action command."""

    ok: bool
    message: str


class WarpCli:
    def __init__(self, binary: str = "warp-cli"):
        self.binary = shutil.which(binary) or binary

    # -- low level ---------------------------------------------------------

    def available(self) -> bool:
        return bool(shutil.which(self.binary)) or os.path.exists(self.binary)

    def _run(self, args, timeout: int = 30, json_flag: bool = False,
             accept_tos: bool = False) -> subprocess.CompletedProcess:
        cmd = [self.binary]
        if json_flag:
            cmd.append("-j")
        if accept_tos:
            cmd.append("--accept-tos")
        cmd += args
        try:
            return subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )
        except FileNotFoundError as exc:
            raise WarpError(
                "warp-cli not found. Is cloudflare-warp installed?"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise WarpError(
                f"Command timed out: warp-cli {' '.join(args)}"
            ) from exc

    @staticmethod
    def _text(proc: subprocess.CompletedProcess) -> str:
        return (proc.stdout or "").strip() or (proc.stderr or "").strip()

    def _action(self, args, timeout: int = 60, accept_tos: bool = False) -> Result:
        proc = self._run(args, timeout=timeout, accept_tos=accept_tos)
        msg = self._text(proc) or (
            "Done." if proc.returncode == 0 else "Command failed."
        )
        return Result(proc.returncode == 0, msg)

    # -- status / settings -------------------------------------------------

    @staticmethod
    def _format_reason(reason) -> str:
        """warp-cli reports `reason` as a plain string when settled
        (e.g. "NetworkHealthy") but as an object while transitioning
        (e.g. {"PerformingHappyEyeballs": [...]}). Normalise both to a short,
        human-readable string."""
        if isinstance(reason, dict):
            if not reason:
                return ""
            reason = next(iter(reason))  # the variant name is the useful part
        if not isinstance(reason, str):
            reason = str(reason)
        # Split CamelCase for readability: "NetworkHealthy" -> "Network Healthy".
        return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", reason)

    def status(self) -> dict:
        """Return {status, reason, ok, raw}. Never raises for a normal
        disconnected/daemon-down state — reports it via the dict instead."""
        try:
            proc = self._run(["status"], json_flag=True, timeout=10)
        except WarpError as exc:
            return {"status": "Unknown", "reason": str(exc), "ok": False,
                    "raw": str(exc)}
        raw = self._text(proc)
        try:
            data = json.loads(proc.stdout)
            return {
                "status": data.get("status", "Unknown"),
                "reason": self._format_reason(data.get("reason", "")),
                "ok": proc.returncode == 0,
                "raw": raw,
            }
        except (json.JSONDecodeError, ValueError):
            return {"status": "Unknown", "reason": raw, "ok": False, "raw": raw}

    def settings(self) -> dict:
        proc = self._run(["settings", "list"], json_flag=True, timeout=10)
        try:
            return json.loads(proc.stdout).get("settings", {})
        except (json.JSONDecodeError, ValueError):
            return {}

    def current_mode(self) -> str | None:
        return self.settings().get("operation_mode")

    def current_protocol(self) -> str | None:
        # Stored lower-case, e.g. 'masque' / 'wireguard'.
        return self.settings().get("warp_tunnel_protocol")

    # -- connection --------------------------------------------------------

    def connect(self) -> Result:
        return self._action(["connect"])

    def disconnect(self) -> Result:
        return self._action(["disconnect"])

    def set_mode(self, mode: str) -> Result:
        return self._action(["mode", mode])

    def set_protocol(self, protocol: str) -> Result:
        return self._action(["tunnel", "protocol", "set", protocol])

    def set_families(self, mode: str) -> Result:
        return self._action(["dns", "families", mode])

    def apply_settings(self, mode=None, protocol=None, family=None) -> Result:
        """Apply any combination of mode / protocol / family in one go
        (used when applying a saved profile). Aggregates the outcomes."""
        steps = []
        if mode:
            steps.append(("mode", self.set_mode(mode)))
        if protocol:
            steps.append(("protocol", self.set_protocol(protocol)))
        if family:
            steps.append(("family", self.set_families(family)))
        if not steps:
            return Result(True, "Nothing to apply.")
        ok = all(r.ok for _, r in steps)
        parts = [f"{name}: {'ok' if r.ok else r.message}" for name, r in steps]
        return Result(ok, "; ".join(parts))

    # -- registration ------------------------------------------------------

    def registration_show(self) -> dict:
        """Return {registered: bool, fields: {..}, error: str}."""
        proc = self._run(["registration", "show"], timeout=15)
        text = self._text(proc)
        if proc.returncode != 0 or "Missing" in text or "not registered" in text.lower():
            return {"registered": False, "fields": {}, "error": text}
        fields = {}
        for line in proc.stdout.splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                fields[key.strip()] = value.strip()
        registered = bool(fields)
        return {"registered": registered, "fields": fields, "error": ""}

    def register_new(self, organization: str | None = None,
                     accept_tos: bool = True) -> Result:
        args = ["registration", "new"]
        if organization:
            args.append(organization)
        return self._action(args, timeout=120, accept_tos=accept_tos)

    def registration_delete(self) -> Result:
        return self._action(["registration", "delete"], timeout=60)

    # -- verification ------------------------------------------------------

    def verify_trace(self, timeout: int = 8) -> dict:
        """Fetch the Cloudflare trace endpoint and report the warp= value.

        Returns {ok: bool, warp: str, message: str}.
        warp is one of 'on', 'plus', 'off' or '' when unknown.
        """
        try:
            with urllib.request.urlopen(TRACE_URL, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", "replace")
        except Exception as exc:  # network error, timeout, etc.
            return {"ok": False, "warp": "", "message": f"Could not reach Cloudflare: {exc}"}
        warp = ""
        for line in body.splitlines():
            if line.startswith("warp="):
                warp = line.split("=", 1)[1].strip()
                break
        if warp in ("on", "plus"):
            return {"ok": True, "warp": warp,
                    "message": f"Verified — traffic goes through WARP (warp={warp})."}
        return {"ok": False, "warp": warp or "unknown",
                "message": f"WARP not detected (warp={warp or 'unknown'})."}
