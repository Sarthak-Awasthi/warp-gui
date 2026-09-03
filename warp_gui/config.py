"""Persisted GUI state: the last-applied DNS family filter and saved profiles.

warp-cli exposes no read-back for the DNS family mode, so we remember the last
value we applied here. Stored as JSON under the XDG config directory.

Config shape::

    {
      "family": "off",                      # last-applied family filter
      "profiles": {
        "Work": {"mode": "warp", "protocol": "MASQUE", "family": "malware"},
        ...
      }
    }
"""

from __future__ import annotations

import json
import os


def _config_dir() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "warp-gui")


class Config:
    def __init__(self, path: str | None = None):
        self.path = path or os.path.join(_config_dir(), "config.json")
        self.family: str = "off"
        self.profiles: dict[str, dict] = {}
        self.load()

    # -- persistence -------------------------------------------------------

    def load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return
        if isinstance(data, dict):
            fam = data.get("family")
            if isinstance(fam, str):
                self.family = fam
            profiles = data.get("profiles")
            if isinstance(profiles, dict):
                # Keep only well-formed entries.
                self.profiles = {
                    str(name): {
                        "mode": p.get("mode"),
                        "protocol": p.get("protocol"),
                        "family": p.get("family"),
                    }
                    for name, p in profiles.items()
                    if isinstance(p, dict)
                }

    def save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(
                    {"family": self.family, "profiles": self.profiles},
                    fh, indent=2,
                )
            os.replace(tmp, self.path)
        except OSError as exc:  # non-fatal: the app still works without saving
            print(f"warp-gui: could not save config: {exc}")

    # -- mutations ---------------------------------------------------------

    def set_family(self, value: str) -> None:
        self.family = value
        self.save()

    def set_profile(self, name: str, mode, protocol, family) -> None:
        self.profiles[name] = {
            "mode": mode, "protocol": protocol, "family": family,
        }
        self.save()

    def delete_profile(self, name: str) -> None:
        self.profiles.pop(name, None)
        self.save()
