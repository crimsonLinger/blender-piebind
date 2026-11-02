"""诊断导出：给 GitHub issue 用。默认对本地路径做脱敏。"""

import os
import platform
import sys
import time

import bpy

from .core import config, keymap as ke

VERSION = "0.1.0"
HOME = os.path.expanduser("~")


def _redact(text):
    if not text or not isinstance(text, str):
        return text
    home = HOME.rstrip("\\/")
    if home and text.startswith(home):
        return "~" + text[len(home):].replace("\\", "/")
    return text


def build_report():
    wm = bpy.context.window_manager
    data = config.load()

    layers = []
    for kc in wm.keyconfigs:
        layers.append({
            "name": kc.name,
            "active": kc == wm.keyconfigs.active,
            "keymaps": len(kc.keymaps),
            "items": sum(len(km.keymap_items) for km in kc.keymaps),
        })

    try:
        addons = sorted(bpy.context.preferences.addons.keys())
    except Exception:
        addons = []

    report = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "tool": {"name": "PieBind", "version": VERSION},
        "blender": {
            "version": bpy.app.version_string,
            "version_number": list(bpy.app.version),
            "background": bool(bpy.app.background),
        },
        "python": sys.version.split()[0],
        "os": platform.platform(),
        "state": {
            "applied": len(ke.APPLIED["items"]),
            "muted": len(ke.APPLIED["muted"]),
            "journal_present": config.read_journal() is not None,
        },
        "config": {
            "dir": _redact(config.config_dir()),
            "schema_version": data.get("schema_version"),
            "pies": len(data.get("pies", [])),
            "bindings": len(data.get("bindings", [])),
            "duplicates": ke.duplicate_bindings(data),
        },
        "layers": layers,
        "plugin_bindings": ke.scan_all_plugin_bindings(),
        "addons": addons,
    }
    return report


def dumps():
    import json
    return json.dumps(build_report(), ensure_ascii=False, indent=1)
