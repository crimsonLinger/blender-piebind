"""验证：用 PieBind 饼菜单放 4 个视图方位（顶/左/右/正）是什么效果。

1) 在临时配置里写一个「视图」饼（N=顶 W=左 E=右 S=正）；
2) 在 3D 视图上下文里直接执行 view3d.view_axis，确认方位值生效；
3) 弹出这个饼并截图。

用法（GUI，在项目根目录）：blender --python tests/gui_probe_views.py
产物：`.probe/view_pie.png`
"""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE_DIR = os.path.join(ROOT, ".probe")
os.makedirs(PROBE_DIR, exist_ok=True)
os.environ["PIEBIND_CONFIG_DIR"] = os.path.join(PROBE_DIR, "cfg_views")

import bpy  # noqa: E402

SHOT = os.path.join(PROBE_DIR, "view_pie.png")


def log(*args):
    print("[PROBE]", *args, flush=True)


def view3d():
    wm = bpy.context.window_manager
    win = bpy.context.window or (wm.windows[0] if wm.windows else None)
    if win is None or win.screen is None:
        return None
    for area in win.screen.areas:
        if area.type == "VIEW_3D":
            return area
    return None


def step_axis():
    area = view3d()
    if area is None:
        log("NO VIEW3D")
        return None
    region = next((r for r in area.regions if r.type == "WINDOW"), None)
    space = area.spaces.active
    rv3d = space.region_3d
    with bpy.context.temp_override(area=area, region=region, space_data=space):
        before = rv3d.view_perspective
        result = bpy.ops.view3d.view_axis(type="TOP")
        after = rv3d.view_perspective
        quat = tuple(round(v, 3) for v in rv3d.view_rotation)
    log("AXIS TOP", result, "perspective", before, "->", after, "quat", quat)
    return None


def step_seed():
    from bl_ext.user_default.piebind.core import config as cfg

    data = cfg.default_data()
    pie = cfg.create_pie(data, "视图")
    for pos, axis, text in (
        ("N", "TOP", "顶视图"),
        ("W", "LEFT", "左视图"),
        ("E", "RIGHT", "右视图"),
        ("S", "FRONT", "正视图"),
    ):
        cfg.set_slot(data, pie["id"], pos, {
            "kind": "operator", "idname": "view3d.view_axis", "text": text,
            "icon": "NONE", "props": {"type": axis},
        })
    cfg.save(data)
    binding = {
        "id": cfg.new_id("bd"),
        "enabled": True,
        "force_override": False,
        "keymap": {"name": "3D View", "space": "VIEW_3D", "region": "WINDOW"},
        "key": {"type": "F9", "value": "PRESS"},
        "target": {"kind": "pie", "id": pie["id"], "props": {}},
    }
    data["bindings"].append(binding)
    cfg.save(data)
    log("SEEDED", pie["id"], "binding", binding["id"])
    bpy.context.window_manager.piebind_pie = pie["id"]
    globals()["VIEW_BINDING_ID"] = binding["id"]
    return None


def step_open_pie():
    binding_id = globals().get("VIEW_BINDING_ID", "")
    try:
        result = bpy.ops.piebind.dispatch(binding_id=binding_id)
        log("OPEN PIE", result)
    except Exception as exc:
        log("OPEN PIE FAIL", type(exc).__name__, exc)
    return None


def step_shot():
    try:
        bpy.ops.screen.screenshot(filepath=SHOT)
        log("SHOT OK", SHOT)
    except Exception as exc:
        log("SHOT FAIL", type(exc).__name__, exc)
    return None


def finish():
    bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(step_axis, first_interval=2.0)
bpy.app.timers.register(step_seed, first_interval=3.5)
bpy.app.timers.register(step_open_pie, first_interval=5.0)
bpy.app.timers.register(step_shot, first_interval=7.0)
bpy.app.timers.register(finish, first_interval=9.0)