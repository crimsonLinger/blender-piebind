"""验证：饼编辑区改完字段后，0.6s 自动写进槽位（不需要「写入槽位」按钮）。

用法（GUI，在项目根目录）：blender --python tests/gui_probe_autosave.py
产物：`.probe\\autosave.png`
"""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE_DIR = os.path.join(ROOT, ".probe")
os.makedirs(PROBE_DIR, exist_ok=True)
os.environ["PIEBIND_CONFIG_DIR"] = os.path.join(PROBE_DIR, "cfg_autosave")

import bpy  # noqa: E402

SHOT = os.path.join(PROBE_DIR, "autosave.png")


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
    pie = cfg.create_pie(data, "自动保存")
    cfg.save(data)
    wm = bpy.context.window_manager
    wm.piebind_pie = pie["id"]
    wm.piebind_slot_pos = "N"
    log("SEEDED", pie["id"])
    return None


def step_open():
    try:
        bpy.ops.preferences.addon_show(module="bl_ext.user_default.piebind")
        bpy.context.window_manager.piebind_tab = "pies"
        log("PREFS OK")
    except Exception as exc:
        log("PREFS FAIL", type(exc).__name__, exc)
    return None


def step_edit():
    wm = bpy.context.window_manager
    wm.piebind_op_choice = "view3d.view_axis"
    wm.piebind_slot_text = "顶视图"
    wm.piebind_slot_props = '{"type": "TOP"}'
    log("EDITED", wm.piebind_op_choice, wm.piebind_slot_props)
    tag_redraw()
    return None


def step_check():
    from bl_ext.user_default.piebind.core import config as cfg

    data = cfg.load()
    pie = data["pies"][0]
    log("SLOT N", pie["slots"].get("N"))
    log("STATUS", getattr(bpy.context.window_manager, "piebind_status", ""))
    return None


def step_shot():
    win = prefs_window()
    if win is None:
        log("NO PREFS WINDOW")
        return None
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
                ctypes.windll.user32.MoveWindow(hwnd, 0, 0, 1080, 1040, True)
                break
    except Exception:
        pass
    tag_redraw()
    return None


def step_shot2():
    win = prefs_window()
    if win is None:
        return None
    area = win.screen.areas[0] if win.screen and win.screen.areas else None
    region = None
    if area is not None:
        for reg in area.regions:
            if reg.type == "WINDOW":
                region = reg
                break
    for kwargs in (
        {"window": win, "area": area, "region": region},
        {"area": area, "region": region},
        {},
    ):
        try:
            with bpy.context.temp_override(**{k: v for k, v in kwargs.items() if v is not None}):
                bpy.ops.screen.screenshot_area(filepath=SHOT)
            log("SHOT OK", SHOT, "override=", [k for k, v in kwargs.items() if v is not None])
            return None
        except Exception as exc:
            log("SHOT FAIL", [k for k, v in kwargs.items() if v is not None],
                type(exc).__name__, exc)
    try:
        tag_redraw()
        with bpy.context.temp_override(window=win):
            bpy.ops.screen.screenshot(filepath=SHOT)
        log("SHOT OK (window)", SHOT)
    except Exception as exc:
        log("SHOT FAIL (window)", type(exc).__name__, exc)
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
bpy.app.timers.register(step_edit, first_interval=5.0)
bpy.app.timers.register(step_check, first_interval=7.5)
bpy.app.timers.register(step_shot, first_interval=8.5)
bpy.app.timers.register(step_shot2, first_interval=10.0)
bpy.app.timers.register(finish, first_interval=11.5)