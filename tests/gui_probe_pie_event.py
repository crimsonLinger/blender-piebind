"""用真实鼠标事件触发饼菜单，检查排布。"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
os.environ["PIEBIND_CONFIG_DIR"] = tempfile.mkdtemp(prefix="pb-pie-ev-")

import bpy

OUT = os.path.join(tempfile.gettempdir(), "piebind_gui_probe")
SHOT = os.path.join(OUT, "pie_event.png")
os.makedirs(OUT, exist_ok=True)

import piebind
import piebind.config as cfg
import piebind.pie as pie_mod


class TMP_OT_trigger(bpy.types.Operator):
    bl_idname = "tmp.trigger"
    bl_label = "trigger"

    def invoke(self, context, event):
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type == "MOUSEMOVE":
            print("MOUSE EVENT", event.mouse_x, event.mouse_y, flush=True)
            pie_mod.PIE_STATE["pie_id"] = self.pie_id
            bpy.ops.wm.call_menu_pie("INVOKE_DEFAULT", name=pie_mod.PIE_MENU_ID)
            return {"FINISHED"}
        return {"RUNNING_MODAL"}


def shot():
    try:
        bpy.ops.screen.screenshot(filepath=SHOT)
        print("SHOT OK", SHOT, flush=True)
    except Exception as exc:
        print("SHOT FAIL", exc, flush=True)
    bpy.ops.wm.quit_blender()
    return None


def start():
    import importlib
    data = cfg.load()
    pie = data["pies"][0] if data.get("pies") else None
    print("PIE", pie["id"] if pie else None, flush=True)
    bpy.ops.tmp.trigger("INVOKE_DEFAULT")
    bpy.app.timers.register(shot, first_interval=3.0)
    return None


def setup():
    piebind.register()
    bpy.utils.register_class(TMP_OT_trigger)
    data = cfg.load()
    pie = cfg.create_pie(data, "模式饼")
    for pos, mode, text in (("W", "EDIT", "编辑模式"), ("E", "OBJECT", "物体模式"),
                            ("N", "SCULPT", "雕刻模式"), ("S", "POSE", "姿态模式")):
        cfg.set_slot(data, pie["id"], pos, {
            "kind": "operator", "idname": "object.mode_set", "text": text,
            "icon": "NONE", "props": {"mode": mode},
        })
    cfg.save(data)
    bpy.app.timers.register(start, first_interval=1.5)
    return None


bpy.app.timers.register(setup, first_interval=1.2)