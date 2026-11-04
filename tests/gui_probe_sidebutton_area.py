"""侧键绑定位置实验：条目放进 3D View keymap 而不是 Window 层。"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
os.environ["PIEBIND_CONFIG_DIR"] = tempfile.mkdtemp(prefix="pb-side2-")

import bpy

import piebind
import piebind.config as cfg
import piebind.keymap_engine as ke


def report():
    print("SNAP_AFTER", bpy.context.scene.tool_settings.use_snap, flush=True)
    bpy.ops.wm.quit_blender()
    return None


def ready():
    print("SNAP_BEFORE", bpy.context.scene.tool_settings.use_snap, flush=True)
    print("READY", flush=True)
    bpy.app.timers.register(report, first_interval=6.0)
    return None


def setup():
    piebind.register()
    data = cfg.load()
    binding_id = cfg.new_id("bd")
    data["bindings"].append({
        "id": binding_id,
        "enabled": True,
        "force_override": False,
        "keymap": {"name": "3D View", "space": "VIEW_3D", "region": "WINDOW"},
        "key": {"type": "BUTTON4MOUSE", "value": "PRESS", "ctrl": False, "shift": False,
                "alt": False, "oskey": False, "any": False, "key_modifier": "NONE"},
        "target": {
            "kind": "operator", "id": "wm.context_toggle",
            "props": {"data_path": "scene.tool_settings.use_snap"},
        },
    })
    cfg.save(data)

    wm = bpy.context.window_manager
    kc = wm.keyconfigs.active
    km = None
    for candidate in kc.keymaps:
        if candidate.name == "3D View" and candidate.space_type == "VIEW_3D":
            km = candidate
            break
    if km is None:
        print("NO_KEYMAP", flush=True)
        bpy.ops.wm.quit_blender()
        return None
    kmi = km.keymap_items.new("piebind.dispatch", "BUTTON4MOUSE", "PRESS")
    kmi.properties.binding_id = binding_id
    wm.keyconfigs.update()
    print("ITEM_CREATED", km.name, kmi.type, flush=True)
    bpy.app.timers.register(ready, first_interval=1.5)
    return None


bpy.app.timers.register(setup, first_interval=1.2)