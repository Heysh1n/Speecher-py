# fc/presets.py
"""Preset management — save/load/delete named file lists."""

import json
from pathlib import Path

from fc.config import get_presets_path


def load_presets(root: Path | None = None) -> dict[str, list[str]]:
    fp = get_presets_path(root)
    if fp.exists():
        try:
            return json.loads(fp.read_text("utf-8"))
        except Exception:
            return {}
    return {}


def save_presets(data: dict[str, list[str]], root: Path | None = None) -> None:
    fp = get_presets_path(root)
    fp.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")


def delete_preset(name: str, root: Path | None = None) -> bool:
    presets = load_presets(root)
    if name not in presets:
        return False
    del presets[name]
    save_presets(presets, root)
    return True