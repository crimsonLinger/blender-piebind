"""决定性实验：把监听挂到「主窗口」（屏幕含 3D 视口的那个）上。"""

import bpy

import importlib

pkg = importlib.import_module("bl_ext.user_default.piebind")
cfg = pkg.core.config
sidekeys = pkg.ops.sidekeys


def main_window(wm):
    for window in wm.windows:
        screen = window.screen
        if screen is None:
            continue
        for area in screen.areas:
            if area.type == "VIEW_3D":
                return window, area
    return None, None


def report():
    print("SNAP_AFTER", bpy.context.scene.tool_settings.use_snap, flush=True)
    bpy.ops.wm.quit_blender()
    return None


def arm():
    wm = bpy.context.window_manager
    window, area = main_window(wm)
    print("MAIN_WINDOW", bool(window), "AREA", area.type if area else None, flush=True)
    if window is None:
        bpy.ops.wm.quit_blender()
        return None
    sidekeys.ALIVE["value"] = False
    try:
        with bpy.context.temp_override(window=window, screen=window.screen, area=area):
            bpy.ops.piebind.side_listener("INVOKE_DEFAULT")
        print("ARMED_MAIN", flush=True)
    except Exception as exc:
        print("ARM_FAIL", exc, flush=True)
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
    bpy.app.timers.register(arm, first_interval=0.5)
    return None


bpy.app.timers.register(setup, first_interval=1.5)