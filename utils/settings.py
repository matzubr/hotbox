"""Per-user HotBox settings (which packages are on), stored outside the tool folder.

$HOUDINI_USER_PREF_DIR/hotbox/settings.json (HOTBOX_SETTINGS overrides the path), so the tool folder can
be copied between users and every user keeps their own choice.

Package state: the user's explicit on/off from the Script Manager wins; otherwise a package is on when it
is listed in the HOTBOX_PACKAGES environment variable (comma separated, e.g. set for a whole studio in
houdini.env); otherwise it is off.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import hou

SETTINGS_ENV = "HOTBOX_SETTINGS"
PACKAGES_ENV = "HOTBOX_PACKAGES"


def settingsPath() -> Path:
    custom = os.environ.get(SETTINGS_ENV)
    if custom:
        return Path(custom)
    pref_dir = hou.getenv("HOUDINI_USER_PREF_DIR")
    if pref_dir:
        return Path(pref_dir) / "hotbox" / "settings.json"
    return Path.home() / ".hotbox" / "settings.json"


def load() -> dict:
    path = settingsPath()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        print(f"HotBox: can't read {path.as_posix()}: {e}")
        return {}
    return data if isinstance(data, dict) else {}


def save(data: dict) -> None:
    path = settingsPath()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")


def _envPackages() -> set[str]:
    value = os.environ.get(PACKAGES_ENV) or hou.getenv(PACKAGES_ENV) or ""
    return {name.strip().casefold() for name in value.split(",") if name.strip()}


def isPackageEnabled(name: str, data: dict | None = None) -> bool:
    data = load() if data is None else data
    explicit = {key.casefold(): value for key, value in data.get("packages", {}).items()}
    key = name.casefold()
    if key in explicit:
        return bool(explicit[key])
    return key in _envPackages()


def enabledChecker(data: dict | None = None):
    """isEnabled(package) with the settings read once"""
    data = load() if data is None else data
    return lambda name: isPackageEnabled(name, data)


def setPackageEnabled(name: str, enabled: bool) -> None:
    data = load()
    data.setdefault("packages", {})[name] = bool(enabled)
    save(data)
