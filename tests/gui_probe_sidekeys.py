"""验证：注册期写入的侧键条目是否能触发 dispatch_side。"""

import bpy

import importlib

pkg = importlib.import_module("bl_ext.user_default.piebind")
cfg = pkg.core.config


def report():
    print("SNAP_AFTER", bpy.context.scene.tool_settings.use_snap, flush=True)
    bpy.ops.wm.quit_blender()
    return None


def ready():
    print("SNAP_BEFORE", bpy.context.scene.tool_settings.use_snap, flush=True)
    print("READY", flush=True)
    bpy.app.timers.register(report, first_interval=6.0)
    return None


def setup():
    data = cfg.load()
    data["bindings"].append({
        "id": cfg.new_id("bd"),
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
    print("BOUND", flush=True)
    bpy.app.timers.register(ready, first_interval=1.0)
    return None


bpy.app.timers.register(setup, first_interval=1.5)