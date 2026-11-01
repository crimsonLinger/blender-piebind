"""打开 PieBind 偏好设置并截图，用于核对面板渲染。"""

import os
import tempfile

import bpy

OUT = os.path.join(tempfile.gettempdir(), "piebind_gui_probe")
os.makedirs(OUT, exist_ok=True)
SHOT = os.path.join(OUT, "panel.png")


def take_shot():
    try:
        bpy.ops.screen.screenshot(filepath=SHOT)
        print("SHOT OK", SHOT, flush=True)
    except Exception as exc:
        print("SHOT FAIL", exc, flush=True)
    bpy.ops.wm.quit_blender()
    return None


def open_prefs():
    try:
        bpy.ops.preferences.addon_show(module="bl_ext.user_default.piebind")
        print("PREFS OPENED", flush=True)
    except Exception as exc:
        print("PREFS FAIL", exc, flush=True)
    bpy.app.timers.register(take_shot, first_interval=2.5)
    return None


bpy.app.timers.register(open_prefs, first_interval=1.2)