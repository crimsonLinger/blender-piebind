"""打开偏好设置窗口并单独截图（带 context override）。"""

import os
import tempfile

import bpy

OUT = os.path.join(tempfile.gettempdir(), "piebind_gui_probe")
os.makedirs(OUT, exist_ok=True)
SHOT = os.path.join(OUT, "panel2.png")


def take_shot():
    wm = bpy.context.window_manager
    target = None
    for win in wm.windows:
        screen = win.screen
        if screen and screen.name != "Layout":
            target = win
            break
    if target is None:
        print("NO PREFS WINDOW", [w.screen.name if w.screen else None for w in wm.windows], flush=True)
        bpy.ops.wm.quit_blender()
        return None
    try:
        with bpy.context.temp_override(window=target, screen=target.screen):
            bpy.ops.screen.screenshot(filepath=SHOT)
        print("SHOT OK", SHOT, flush=True)
    except Exception as exc:
        print("SHOT FAIL", type(exc).__name__, exc, flush=True)
    bpy.ops.wm.quit_blender()
    return None


def open_prefs():
    try:
        bpy.ops.preferences.addon_show(module="bl_ext.user_default.piebind")
        print("PREFS OPENED", flush=True)
    except Exception as exc:
        print("PREFS FAIL", exc, flush=True)
    bpy.app.timers.register(take_shot, first_interval=3.0)
    return None


bpy.app.timers.register(open_prefs, first_interval=1.5)