"""侧键实验：把条目放进 active keyconfig 的 3D View，看是否分发。"""

import bpy

import importlib

pkg = importlib.import_module("bl_ext.user_default.piebind")
cfg = pkg.core.config
ke = pkg.core.keymap


def report():
    print("SNAP_AFTER", bpy.context.scene.tool_settings.use_snap, flush=True)
    bpy.ops.wm.quit_blender()
    return None


def ready():
    print("SNAP_BEFORE", bpy.context.scene.tool_settings.use_snap, flush=True)
    print("READY", flush=True)
    bpy.app.timers.register(report, first_interval=6.0)
    return None


def move_items_to_active():
    wm = bpy.context.window_manager
    # 先清掉注册期写进 user keyconfig 的侧键条目
    for kc in wm.keyconfigs:
        for km in kc.keymaps:
            for kmi in list(km.keymap_items):
                if kmi.idname == "piebind.dispatch_side":
                    try:
                        km.keymap_items.remove(kmi)
                    except Exception:
                        pass
    active = wm.keyconfigs.active
    km = None
    for candidate in active.keymaps:
        if candidate.name == "3D View" and candidate.space_type == "VIEW_3D":
            km = candidate
            break
    if km is None:
        print("NO_ACTIVE_KEYMAP", flush=True)
        bpy.ops.wm.quit_blender()
        return None
    kmi = km.keymap_items.new("piebind.dispatch_side", "BUTTON4MOUSE", "PRESS")
    print("ACTIVE_ITEM", kmi.type, "kc=", active.name, flush=True)
    wm.keyconfigs.update()
    bpy.app.timers.register(ready, first_interval=1.0)
    return None


def setup():
    data = cfg.load()
    data["bindings"].append({
        "id": cfg.new_id("bd"),
        "enabled": True,
        "force_override": False,
        "keymap": {"name": "3D View", "space": "VIEW_3D", "region": "WINDOW"},
        "key": {"type": "BUTTON4MOUSE", "value": "PRESS"},
        "target": {
            "kind": "operator", "id": "wm.context_toggle",
            "props": {"data_path": "scene.tool_settings.use_snap"},
        },
    })
    cfg.save(data)
    print("BOUND", flush=True)
    bpy.app.timers.register(move_items_to_active, first_interval=0.8)
    return None


bpy.app.timers.register(setup, first_interval=1.5)