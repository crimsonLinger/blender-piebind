"""验证「保存绑定」链路（之前 split_keymap_identifier 未定义会直接报错）。

用法（GUI，在项目根目录）：blender --python tests/gui_probe_binding_save.py
产物：`.probe\\binding_saved.png`
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE_DIR = os.path.join(ROOT, ".probe")
os.makedirs(PROBE_DIR, exist_ok=True)
os.environ["PIEBIND_CONFIG_DIR"] = os.path.join(PROBE_DIR, "cfg_binding")

import bpy  # noqa: E402

SHOT = os.path.join(PROBE_DIR, "binding_saved.png")


def log(*args):
    print("[PROBE]", *args, flush=True)


def pkg():
    import importlib

    return importlib.import_module("bl_ext.user_default.piebind")


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


def step_open():
    wm = bpy.context.window_manager
    wm.piebind_tab = "bindings"
    wm.piebind_show_new = True
    try:
        bpy.ops.preferences.addon_show(module="bl_ext.user_default.piebind")
        log("PREFS OK")
    except Exception as exc:
        log("PREFS FAIL", type(exc).__name__, exc)
    return None


def step_save():
    wm = bpy.context.window_manager
    core = pkg().core
    wm.piebind_keymap = core.keyspec.make_keymap_identifier("3D View", "VIEW_3D", "WINDOW")
    wm.piebind_key_json = json.dumps({
        "type": "F8", "value": "PRESS", "ctrl": True, "shift": False,
        "alt": False, "oskey": False, "any": False, "key_modifier": "NONE",
    })
    wm.piebind_target_kind = "operator"
    wm.piebind_op_choice = "wm.context_toggle"
    wm.piebind_force_override = False
    wm.piebind_restrict_view3d = True
    try:
        result = bpy.ops.piebind.create_binding()
        log("CREATE", result)
    except Exception as exc:
        log("CREATE FAIL", type(exc).__name__, exc)
    data = core.config.load()
    log("BINDINGS", len(data["bindings"]),
        data["bindings"][-1] if data["bindings"] else None)
    tag_redraw()
    return None


def step_menu():
    try:
        result = bpy.ops.wm.call_menu(name="PIEBIND_MT_keymaps")
        log("KEYMAP MENU", result)
    except Exception as exc:
        log("KEYMAP MENU FAIL", type(exc).__name__, exc)
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
        log("SHOT OK", SHOT)
    except Exception as exc:
        log("SHOT FAIL", type(exc).__name__, exc)
    return None


def finish():
    try:
        pkg().core.keymap.unapply()
        log("UNAPPLIED")
    except Exception as exc:
        log("UNAPPLY FAIL", type(exc).__name__, exc)
    bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(step_open, first_interval=2.0)
bpy.app.timers.register(step_save, first_interval=4.0)
bpy.app.timers.register(step_menu, first_interval=6.0)
bpy.app.timers.register(step_shot, first_interval=8.0)
bpy.app.timers.register(finish, first_interval=10.0)