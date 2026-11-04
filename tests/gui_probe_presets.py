"""验证：槽位编辑器的「参数预设」链路（选操作符 → 套预设 → 写入槽位）。

用法（GUI，在项目根目录）：blender --python tests/gui_probe_presets.py
产物：`.probe/slot_presets.png`
"""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE_DIR = os.path.join(ROOT, ".probe")
os.makedirs(PROBE_DIR, exist_ok=True)
os.environ["PIEBIND_CONFIG_DIR"] = os.path.join(PROBE_DIR, "cfg_presets")

import bpy  # noqa: E402

SHOT = os.path.join(PROBE_DIR, "slot_presets.png")


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


def step_seed_open():
    from bl_ext.user_default.piebind.core import config as cfg

    data = cfg.default_data()
    pie = cfg.create_pie(data, "视图")
    cfg.save(data)
    log("SEEDED", pie["id"])
    bpy.context.window_manager.piebind_pie = pie["id"]
    try:
        bpy.ops.preferences.addon_show(module="bl_ext.user_default.piebind")
    except Exception as exc:
        log("PREFS FAIL", type(exc).__name__, exc)
        bpy.ops.wm.quit_blender()
    return None


def step_fill():
    from bl_ext.user_default.piebind.core import config as cfg

    wm = bpy.context.window_manager
    wm.piebind_tab = "pies"
    wm.piebind_slot_pos = "N"
    wm.piebind_op_choice = "view3d.view_axis"
    wm.piebind_slot_text = ""
    wm.piebind_slot_props = ""
    result = bpy.ops.piebind.apply_slot_preset(
        op_id="view3d.view_axis", props_json='{"type": "TOP"}', slot_text="顶视图")
    log("PRESET", result, "props=", wm.piebind_slot_props, "text=", wm.piebind_slot_text)
    added = bpy.ops.piebind.add_slot()
    log("ADD", added)
    pie = cfg.load()["pies"][0]
    log("SLOT N", pie["slots"].get("N"))
    # 临时缩小界面 + 放大窗口，让槽位编辑区进得了截图（收尾会还原）
    globals()["UI_SCALE"] = bpy.context.preferences.view.ui_scale
    bpy.context.preferences.view.ui_scale = 0.85
    log("UI_SCALE", globals()["UI_SCALE"], "->", bpy.context.preferences.view.ui_scale)
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
                log("RESIZED", title)
                break
    except Exception as exc:
        log("RESIZE FAIL", type(exc).__name__, exc)
    tag_redraw()
    return None


def step_shot():
    win = prefs_window()
    if win is None:
        log("NO PREFS WINDOW")
        return None
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
            log("UI_SCALE restored", original)
        except Exception as exc:
            log("UI_SCALE RESTORE FAIL", exc)
    bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(step_seed_open, first_interval=2.0)
bpy.app.timers.register(step_fill, first_interval=4.5)
bpy.app.timers.register(step_shot, first_interval=7.0)
bpy.app.timers.register(finish, first_interval=9.0)