"""侧键绑定：分别尝试 active / user keyconfig 的 3D View keymap。"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
os.environ["PIEBIND_CONFIG_DIR"] = tempfile.mkdtemp(prefix="pb-side3-")

import bpy

import piebind
import piebind.config as cfg

BINDING_ID = "bd_side_test"


def report():
    print("SNAP_AFTER", bpy.context.scene.tool_settings.use_snap, flush=True)
    bpy.ops.wm.quit_blender()
    return None


def add_item(kc, label):
    km = None
    for candidate in kc.keymaps:
        if candidate.name == "3D View" and candidate.space_type == "VIEW_3D":
            km = candidate
            break
    if km is None:
        print("NO_KEYMAP", label, flush=True)
        return None
    try:
        kmi = km.keymap_items.new("piebind.dispatch", "LEFTMOUSE", "PRESS")
        kmi.properties.binding_id = BINDING_ID
        print("ADDED", label, kmi.type, flush=True)
        return kmi
    except Exception as exc:
        print("ADD_FAIL", label, exc, flush=True)
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
        "id": BINDING_ID,
        "enabled": True,
        "force_override": False,
        "keymap": {"name": "3D View", "space": "VIEW_3D", "region": "WINDOW"},
        "key": {"type": "BUTTON4MOUSE", "value": "PRESS"},
        "target": {
            "kind": "operator", "id": "wm.context_toggle",
            "props": {"data_path": "scene.tool_settings.use_snap"},
        },
    })
    cfg.save(data)

    wm = bpy.context.window_manager
    add_item(wm.keyconfigs.user, "user")
    add_item(wm.keyconfigs.active, "active")
    wm.keyconfigs.update()
    bpy.app.timers.register(ready, first_interval=1.5)
    return None


bpy.app.timers.register(setup, first_interval=1.2)
