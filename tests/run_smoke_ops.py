"""冒烟：把每个操作符、每个菜单、四个页签都实际跑一遍。

用途：找出「写了但从来没执行过」的路径里的崩溃（NameError、非法图标、空数据等）。

用法（在项目根目录）：
  blender -b --factory-startup --python-exit-code 1 --python tests/run_smoke_ops.py

退出码：有 FAIL 时为 1。
"""

import json
import os
import sys
import tempfile
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ["PIEBIND_CONFIG_DIR"] = tempfile.mkdtemp(prefix="piebind-smoke-")

import bpy  # noqa: E402

import piebind  # noqa: E402
from piebind import api  # noqa: E402
from piebind.core import config, keymap as ke, keyspec, pies as pie  # noqa: E402
from piebind.ui import prefs as prefs_ui  # noqa: E402

RESULTS = []
TMP = tempfile.mkdtemp(prefix="piebind-smoke-files-")


# ---------------------------------------------------------------- 桩布局
class StubItem:
    def __init__(self, recorder, kind, name):
        self._recorder = recorder
        self._kind = kind
        self._name = name


class StubLayout:
    def __init__(self, recorder):
        self._recorder = recorder
        self.scale_y = 1.0

    # 容器：返回新的布局（共用同一个记录器）
    def box(self):
        return StubLayout(self._recorder)

    def column(self, align=False, **kwargs):
        return StubLayout(self._recorder)

    def row(self, align=False, **kwargs):
        return StubLayout(self._recorder)

    def split(self, factor=0.5, align=False, **kwargs):
        return StubLayout(self._recorder)

    def grid_flow(self, **kwargs):
        return StubLayout(self._recorder)

    def menu_pie(self, **kwargs):
        self._recorder.append(("menu_pie", ""))
        return StubLayout(self._recorder)

    # 叶子
    def operator(self, idname, text="", icon="", **kwargs):
        self._recorder.append(("op", idname))
        return StubItem(self._recorder, "op", idname)

    def menu(self, idname, text="", icon="", **kwargs):
        self._recorder.append(("menu", idname))
        return StubItem(self._recorder, "menu", idname)

    def label(self, text="", icon="", **kwargs):
        self._recorder.append(("label", text))

    def prop(self, data, name, text="", **kwargs):
        self._recorder.append(("prop", name))

    def separator(self, **kwargs):
        self._recorder.append(("sep", ""))

    def template_list(self, *args, **kwargs):
        self._recorder.append(("tlist", ""))


class StubHost:
    def __init__(self):
        self.records = []
        self.layout = StubLayout(self.records)


# ---------------------------------------------------------------- 夹具
def fixture():
    data = config.default_data()
    pie_doc = config.create_pie(data, "冒烟饼")
    config.set_slot(data, pie_doc["id"], "N", {
        "kind": "operator", "idname": "view3d.view_axis", "text": "顶视图",
        "icon": "NONE", "props": {"type": "TOP"},
    })
    empty = config.create_pie(data, "空饼")
    binding = {
        "id": "bd_smoke", "enabled": True, "force_override": False,
        "keymap": {"name": "3D View", "space": "VIEW_3D", "region": "WINDOW"},
        "key": {"type": "F8", "value": "PRESS", "ctrl": True, "shift": False,
                "alt": False, "oskey": False, "any": False, "key_modifier": "NONE"},
        "target": {"kind": "pie", "id": pie_doc["id"], "props": {}},
    }
    data["bindings"].append(binding)
    config.save(data)
    return data, pie_doc["id"], empty["id"]


def run(name, fn):
    print(f"[RUN ] {name}", flush=True)
    try:
        result = fn()
        RESULTS.append(("OK", name, repr(result)[:100]))
        print(f"[OK  ] {name} :: {result}", flush=True)
    except Exception as exc:  # noqa: BLE001
        RESULTS.append(("FAIL", name, f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"))
        print(f"[FAIL] {name} :: {type(exc).__name__}: {exc}", flush=True)


def skip(name, reason):
    RESULTS.append(("SKIP", name, reason))


def expect_error(name, fn, needle=""):
    """预期：操作符报错并取消（bpy.ops 会抛 RuntimeError）。"""
    print(f"[RUN ] {name}", flush=True)
    try:
        fn()
    except RuntimeError as exc:
        text = str(exc)
        if needle and needle not in text:
            RESULTS.append(("FAIL", name, f"报错信息不符：[{text}] 未包含 [{needle}]"))
            print(f"[FAIL] {name} :: 报错信息不符：{text}", flush=True)
        else:
            RESULTS.append(("OK", name, f"按预期报错：{text[:80]}"))
            print(f"[OK  ] {name} :: 按预期报错", flush=True)
    except Exception as exc:  # noqa: BLE001
        RESULTS.append(("FAIL", name, f"非预期异常：{type(exc).__name__}: {exc}"))
        print(f"[FAIL] {name} :: 非预期异常 {type(exc).__name__}: {exc}", flush=True)
    else:
        RESULTS.append(("FAIL", name, "预期报错，但操作符成功返回"))
        print(f"[FAIL] {name} :: 预期报错但没有报错", flush=True)


def smoke_operators():
    wm = bpy.context.window_manager

    def reset():
        return fixture()

    run("apply", lambda: (reset(), bpy.ops.piebind.apply())[1])
    run("unapply", lambda: (reset(), bpy.ops.piebind.unapply())[1])

    def create_binding():
        reset()
        wm.piebind_keymap = keyspec.make_keymap_identifier("3D View", "VIEW_3D", "WINDOW")
        wm.piebind_key_json = json.dumps({
            "type": "F7", "value": "PRESS", "ctrl": True, "shift": False,
            "alt": False, "oskey": False, "any": False, "key_modifier": "NONE"})
        wm.piebind_target_kind = "operator"
        wm.piebind_op_choice = "wm.context_toggle"
        wm.piebind_force_override = False
        wm.piebind_restrict_view3d = True
        return bpy.ops.piebind.create_binding()

    run("create_binding", create_binding)
    run("delete_binding", lambda: (reset(), bpy.ops.piebind.delete_binding(binding_id="bd_smoke"))[1])
    run("toggle_binding", lambda: (reset(), bpy.ops.piebind.toggle_binding(binding_id="bd_smoke"))[1])
    run("check_binding", lambda: (reset(), bpy.ops.piebind.check_binding(binding_id="bd_smoke"))[1])

    def create_pie():
        reset()
        wm.piebind_new_pie_label = "冒烟新饼"
        return bpy.ops.piebind.create_pie()

    run("create_pie", create_pie)
    expect_error("rename_pie(不存在的饼)",
                 lambda: bpy.ops.piebind.rename_pie(pie_id="pie_nope", label="改名"),
                 "饼不存在")

    def delete_missing():
        reset()
        wm.piebind_pie = ""
        return bpy.ops.piebind.delete_pie(pie_id="")

    expect_error("delete_pie(未选中)", delete_missing, "请先选择一个饼")

    def rename_real():
        _data, pie_id, _empty = reset()
        return bpy.ops.piebind.rename_pie(pie_id=pie_id, label="改名后")

    run("rename_pie(真实 id)", rename_real)

    def delete_real():
        _data, _pie, empty_id = reset()
        return bpy.ops.piebind.delete_pie(pie_id=empty_id)

    run("delete_pie(真实 id)", delete_real)

    def add_slot():
        _data, pie_id, _empty = reset()
        wm.piebind_pie = pie_id
        wm.piebind_slot_pos = "E"
        wm.piebind_op_choice = "view3d.view_axis"
        wm.piebind_slot_text = "右视图"
        wm.piebind_slot_props = '{"type": "RIGHT"}'
        return bpy.ops.piebind.add_slot()

    run("add_slot", add_slot)

    def remove_slot():
        _data, pie_id, _empty = reset()
        return bpy.ops.piebind.remove_slot(pie_id=pie_id, pos="N")

    run("remove_slot", remove_slot)
    run("select_slot", lambda: bpy.ops.piebind.select_slot(pos="SE"))

    def load_slot():
        _data, pie_id, _empty = reset()
        wm.piebind_pie = pie_id
        wm.piebind_slot_pos = "N"
        return bpy.ops.piebind.load_slot()

    run("load_slot", load_slot)

    def select_pie():
        _data, pie_id, _empty = reset()
        return bpy.ops.piebind.select_pie(pie_id=pie_id)

    run("select_pie", select_pie)
    run("pick_operator", lambda: bpy.ops.piebind.pick_operator(idname="mesh.bevel"))
    run("select_keymap",
        lambda: bpy.ops.piebind.select_keymap(
            identifier=keyspec.make_keymap_identifier("Mesh", "EMPTY", "WINDOW")))

    def apply_preset():
        reset()
        return bpy.ops.piebind.apply_slot_preset(
            op_id="view3d.view_axis", props_json='{"type": "TOP"}', slot_text="顶视图")

    run("apply_slot_preset", apply_preset)
    run("slot_missing", lambda: bpy.ops.piebind.slot_missing(slot_text="测试"))
    expect_error("dispatch(后台)", lambda: (reset(), bpy.ops.piebind.dispatch(binding_id="bd_smoke"))[1],
                 "后台模式下无法打开饼菜单")
    run("save_defaults", lambda: bpy.ops.piebind.save_defaults())
    run("load_defaults", lambda: bpy.ops.piebind.load_defaults())
    run("refresh_health", lambda: bpy.ops.piebind.refresh_health())
    run("copy_diagnostics", lambda: bpy.ops.piebind.copy_diagnostics())
    run("arm_side_listener", lambda: bpy.ops.piebind.arm_side_listener())

    def export_config():
        return bpy.ops.piebind.export_config(filepath=os.path.join(TMP, "cfg.json"))

    def import_config():
        return bpy.ops.piebind.import_config(filepath=os.path.join(TMP, "cfg.json"))

    def export_diag():
        return bpy.ops.piebind.export_diagnostics(filepath=os.path.join(TMP, "diag.json"))

    run("export_config", export_config)
    run("import_config", import_config)
    run("export_diagnostics", export_diag)
    run("open_config_dir", lambda: bpy.ops.piebind.open_config_dir())

    # 需要真实窗口/modal，headless 下跳过
    skip("capture_key", "modal，需 GUI")
    skip("side_listener", "modal，需 GUI")
    skip("test_pie", "invoke → call_menu_pie，需 GUI")
    skip("call_pie", "invoke → call_menu_pie，需 GUI")


def smoke_menus():
    wm = bpy.context.window_manager
    _data, pie_id, _empty = fixture()
    wm.piebind_pie = pie_id
    wm.piebind_op_choice = "view3d.view_axis"
    wm.piebind_slot_props = '{"type": "TOP"}'
    pipe_state = dict(pie.PIE_STATE)
    pie.PIE_STATE["pie_id"] = pie_id

    menus = [
        ("PIEBIND_MT_pie", pie.PIEBIND_MT_pie),
        ("PIEBIND_MT_pies", piebind.ops.PIEBIND_MT_pies),
        ("PIEBIND_MT_operators", piebind.ops.PIEBIND_MT_operators),
        ("PIEBIND_MT_keymaps", piebind.ops.PIEBIND_MT_keymaps),
        ("PIEBIND_MT_slot_presets", piebind.ops.PIEBIND_MT_slot_presets),
    ]
    for name, cls in menus:
        host = StubHost()
        try:
            cls.draw(host, bpy.context)
            RESULTS.append(("OK", f"menu {name}", f"{len(host.records)} 项"))
        except Exception as exc:  # noqa: BLE001
            RESULTS.append(("FAIL", f"menu {name}",
                            f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"))
    pie.PIE_STATE.update(pipe_state)


def smoke_panels():
    wm = bpy.context.window_manager
    for tab in ("bindings", "pies", "settings", "health"):
        wm.piebind_tab = tab
        host = StubHost()
        try:
            prefs_ui.draw_preferences(host, bpy.context)
            RESULTS.append(("OK", f"panel {tab}", f"{len(host.records)} 项"))
        except Exception as exc:  # noqa: BLE001
            RESULTS.append(("FAIL", f"panel {tab}",
                            f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"))


def main():
    piebind.register()
    try:
        smoke_operators()
        smoke_menus()
        smoke_panels()
    finally:
        try:
            piebind.unregister()
        except Exception:
            pass

    fails = [r for r in RESULTS if r[0] == "FAIL"]
    skips = [r for r in RESULTS if r[0] == "SKIP"]
    for status, name, detail in RESULTS:
        if status == "FAIL":
            print(f"[FAIL] {name}\n{detail}")
        else:
            print(f"[{status}] {name} :: {detail}")
    print(f"\nSMOKE: OK {len(RESULTS) - len(fails) - len(skips)} / FAIL {len(fails)} / SKIP {len(skips)}")
    if fails:
        raise SystemExit(1)


main()