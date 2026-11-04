"""诊断：饼菜单「命名 / 改名」的界面是否可用。

流程：造一个饼 → 打开偏好设置 → 切到「饼菜单」页签 → 截图 → 打开改对话框 → 截图 → 验证改名。

用法（GUI，在项目根目录）：
  blender --python tests/gui_probe_pie_name.py
产物：`.probe/pies_tab.png`、`.probe/pie_rename_dialog.png` + 控制台 [PROBE] 日志。
"""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE_DIR = os.path.join(ROOT, ".probe")
os.makedirs(PROBE_DIR, exist_ok=True)
os.environ["PIEBIND_CONFIG_DIR"] = os.path.join(PROBE_DIR, "cfg")

import bpy  # noqa: E402

SHOT_TAB = os.path.join(PROBE_DIR, "pies_tab.png")
SHOT_DLG = os.path.join(PROBE_DIR, "pie_rename_dialog.png")


def log(*args):
    print("[PROBE]", *args, flush=True)


def prefs_window():
    for win in bpy.context.window_manager.windows:
        screen = win.screen
        if screen and screen.name != "Layout":
            return win
    return None


def shot(path):
    win = prefs_window()
    if win is None:
        log("NO PREFS WINDOW")
        return False
    try:
        with bpy.context.temp_override(window=win):
            bpy.ops.screen.screenshot(filepath=path)
        log("SHOT OK", path)
        return True
    except Exception as exc:
        log("SHOT FAIL", type(exc).__name__, exc)
        return False


def tag_redraw():
    for win in bpy.context.window_manager.windows:
        screen = win.screen
        if not screen:
            continue
        for area in screen.areas:
            try:
                area.tag_redraw()
            except Exception:
                pass


def step_seed_and_open():
    from bl_ext.user_default.piebind.core import config as cfg

    data = cfg.default_data()
    created = cfg.create_pie(data, "模式选择")
    cfg.set_slot(data, created["id"], "W", {
        "kind": "operator", "idname": "object.mode_set", "text": "编辑模式",
        "icon": "NONE", "props": {"mode": "EDIT"},
    })
    cfg.set_slot(data, created["id"], "N", {
        "kind": "operator", "idname": "object.mode_set", "text": "物体模式",
        "icon": "NONE", "props": {"mode": "OBJECT"},
    })
    cfg.save(data)
    log("SEEDED", created["id"], created["label"])
    try:
        bpy.ops.preferences.addon_show(module="bl_ext.user_default.piebind")
        log("addon_show OK")
    except Exception as exc:
        log("addon_show FAIL", type(exc).__name__, exc)
        bpy.ops.wm.quit_blender()
    return None


def step_select():
    wm = bpy.context.window_manager
    from bl_ext.user_default.piebind.core import config as cfg

    pies = cfg.load().get("pies", [])
    wm.piebind_tab = "pies"
    wm.piebind_pie = pies[0]["id"] if pies else ""
    wm.piebind_new_pie_label = "新饼示例"
    log("SELECTED", wm.piebind_pie, "tab=", wm.piebind_tab)
    tag_redraw()
    return None


def step_shot_tab():
    shot(SHOT_TAB)
    return None


def step_open_dialog():
    from bl_ext.user_default.piebind.core import config as cfg

    pies = cfg.load().get("pies", [])
    if not pies:
        log("NO PIE FOR DIALOG")
        return None
    try:
        result = bpy.ops.piebind.rename_pie("INVOKE_DEFAULT", pie_id=pies[0]["id"])
        log("DIALOG INVOKE", result)
    except Exception as exc:
        log("DIALOG FAIL", type(exc).__name__, exc)
    return None


def step_shot_dialog():
    shot(SHOT_DLG)
    return None


def step_verify():
    from bl_ext.user_default.piebind.core import config as cfg

    wm = bpy.context.window_manager
    pie_id = cfg.load()["pies"][0]["id"]
    before = cfg.find_pie(cfg.load(), pie_id)["label"]
    result = bpy.ops.piebind.rename_pie(pie_id=pie_id, label="改名后")
    after = cfg.find_pie(cfg.load(), pie_id)["label"]
    log("RENAME before=", before, "result=", result, "after=", after,
        "status=", getattr(wm, "piebind_status", ""))
    return None


def finish():
    bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(step_seed_and_open, first_interval=2.0)
bpy.app.timers.register(step_select, first_interval=4.0)
bpy.app.timers.register(step_shot_tab, first_interval=6.5)
bpy.app.timers.register(step_open_dialog, first_interval=8.0)
bpy.app.timers.register(step_shot_dialog, first_interval=10.0)
bpy.app.timers.register(step_verify, first_interval=11.5)
bpy.app.timers.register(finish, first_interval=13.0)