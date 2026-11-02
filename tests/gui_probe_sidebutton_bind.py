"""端到端验证：把侧键绑到 wm.context_toggle，发送 XBUTTON 看是否触发。"""

import os
import sys
import tempfile

sys.path.insert(0, r"<旧目录>\src")
os.environ["PIEBIND_CONFIG_DIR"] = tempfile.mkdtemp(prefix="pb-side-")

import bpy

import piebind
import piebind.config as cfg
import piebind.keymap_engine as ke

STATE = {}


def report():
    print("SNAP_AFTER", bpy.context.scene.tool_settings.use_snap, flush=True)
    try:
        ke.unapply()
    except Exception as exc:
        print("UNAPPLY_FAIL", exc, flush=True)
    bpy.ops.wm.quit_blender()
    return None


def ready():
    print("SNAP_BEFORE", bpy.context.scene.tool_settings.use_snap, flush=True)
    print("READY", flush=True)
    bpy.app.timers.register(report, first_interval=6.0)
    return None


def setup():
    piebind.register()
    data = cfg.load()
    data["bindings"].append({
        "id": cfg.new_id("bd"),
        "enabled": True,
        "force_override": False,
        "keymap": {"name": "3D View", "space": "VIEW_3D", "region": "WINDOW"},
        "key": {"type": "BUTTON4MOUSE", "value": "PRESS", "ctrl": False, "shift": False,
                "alt": False, "oskey": False, "any": False, "key_modifier": "NONE"},
        "target": {
            "kind": "operator", "id": "wm.context_toggle", "idname": "wm.context_toggle",
            "props": {"data_path": "scene.tool_settings.use_snap"},
        },
    })
    cfg.save(data)
    print("APPLY", ke.apply(data), flush=True)
    bpy.app.timers.register(ready, first_interval=1.5)
    return None


bpy.app.timers.register(setup, first_interval=1.2)
