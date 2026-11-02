"""验证侧键（XBUTTON）能否被捕获。"""

import bpy

RESULT = []


def finish():
    wm = bpy.context.window_manager
    print("CAPTURE_LABEL", repr(wm.piebind_capture_label), flush=True)
    print("KEY_JSON", wm.piebind_key_json, flush=True)
    bpy.ops.wm.quit_blender()
    return None


def start_capture():
    try:
        bpy.ops.piebind.capture_key("INVOKE_DEFAULT")
        print("CAPTURE_STARTED", flush=True)
    except Exception as exc:
        print("CAPTURE_FAIL", exc, flush=True)
    bpy.app.timers.register(finish, first_interval=4.0)
    return None


def setup():
    try:
        bpy.ops.preferences.addon_enable(module="bl_ext.user_default.piebind")
        print("ENABLED", flush=True)
    except Exception as exc:
        print("ENABLE_FAIL", exc, flush=True)
    bpy.app.timers.register(start_capture, first_interval=3.5)
    return None


bpy.app.timers.register(setup, first_interval=1.2)