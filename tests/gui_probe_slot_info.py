"""截图验证：槽位编辑区显示「现有功能 + 参数 JSON」，并可一键载入。

用法（GUI，在项目根目录）：blender --python tests/gui_probe_slot_info.py
产物：`.probe/slot_info.png`
"""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE_DIR = os.path.join(ROOT, ".probe")
os.makedirs(PROBE_DIR, exist_ok=True)
os.environ["PIEBIND_CONFIG_DIR"] = os.path.join(PROBE_DIR, "cfg_slotinfo")

import bpy  # noqa: E402

SHOT = os.path.join(PROBE_DIR, "slot_info.png")


def log(*args):
    print("[PROBE]", *args, flush=True)


def prefs_window():
    for win in bpy.context.window_manager.windows:
        if win.screen and win.screen.name != "Layout":
            return win
    return None


def tag_redraw():
    for win in bpy.context.window_manager.windows:
        if not win.screen:
            continue
        for area in win.screen.areas:
            try:
                area.tag_redraw()
            except Exception:
                pass


def step_seed():
    from bl_ext.user_default.piebind.core import config as cfg

    data = cfg.default_data()
    pie = cfg.create_pie(data, "模式选择")
    cfg.set_slot(data, pie["id"], "N", {
        "kind": "operator", "idname": "object.mode_set", "text": "物体模式",
        "icon": "NONE", "props": {"mode": "OBJECT"},
    })
    cfg.set_slot(data, pie["id"], "S", {
        "kind": "operator", "idname": "object.mode_set", "text": "编辑模式",
        "icon": "NONE", "props": {"mode": "EDIT"},
    })
    cfg.save(data)
    wm = bpy.context.window_manager
    wm.piebind_pie = pie["id"]
    log("SEEDED", pie["id"])
    return None


def step_open():
    try:
        bpy.ops.preferences.addon_show(module="bl_ext.user_default.piebind")
        log("PREFS OK")
    except Exception as exc:
        log("PREFS FAIL", type(exc).__name__, exc)
    return None


def step_select_slot():
    wm = bpy.context.window_manager
    wm.piebind_tab = "pies"
    try:
        bpy.ops.piebind.select_slot(pos="S")
        log("SELECTED S", "op=", wm.piebind_op_choice,
            "props=", wm.piebind_slot_props, "text=", wm.piebind_slot_text)
    except Exception as exc:
        log("SELECT FAIL", type(exc).__name__, exc)
    # 放大窗口 + 缩小界面，让整个编辑区进截图
    globals()["UI_SCALE"] = bpy.context.preferences.view.ui_scale
    bpy.context.preferences.view.ui_scale = 0.85
    try:
        import ctypes

        titles = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def _enum(hwnd, _lparam):
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            if buf.value:
                titles.append((hwnd, buf.value))
            return True

        ctypes.windll.user32.EnumWindows(_enum, 0)
        for hwnd, title in titles:
            if "偏好设置" in title or "Preferences" in title:
                ctypes.windll.user32.MoveWindow(hwnd, 60, 40, 1100, 1150, True)
                break
    except Exception as exc:
        log("RESIZE FAIL", exc)
    tag_redraw()
    return None


def step_resize():
    try:
        import ctypes

        titles = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def _enum(hwnd, _lparam):
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            if buf.value:
                titles.append((hwnd, buf.value))
            return True

        ctypes.windll.user32.EnumWindows(_enum, 0)
        for hwnd, title in titles:
            if "偏好设置" in title or "Preferences" in title:
                ctypes.windll.user32.MoveWindow(hwnd, 20, 10, 1060, 1100, True)
                log("RESIZED", title)
                break
        else:
            log("NO PREFS TITLE", [t for _h, t in titles if "Blender" in t][:3])
    except Exception as exc:
        log("RESIZE FAIL", type(exc).__name__, exc)
    return None


def step_shot():
    win = prefs_window()
    if win is None:
        log("NO PREFS WINDOW")
        return None
    log("WINDOW SIZE", win.width, win.height)
    try:
        tag_redraw()
        with bpy.context.temp_override(window=win):
            bpy.ops.screen.screenshot(filepath=SHOT)
        log("SHOT OK", SHOT, "size=", win.width, win.height)
    except Exception as exc:
        log("SHOT FAIL", type(exc).__name__, exc)
    return None


def finish():
    original = globals().get("UI_SCALE")
    if original is not None:
        try:
            bpy.context.preferences.view.ui_scale = original
        except Exception:
            pass
    bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(step_seed, first_interval=2.0)
bpy.app.timers.register(step_open, first_interval=3.5)
bpy.app.timers.register(step_select_slot, first_interval=5.0)
bpy.app.timers.register(step_resize, first_interval=6.5)
bpy.app.timers.register(step_shot, first_interval=9.0)
bpy.app.timers.register(finish, first_interval=11.5)