"""冒烟：在真实窗口里打开「参数预设」下拉，确认菜单 draw 不报错。

用法（GUI，在项目根目录）：blender --python tests/gui_probe_preset_menu.py
"""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE_DIR = os.path.join(ROOT, ".probe")
os.makedirs(PROBE_DIR, exist_ok=True)
os.environ["PIEBIND_CONFIG_DIR"] = os.path.join(PROBE_DIR, "cfg_menu")

import bpy  # noqa: E402


def log(*args):
    print("[PROBE]", *args, flush=True)


def step_seed():
    from bl_ext.user_default.piebind.core import config as cfg

    data = cfg.default_data()
    pie = cfg.create_pie(data, "视图")
    cfg.save(data)
    wm = bpy.context.window_manager
    wm.piebind_pie = pie["id"]
    wm.piebind_slot_pos = "N"
    wm.piebind_op_choice = "view3d.view_axis"
    log("SEEDED", pie["id"])
    return None


def step_open_prefs():
    try:
        bpy.ops.preferences.addon_show(module="bl_ext.user_default.piebind")
        bpy.context.window_manager.piebind_tab = "pies"
        log("PREFS OK")
    except Exception as exc:
        log("PREFS FAIL", type(exc).__name__, exc)
    return None


def step_open_menu():
    try:
        result = bpy.ops.wm.call_menu(name="PIEBIND_MT_slot_presets")
        log("MENU", result)
    except Exception as exc:
        log("MENU FAIL", type(exc).__name__, exc)
    return None


def step_close_menu():
    try:
        # 关掉弹层：把 ESC 事件送给当前弹窗
        bpy.ops.wm.call_menu(name="PIEBIND_MT_slot_presets")
    except Exception:
        pass
    return None


def finish():
    log("DONE")
    bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(step_seed, first_interval=1.5)
bpy.app.timers.register(step_open_prefs, first_interval=3.0)
bpy.app.timers.register(step_open_menu, first_interval=5.0)
bpy.app.timers.register(finish, first_interval=8.0)