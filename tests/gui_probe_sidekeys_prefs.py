"""侧键验证：打开偏好设置（draw 里会挂监听）后按侧键。"""

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
    bpy.app.timers.register(report, first_interval=7.0)
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
    try:
        bpy.ops.preferences.addon_show(module="bl_ext.user_default.piebind")
        print("PREFS_OPENED", flush=True)
    except Exception as exc:
        print("PREFS_FAIL", exc, flush=True)
    bpy.app.timers.register(ready, first_interval=1.5)
    return None


bpy.app.timers.register(setup, first_interval=1.5)