"""Headless 端到端测试。

运行（在项目根目录）：
  blender -b --factory-startup --python-exit-code 1 --python tests/run_headless.py
"""

import json
import os
import sys
import tempfile
import time
import traceback

import bpy

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

CONFIG_DIR = tempfile.mkdtemp(prefix="piebind-test-")
os.environ["PIEBIND_CONFIG_DIR"] = CONFIG_DIR

import piebind  # noqa: E402
from piebind import api, config, keymap_engine as ke, ops  # noqa: E402
from piebind import pie as pie_mod  # noqa: E402

PASSED = []
FAILED = []


def check(name, condition, detail=""):
    if condition:
        PASSED.append(name)
        print(f"  PASS  {name}")
    else:
        FAILED.append(f"{name} :: {detail}")
        print(f"  FAIL  {name}  {detail}")


def section(title):
    print(f"\n== {title} ==")


def items_in(kc, spec, key=None, idname=None):
    km = ke.find_keymap(kc, spec)
    if km is None:
        return []
    out = []
    for item in km.keymap_items:
        if key is not None and not ke.combo_match(item, key):
            continue
        if idname is not None and item.idname != idname:
            continue
        out.append(item)
    return out


def main():
    piebind.register()

    section("配置读写")
    data = config.load()
    check("默认配置为空", data["pies"] == [] and data["bindings"] == [])
    pie = config.create_pie(data, "测试饼")
    config.set_slot(data, pie["id"], "W", {
        "kind": "operator", "idname": "mesh.bevel", "text": "倒角", "props": {},
    })
    config.save(data)
    reloaded = config.load()
    check("饼可持久化", len(reloaded["pies"]) == 1 and reloaded["pies"][0]["label"] == "测试饼")
    check("槽位可持久化", reloaded["pies"][0]["slots"]["W"]["idname"] == "mesh.bevel")

    section("饼命名")
    data = config.load()
    first = data["pies"][0]
    renamed = config.rename_pie(data, first["id"], "  模式饼  ")
    check("改名去掉首尾空格", renamed is not None and renamed["label"] == "模式饼", renamed)
    kept = config.rename_pie(data, first["id"], "   ")
    check("空名字保留原名", kept is not None and kept["label"] == "模式饼", kept)
    check("未知饼改名返回 None", config.rename_pie(data, "pie_nope", "x") is None)
    config.save(data)
    check("改名已落盘", config.load()["pies"][0]["label"] == "模式饼",
          config.load()["pies"][0].get("label"))
    dup_a = config.create_pie(data, "重名测试")
    dup_b = config.create_pie(data, "重名测试")
    check("新建重名自动加序号", (dup_a["label"], dup_b["label"]) == ("重名测试", "重名测试 2"),
          (dup_a["label"], dup_b["label"]))
    data["pies"] = [p for p in data["pies"] if p["id"] not in (dup_a["id"], dup_b["id"])]
    config.save(data)

    section("键位标签")
    label = ke.key_label({"type": "E", "alt": True, "shift": True})
    check("标签格式", label == "SHIFT+ALT+E", label)
    label = ke.key_label({"type": "ONE", "ctrl": True})
    check("数字键标签", label == "CTRL+1", label)
    check("侧键标签", ke.key_label({"type": "BUTTON4MOUSE"}) == "M4",
          ke.key_label({"type": "BUTTON4MOUSE"}))
    check("侧键解析", (ops.parse_key_text("m5") or {}).get("type") == "BUTTON5MOUSE",
          ops.parse_key_text("m5"))

    section("侧键匹配")
    check("同组合匹配", ke.same_combo({"type": "BUTTON4MOUSE"},
                                   {"type": "button4mouse", "value": "PRESS"}))
    check("修饰键不同不匹配", not ke.same_combo(
        {"type": "BUTTON4MOUSE", "ctrl": True}, {"type": "BUTTON4MOUSE"}))
    from piebind.ops import dispatch as dispatch_mod
    _side_data = {"bindings": [{
        "id": "bd_side", "enabled": True,
        "key": {"type": "BUTTON4MOUSE", "value": "PRESS"},
        "keymap": {"name": "3D View", "space": "VIEW_3D", "region": "WINDOW"},
        "target": {"kind": "operator", "id": "wm.context_toggle", "props": {}},
    }]}
    _hit = dispatch_mod.find_binding_for_key(
        _side_data, {"type": "BUTTON4MOUSE", "value": "PRESS"})
    check("按事件反查到侧键绑定", _hit is not None and _hit["id"] == "bd_side", _hit)
    _miss = dispatch_mod.find_binding_for_key(
        _side_data, {"type": "BUTTON5MOUSE", "value": "PRESS"})
    check("不同侧键不误匹配", _miss is None)

    section("图标合法性")
    import re as _re
    import pathlib as _pathlib
    _icons = {
        item.identifier
        for item in bpy.types.UILayout.bl_rna.functions["label"].parameters["icon"].enum_items
    }
    _root = _pathlib.Path(__file__).resolve().parent.parent.joinpath("src", "piebind")
    _bad = []
    for _path in _root.rglob("*.py"):
        _text = _path.read_text(encoding="utf-8")
        for _m in _re.finditer(r'icon\s*=\s*"([A-Z0-9_]+)"', _text):
            if _m.group(1) not in _icons:
                _rel = _path.relative_to(_root)
                _bad.append(f"{_rel}:{_text[:_m.start()].count(chr(10)) + 1}:{_m.group(1)}")
    check("源码中图标名全部合法", not _bad, _bad[:5])

    # 下拉数据里的图标（不是 icon="..." 字面量）也要能通过校验
    _bad_items = [key for key, _label, _desc in ops.ICON_ITEMS if key not in _icons]
    check("槽位图标选项全部合法", not _bad_items, _bad_items)
    from piebind.ui import widgets as _widgets
    _bad_sev = [v for v in _widgets.SEVERITY_ICON.values() if v not in _icons]
    check("冲突徽标图标全部合法", not _bad_sev, _bad_sev)
    check("失效图标回退为 NONE", pie_mod.safe_icon("EDIT") == "NONE", pie_mod.safe_icon("EDIT"))
    check("合法图标原样保留", pie_mod.safe_icon("MESH_CUBE") == "MESH_CUBE",
          pie_mod.safe_icon("MESH_CUBE"))

    section("未定义全局名扫描")
    import builtins as _builtins
    import dis as _dis
    import pkgutil as _pkgutil
    _missing = []
    for _info in _pkgutil.walk_packages(piebind.__path__, prefix="piebind."):
        _mod = __import__(_info.name, fromlist=["_"])
        for _name, _obj in vars(_mod).items():
            _targets = []
            if isinstance(_obj, type) and _obj.__module__.startswith("piebind"):
                for _attr in dir(_obj):
                    _targets.append((f"{_name}.{_attr}", getattr(_obj, _attr)))
            elif callable(_obj) and getattr(_obj, "__module__", "").startswith("piebind"):
                _targets.append((_name, _obj))
            for _label, _fn in _targets:
                _code = getattr(_fn, "__code__", None)
                _ns = getattr(_fn, "__globals__", None)
                if _code is None or _ns is None:
                    continue
                for _ins in _dis.get_instructions(_code):
                    if _ins.opname in ("LOAD_GLOBAL", "LOAD_NAME"):
                        _g = str(_ins.argval).replace("NULL + ", "")
                        if _g not in _ns and not hasattr(_builtins, _g):
                            _missing.append(f"{_info.name}:{_label}:{_g}")
    _missing = sorted(set(_missing))
    check("没有未定义的全局名", not _missing, _missing[:5])

    section("饼菜单布局")
    class _FakeLayout:
        def __init__(self):
            self.calls = []

        def menu_pie(self):
            self.calls.append("menu_pie")
            return self

        def operator(self, idname, **kwargs):
            self.calls.append(("op", idname))
            return type("Op", (), {})()

        def separator(self):
            self.calls.append("sep")

        def label(self, **kwargs):
            self.calls.append("label")

    class _FakeSelf:
        def __init__(self):
            self.layout = _FakeLayout()

    data = config.load()
    pie_data = config.create_pie(data, "布局测试")
    config.set_slot(data, pie_data["id"], "N", {
        "kind": "operator", "idname": "object.mode_set", "text": "n",
        "icon": "NONE", "props": {},
    })
    config.set_slot(data, pie_data["id"], "SE", {
        "kind": "operator", "idname": "object.mode_set", "text": "se",
        "icon": "NONE", "props": {},
    })
    config.save(data)
    old_state = dict(pie_mod.PIE_STATE)
    pie_mod.PIE_STATE["pie_id"] = pie_data["id"]
    stub = _FakeSelf()
    pie_mod.PIEBIND_MT_pie.draw(stub, bpy.context)
    pie_mod.PIE_STATE.update(old_state)
    ops_calls = [c for c in stub.layout.calls if isinstance(c, tuple)]
    check("饼菜单使用 menu_pie()", "menu_pie" in stub.layout.calls, stub.layout.calls[:3])
    check("饼菜单 8 个槽位都有占位", len(stub.layout.calls) == 1 + 8, len(stub.layout.calls))
    check("只有已填槽位产生操作符", len(ops_calls) == 2, ops_calls)

    section("Keymap 列表")
    rows_all = ops.keymap_rows()
    check("keymap 列表非空", len(rows_all) > 10, len(rows_all))
    rows_q = ops.keymap_rows("3d")
    check("keymap 搜索可用", all("3d" in (r["name"] + r["space"]).lower() for r in rows_q) and len(rows_q) > 0,
          len(rows_q))
    if rows_all:
        first = rows_all[0]["name"]
        check("常用 keymap 优先", first in ops.COMMON_KEYMAPS or len(rows_all) < 3, first)

    section("捕获回调")
    class _CaptureStub:
        binding_id = ""

    try:
        result = ops.PIEBIND_OT_capture_key._finish(
            _CaptureStub(), bpy.context, "Tab", {"type": "TAB", "value": "PRESS"}
        )
        check("捕获 _finish 正常返回", result == {"FINISHED"}, result)
        check("捕获结果写入属性", json.loads(bpy.context.window_manager.piebind_key_json)["type"] == "TAB",
              bpy.context.window_manager.piebind_key_json)
    except Exception as exc:
        check("捕获 _finish 正常返回", False, f"{type(exc).__name__}: {exc}")

    section("手动键位解析")
    parsed = ops.parse_key_text("TAB")
    check("TAB 解析", parsed and parsed["type"] == "TAB", parsed)
    parsed = ops.parse_key_text("ctrl+shift+e")
    check("组合键解析", parsed and parsed["type"] == "E" and parsed["ctrl"] and parsed["shift"], parsed)
    parsed = ops.parse_key_text("F8")
    check("F 键解析", parsed and parsed["type"] == "F8", parsed)
    parsed = ops.parse_key_text("1")
    check("数字键解析", parsed and parsed["type"] == "ONE", parsed)
    parsed = ops.parse_key_text("alt+LMB")
    check("鼠标键解析", parsed and parsed["type"] == "LEFTMOUSE" and parsed["alt"], parsed)
    check("空输入返回 None", ops.parse_key_text("  ") is None)

    section("应用 / 复原（无冲突）")
    data = config.load()
    data["bindings"].append({
        "id": "bd_test_1",
        "enabled": True,
        "force_override": False,
        "keymap": {"name": "3D View", "space": "VIEW_3D", "region": "WINDOW"},
        "key": {"type": "F10", "value": "PRESS", "ctrl": True, "alt": True, "shift": True},
        "target": {"kind": "pie", "id": pie["id"], "props": {}},
    })
    config.save(data)
    report = ke.apply(data)
    check("创建了 1 条绑定", len(report["created"]) == 1, report)
    addon_kc = bpy.context.window_manager.keyconfigs.addon
    target_kc = ke.target_keyconfig()
    spec0 = {"name": "Window", "space": "EMPTY", "region": "WINDOW"}
    check("活动层 keyconfig 可用", target_kc is not None, target_kc)
    ours = items_in(target_kc, spec0, idname=ke.DISPATCH_IDNAME)
    check("活动层出现我们的条目", len(ours) == 1, len(ours))
    check("条目携带 binding_id", getattr(ours[0].properties, "binding_id", "") == "bd_test_1")
    check("无冲突时 journal 清空", config.read_journal() is None)

    result = ke.unapply()
    check("卸载后条目清零", result["removed"] >= 1, result)
    leftovers = []
    for layer_kc in (target_kc, addon_kc):
        leftovers += [
            k for k in items_in(layer_kc, spec0)
            if (k.idname or "").startswith("piebind.")
        ]
    check("卸载后无残留", leftovers == [], len(leftovers))

    section("dry-run 不落库")
    data = config.load()
    before = len(items_in(target_kc, spec0))
    dry = ke.apply(data, dry_run=True)
    after = len(items_in(target_kc, spec0))
    check("dry-run 报告创建数", len(dry["created"]) == 1, dry)
    check("dry-run 未真实创建", before == after, (before, after))

    section("强制覆盖：就地接管与复原")
    data = config.load()
    spec = {"name": "3D View", "space": "VIEW_3D", "region": "WINDOW"}
    km = ke.ensure_keymap(addon_kc, spec)
    # 模拟另一个插件先占用了同一键位
    rival = km.keymap_items.new("wm.context_toggle", "F9", "PRESS", ctrl=True, alt=True, shift=True)
    rival.properties.data_path = "scene.tool_settings.use_snap"
    rival_key = {"type": "F9", "value": "PRESS", "ctrl": True, "alt": True, "shift": True}
    rivals = [k for k in km.keymap_items if ke.combo_match(k, rival_key)]
    check("模拟的干扰条目存在且激活", len(rivals) == 1 and rivals[0].active, [(r.active) for r in rivals])

    data["bindings"][0]["force_override"] = True
    data["bindings"][0]["key"] = rival_key
    config.save(data)
    report = ke.apply(data)
    check("覆盖报告标记为接管", report["created"] and report["created"][0].get("patched") == 1, report["created"])
    check("干扰条目被改写成分发器", rival.idname == ke.DISPATCH_IDNAME, rival.idname)
    check("接管后条目仍激活", rival.active is True, rival.active)
    check("journal 记下接管信息", (config.read_journal() or {}).get("patched") is not None,
          config.read_journal())

    ke.unapply()
    check("复原后条目写回原操作符", rival.idname == "wm.context_toggle", rival.idname)
    check("复原后参数写回", getattr(rival.properties, "data_path", "") == "scene.tool_settings.use_snap",
          getattr(rival.properties, "data_path", ""))
    check("复原后仍激活", rival.active is True, rival.active)
    check("复原后 journal 清空", config.read_journal() is None)
    try:
        km.keymap_items.remove(rival)
    except Exception:
        pass

    section("缺失操作符降级")
    data = config.load()
    data["bindings"].append({
        "id": "bd_missing",
        "enabled": True,
        "force_override": False,
        "keymap": {"name": "3D View", "space": "VIEW_3D", "region": "WINDOW"},
        "key": {"type": "F8", "ctrl": True, "shift": True, "alt": True},
        "target": {"kind": "operator", "id": "piebind.nonexistent_op", "props": {}},
    })
    config.save(data)
    report = ke.apply(data)
    check("缺失操作符被跳过", any(s.get("binding") == "bd_missing" for s in report["skipped"]), report["skipped"])
    ke.unapply()

    section("原生操作符目标：就地接管、可幂等重放")
    spec = {"name": "3D View", "space": "VIEW_3D", "region": "WINDOW"}
    km = ke.ensure_keymap(addon_kc, spec)
    native_key = {"type": "F6", "value": "PRESS", "ctrl": True, "shift": True, "alt": True}
    rival = km.keymap_items.new("wm.context_toggle", "F6", "PRESS", ctrl=True, shift=True, alt=True)
    rival.properties.data_path = "scene.tool_settings.use_snap"

    data = config.load()
    data["bindings"] = [{
        "id": "bd_native",
        "enabled": True,
        "force_override": True,
        "keymap": spec,
        "key": native_key,
        "target": {"kind": "operator", "id": "wm.context_toggle",
                   "props": {"data_path": "scene.tool_settings.use_snap_rotate"}},
    }]
    config.save(data)
    report = ke.apply(data)
    matches = items_in(addon_kc, spec, key=native_key)
    check("就地接管为分发器", len(matches) == 1 and matches[0].idname == ke.DISPATCH_IDNAME,
          [m.idname for m in matches])
    check("接管条目携带 binding_id",
          getattr(matches[0].properties, "binding_id", "") == "bd_native", matches)

    ke.apply(config.load())  # 重放
    matches = items_in(addon_kc, spec, key=native_key)
    check("重放不产生重复条目", len(matches) == 1, len(matches))

    ke.unapply()
    check("卸载后写回原操作符", rival.idname == "wm.context_toggle", rival.idname)
    check("卸载后 owned 清空", config.read_owned() == [])
    try:
        km.keymap_items.remove(rival)
    except Exception:
        pass

    section("面板属性与重复键检测")
    check("WM 捕获属性已注册", hasattr(bpy.types.WindowManager, "piebind_capture_label"))
    check("WM 图标属性已注册", hasattr(bpy.types.WindowManager, "piebind_slot_icon"))
    check("WM 方位属性已注册", hasattr(bpy.types.WindowManager, "piebind_slot_pos"))

    dup_key = {"type": "F10", "value": "PRESS", "ctrl": True, "shift": True, "alt": True}
    data = config.load()
    data["bindings"] = [
        {"id": "bd_dup_a", "enabled": True, "force_override": False,
         "keymap": {"name": "3D View", "space": "VIEW_3D", "region": "WINDOW"},
         "key": dup_key, "target": {"kind": "operator", "id": "wm.context_toggle", "props": {}}},
        {"id": "bd_dup_b", "enabled": True, "force_override": False,
         "keymap": {"name": "3D View", "space": "VIEW_3D", "region": "WINDOW"},
         "key": dup_key, "target": {"kind": "operator", "id": "wm.context_toggle", "props": {}}},
    ]
    config.save(data)
    dups = ke.duplicate_bindings(data)
    check("重复键被识别", len(dups) == 1 and dups[0]["key"] == ke.key_label(dup_key), dups)
    report = ke.apply(data, dry_run=True)
    check("apply 报告含重复信息", len(report.get("duplicates", [])) == 1, report.get("duplicates"))

    section("UI 回调")
    wm = bpy.context.window_manager
    ctx = bpy.context

    from piebind.core import presets as preset_mod
    view_rows = preset_mod.presets_for("view3d.view_axis")
    check("视图方位预设 6 项",
          len(view_rows) == 6 and view_rows[0]["props"] == {"type": "TOP"}, view_rows[:1])
    mode_rows = preset_mod.presets_for("object.mode_set")
    check("模式预设非空", len(mode_rows) >= 6, len(mode_rows))
    check("未知操作符无预设", preset_mod.presets_for("piebind.nope") == [])
    check("无枚举参数的操作符无预设", preset_mod.presets_for("wm.context_toggle") == [])
    hide_rows = preset_mod.presets_for("object.hide_view_set")
    check("隐藏操作符带布尔预设",
          len(hide_rows) == 2 and hide_rows[1]["props"] == {"unselected": True}, hide_rows)
    bool_rows = preset_mod.presets_for("view3d.view_all")
    check("布尔参数自动生成预设", len(bool_rows) >= 2, bool_rows[:2])
    check("预设菜单已注册", hasattr(bpy.types, "PIEBIND_MT_slot_presets"))
    wm.piebind_op_choice = ""
    wm.piebind_slot_text = ""
    preset_result = bpy.ops.piebind.apply_slot_preset(
        op_id="view3d.view_axis", props_json='{"type": "LEFT"}', slot_text="左视图")
    check("预设操作符返回 FINISHED", preset_result == {"FINISHED"}, preset_result)
    check("预设写入属性 JSON", json.loads(wm.piebind_slot_props or "{}") == {"type": "LEFT"},
          wm.piebind_slot_props)
    check("预设补上文字", wm.piebind_slot_text == "左视图", wm.piebind_slot_text)
    wm.piebind_op_choice = "view3d.view_all"
    wm.piebind_slot_text = "自定义文字"
    bpy.ops.piebind.apply_slot_preset(
        op_id="view3d.view_all", props_json='{"use_all_regions": false}', slot_text="")
    check("无文字的预设不覆盖文字", wm.piebind_slot_text == "自定义文字", wm.piebind_slot_text)
    check("已移除「模式」快捷字段", not hasattr(bpy.types.WindowManager, "piebind_slot_mode"))

    # 写入槽位：只走「操作符 + 属性 JSON」，不再有模式覆盖
    slot_data = config.load()
    slot_pie = config.create_pie(slot_data, "槽位测试")
    config.save(slot_data)
    wm.piebind_pie = slot_pie["id"]
    wm.piebind_op_choice = "view3d.view_axis"
    wm.piebind_slot_text = "顶视图"
    wm.piebind_slot_props = '{"type": "TOP"}'
    wm.piebind_slot_pos = "N"
    add_result = bpy.ops.piebind.add_slot()
    saved_slot = (config.find_pie(config.load(), slot_pie["id"]) or {}).get("slots", {}).get("N")
    check("写入槽位返回 FINISHED", add_result == {"FINISHED"}, add_result)
    check("槽位保存操作符与参数",
          saved_slot and saved_slot["idname"] == "view3d.view_axis"
          and saved_slot["props"] == {"type": "TOP"} and saved_slot["text"] == "顶视图",
          saved_slot)

    # 旧参数串台：换操作符要清空 JSON；写入时再兜底过滤非法参数
    wm.piebind_op_choice = "view3d.view_axis"
    wm.piebind_slot_props = '{"type": "TOP"}'
    wm.piebind_slot_text = ke.operator_label_zh("view3d.view_axis")
    switched = bpy.ops.piebind.pick_operator(idname="mesh.bevel")
    check("换操作符清空旧参数",
          switched == {"FINISHED"} and not (wm.piebind_slot_props or "").strip(),
          (switched, wm.piebind_slot_props))
    check("换操作符刷新自动文字", wm.piebind_slot_text == ke.operator_label_zh("mesh.bevel"),
          wm.piebind_slot_text)

    wm.piebind_op_choice = "view3d.view_axis"
    wm.piebind_slot_text = "测试槽位"
    wm.piebind_slot_props = '{"type": "FRONT", "bogus": 1}'
    wm.piebind_slot_pos = "S"
    bpy.ops.piebind.add_slot()
    filtered = (config.find_pie(config.load(), slot_pie["id"]) or {}).get("slots", {}).get("S")
    check("写入时丢弃不适用参数", filtered and filtered["props"] == {"type": "FRONT"}, filtered)

    section("槽位回读")
    read_data = config.load()
    read_pie = config.create_pie(read_data, "回读测试")
    config.set_slot(read_data, read_pie["id"], "N", {
        "kind": "operator", "idname": "view3d.view_axis", "text": "顶视图",
        "icon": "NONE", "props": {"type": "TOP"},
    })
    config.save(read_data)
    wm.piebind_pie = read_pie["id"]
    wm.piebind_slot_pos = "E"
    wm.piebind_op_choice = "mesh.bevel"
    wm.piebind_slot_text = "旧文字"
    wm.piebind_slot_props = '{"x": 1}'
    bpy.ops.piebind.select_slot(pos="N")
    check("选中槽位读入操作符", wm.piebind_op_choice == "view3d.view_axis", wm.piebind_op_choice)
    check("选中槽位读入参数", json.loads(wm.piebind_slot_props or "{}") == {"type": "TOP"},
          wm.piebind_slot_props)
    check("选中槽位读入文字", wm.piebind_slot_text == "顶视图", wm.piebind_slot_text)
    bpy.ops.piebind.select_slot(pos="E")
    check("空槽清空编辑区",
          not wm.piebind_op_choice and not wm.piebind_slot_props and not wm.piebind_slot_text,
          (wm.piebind_op_choice, wm.piebind_slot_props, wm.piebind_slot_text))
    bpy.ops.piebind.select_slot(pos="N")
    wm.piebind_slot_text = "手改"
    bpy.ops.piebind.load_slot()
    check("重载恢复槽位内容", wm.piebind_slot_text == "顶视图", wm.piebind_slot_text)
    check("载入槽位操作符已注册", hasattr(bpy.types, "PIEBIND_OT_load_slot"))

    section("槽位自动保存")
    from piebind.ops import common as _common
    auto_data = config.load()
    auto_pie = config.create_pie(auto_data, "自动保存测试")
    config.save(auto_data)
    wm.piebind_tab = "pies"
    wm.piebind_pie = auto_pie["id"]
    wm.piebind_slot_pos = "N"
    wm.piebind_op_choice = "view3d.view_axis"
    wm.piebind_slot_text = "顶视图"
    wm.piebind_slot_props = '{"type": "TOP"}'
    wm.piebind_slot_icon = "NONE"
    _first_save = _common.save_current_slot(wm)
    _auto_slot = (config.find_pie(config.load(), auto_pie["id"]) or {}).get("slots", {}).get("N")
    check("自动保存写入槽位",
          _first_save is True and _auto_slot and _auto_slot["props"] == {"type": "TOP"},
          _auto_slot)
    check("内容没变不重复写", _common.save_current_slot(wm) is False)
    wm.piebind_slot_props = '{"type": "TO'
    check("半截 JSON 不写盘", _common.save_current_slot(wm) is False)
    wm.piebind_slot_props = '{"type": "FRONT"}'
    check("JSON 修好后继续写", _common.save_current_slot(wm) is True)
    wm.piebind_slot_text = "正视图"
    check("改文字也会触发写盘", _common.save_current_slot(wm) is True)
    wm.piebind_suppress_save = True
    wm.piebind_slot_props = '{"type": "BACK"}'
    check("抑制标志生效", _common.save_current_slot(wm) is False)
    wm.piebind_suppress_save = False
    wm.piebind_tab = "bindings"
    wm.piebind_slot_props = '{"type": "LEFT"}'
    check("非饼页签不写盘", _common.save_current_slot(wm) is False)
    wm.piebind_tab = "pies"

    wm.piebind_slot_props = '{"type": "BACK"}'
    _common._AUTOSAVE_TIMER["pending"] = True
    _flushed = _common.flush_pending_save(wm)
    _flushed_slot = (config.find_pie(config.load(), auto_pie["id"]) or {}).get("slots", {}).get("N")
    check("切槽位前先落盘", _flushed is True and _flushed_slot["props"] == {"type": "BACK"},
          _flushed_slot)

    from piebind.ops import dispatch as dispatch_mod_guard
    bad_binding = {
        "keymap": {"name": "3D View", "space": "VIEW_3D", "region": "WINDOW"},
        "target": {"kind": "operator", "id": "wm.context_toggle", "props": {"bogus": 1}},
    }
    guarded = dispatch_mod_guard.run_binding(bpy.context, bad_binding)
    check("参数不匹配时安全取消", guarded == {"CANCELLED"}, guarded)

    # 后台调用饼菜单会让 Blender 原生崩溃，必须先拦住
    pie_binding = {
        "keymap": {"name": "3D View", "space": "VIEW_3D", "region": "WINDOW"},
        "target": {"kind": "pie", "id": pie["id"], "props": {}},
    }
    pie_guarded = dispatch_mod_guard.run_binding(bpy.context, pie_binding)
    check("后台不调用饼菜单（防崩溃）", pie_guarded == {"CANCELLED"}, pie_guarded)
    class _StubPreviewOp:
        msg = ""

        def report(self, level, message):
            self.msg = f"{level}:{message}"

    _stub_op = _StubPreviewOp()
    _preview_result = ops.PIEBIND_OT_test_pie.invoke(_stub_op, bpy.context, None)
    check("后台预览饼安全拒绝",
          _preview_result == {"CANCELLED"} and "后台" in _stub_op.msg,
          (_preview_result, _stub_op.msg))

    # 用桩布局把「参数预设」菜单画一遍：确认条目数与回调都正确
    class _StubOpItem:
        def __init__(self, idname, text):
            self.idname = idname
            self.text = text

    class _StubPresetLayout:
        def __init__(self):
            self.items = []

        def operator(self, idname, text="", icon=""):
            item = _StubOpItem(idname, text)
            self.items.append(item)
            return item

        def label(self, text="", icon=""):
            self.items.append(("label", text))

        def separator(self):
            self.items.append(("sep", ""))

    class _StubMenuHost:
        def __init__(self):
            self.layout = _StubPresetLayout()

    wm.piebind_op_choice = "view3d.view_axis"
    stub_menu = _StubMenuHost()
    ops.PIEBIND_MT_slot_presets.draw(stub_menu, bpy.context)
    preset_ops = [i for i in stub_menu.layout.items if getattr(i, "idname", "") == "piebind.apply_slot_preset"]
    check("预设菜单列出 6 个视图方位", len(preset_ops) == 6, len(preset_ops))
    check("预设菜单条目带 JSON",
          all(getattr(i, "props_json", "").startswith("{") for i in preset_ops),
          preset_ops[0].props_json if preset_ops else None)
    check("预设标签可反查",
          preset_mod.label_for("view3d.view_axis", {"type": "TOP"}) == "顶视图",
          preset_mod.label_for("view3d.view_axis", {"type": "TOP"}))
    check("未匹配的 JSON 无标签",
          preset_mod.label_for("view3d.view_axis", {"type": "NOPE"}) == "");
    check("捕获操作符已注册", hasattr(bpy.types, "PIEBIND_OT_capture_key"))
    check("选择槽位操作符已注册", hasattr(bpy.types, "PIEBIND_OT_select_slot"))
    check("改名操作符已注册", hasattr(bpy.types, "PIEBIND_OT_rename_pie"))
    _rename_id = config.load()["pies"][0]["id"]
    _rename_result = bpy.ops.piebind.rename_pie(pie_id=_rename_id, label="操作符改名")
    check("改名操作符返回 FINISHED", _rename_result == {"FINISHED"}, _rename_result)
    check("改名操作符已生效", config.load()["pies"][0]["label"] == "操作符改名",
          config.load()["pies"][0].get("label"))
    keymap_items = ops._refresh_keymap_items(wm, ctx)
    check("keymap 枚举可用", len(keymap_items) >= 1, len(keymap_items))
    pie_items = ops._refresh_pie_items(wm, ctx)
    check("饼枚举可用", len(pie_items) >= 1, pie_items)
    pos_items = ops._refresh_slot_pos(wm, ctx)
    check("方位枚举 8 项", len(pos_items) == 8, len(pos_items))
    try:
        op_items = ops._operator_choices(wm, ctx)
        check("操作符枚举可用", len(op_items) >= 1, len(op_items))
    except Exception as exc:
        check("操作符枚举可用", False, exc)

    section("中文搜索")
    _t0 = time.perf_counter()
    _rows = ke.operator_index()
    _dt = (time.perf_counter() - _t0) * 1000
    print(f"  [perf] 操作符索引 {len(_rows)} 条，构建/加载 {_dt:.0f} ms")
    check("索引非空", len(_rows) > 1000, len(_rows))
    en_hits = ke.search_operators("bevel", limit=5)
    check("英文关键词可搜", len(en_hits) > 0, en_hits)
    locale = getattr(bpy.app.translations, "locale", "en") or "en"
    if locale.lower().startswith("zh"):
        zh_hits = ke.search_operators("倒角", limit=5)
        check("中文关键词可搜到倒角", "mesh.bevel" in zh_hits, zh_hits)
        check("中文标签可用", ke.operator_label_zh("mesh.bevel") != "Bevel",
              ke.operator_label_zh("mesh.bevel"))
    else:
        print(f"  SKIP 中文搜索（当前语言 {locale}）")

    section("API")
    described = api.call("describe")
    check("describe 可用", described.get("ok") is True and "bind" in described["data"]["actions"])
    unknown = api.call("nope_action")
    check("未知动作返回结构化错误", unknown.get("ok") is False and unknown["error"]["code"] == "UNKNOWN_ACTION")
    found = api.call("search_operators", query="bevel", limit=5)
    check("操作符搜索非空", found.get("ok") and len(found["data"]) > 0, found)
    conflicts = api.call("check_conflict", keymap="3D View", key={"type": "T"})
    check("冲突检测可调用", conflicts.get("ok") is True)
    dry = api.call("bind", keymap="3D View", key={"type": "F7", "ctrl": True, "alt": True},
                   target={"kind": "pie", "id": pie["id"]}, dry_run=True)
    check("api bind dry-run 返回 would_bind", dry.get("ok") is True and "would_bind" in dry["data"], dry)

    snap = api.call("diagnostics")
    check("诊断快照可用", snap.get("ok") is True and snap["data"]["tool"]["name"] == "PieBind", snap.get("error"))
    check("诊断含层信息", len(snap["data"].get("layers", [])) >= 1, snap["data"].get("layers"))
    check("诊断路径已脱敏", "\\Users\\" not in str(snap["data"]["config"]["dir"]).replace("/", "\\")
          or snap["data"]["config"]["dir"].startswith("~"), snap["data"]["config"]["dir"])

    section("保存绑定与 Keymap 下拉")
    from piebind.core import keyspec as _keyspec
    wm.piebind_keymap = _keyspec.make_keymap_identifier("3D View", "VIEW_3D", "WINDOW")
    wm.piebind_key_json = json.dumps({
        "type": "F8", "value": "PRESS", "ctrl": True, "shift": False,
        "alt": False, "oskey": False, "any": False, "key_modifier": "NONE",
    })
    wm.piebind_target_kind = "operator"
    wm.piebind_op_choice = "wm.context_toggle"
    wm.piebind_force_override = False
    wm.piebind_restrict_view3d = True
    _before = len(config.load()["bindings"])
    _created = bpy.ops.piebind.create_binding()
    _bindings = config.load()["bindings"]
    check("保存绑定返回 FINISHED", _created == {"FINISHED"}, _created)
    check("绑定已写入且 keymap 正确",
          len(_bindings) == _before + 1 and _bindings[-1]["keymap"]["name"] == "3D View",
          _bindings[-1] if _bindings else None)

    class _StubMenuLayout:
        def __init__(self):
            self.ops = []
            self.labels = []

        def operator(self, idname, text="", icon=""):
            self.ops.append((idname, text))
            return type("Op", (), {})()

        def label(self, text="", icon=""):
            self.labels.append(text)

        def separator(self):
            pass

    _host = type("Host", (), {})()
    _host.layout = _StubMenuLayout()
    ops.PIEBIND_MT_keymaps.draw(_host, bpy.context)
    check("Keymap 下拉可绘制", len(_host.layout.ops) > 0, len(_host.layout.ops))

    section("快捷键展示")
    _kc = bpy.context.window_manager.keyconfigs.active
    _km = _kc.keymaps.get("3D View")
    _created_km = False
    if _km is None:
        _km = _kc.keymaps.new("3D View", space_type="VIEW_3D")
        _created_km = True
    _kmi = _km.keymap_items.new("wm.context_toggle", type="H", value="PRESS")
    _kmi.active = True
    ke.shortcut_map(refresh=True)
    _short_label = ke.shortcut_for("wm.context_toggle")
    check("能查到操作符的现有键位", "H" in _short_label, _short_label)

    wm.piebind_op_query = "context_toggle"
    _menu_host = type("MenuHost", (), {})()
    _menu_host.layout = _StubMenuLayout()
    ops.PIEBIND_MT_operators.draw(_menu_host, bpy.context)
    _menu_texts = [text for _idname, text in _menu_host.layout.ops]
    check("搜索结果里带出快捷键", any("H" in text for text in _menu_texts), _menu_texts[:2])

    _h_hits = ke.search_operators("h", limit=10)
    check("按键位搜索命中操作符", "wm.context_toggle" in _h_hits[:3], _h_hits[:5])
    _shift_kmi = _km.keymap_items.new("wm.context_toggle", type="H", value="PRESS")
    _shift_kmi.shift = True
    _shift_kmi.active = True
    ke.shortcut_map(refresh=True)
    _shift_hits = ke.search_operators("shift+h", limit=10)
    check("组合键搜索命中操作符", "wm.context_toggle" in _shift_hits[:3], _shift_hits[:5])
    check("索引带格式版本", ke._INDEX_FORMAT == 2, ke._INDEX_FORMAT)
    ke.shortcut_map(refresh=True)
    check("缓存刷新后仍可查", "H" in ke.shortcut_for("wm.context_toggle"))
    try:
        _km.keymap_items.remove(_kmi)
        _km.keymap_items.remove(_shift_kmi)
    except Exception:
        pass
    if _created_km:
        try:
            _kc.keymaps.remove(_km)
        except Exception:
            pass
    ke.shortcut_map(refresh=True)
    check("未知操作符返回空键位", ke.shortcut_for("piebind.nope") == "")

    section("操作符范围")
    check("范围标签有中文", ke.prefix_label("view3d") == "3D 视图", ke.prefix_label("view3d"))
    check("空范围显示全部", ke.prefix_label("") == "全部")
    _obj_hits = ke.search_operators("", limit=20, prefix="object")
    check("范围过滤只出 object.*",
          bool(_obj_hits) and all(hit.startswith("object.") for hit in _obj_hits),
          _obj_hits[:3])
    _scoped_hits = ke.search_operators("view", limit=20, prefix="view3d")
    check("范围与关键词叠加",
          all(hit.startswith("view3d.") for hit in _scoped_hits), _scoped_hits[:3])
    wm.piebind_op_query = ""
    wm.piebind_op_prefix = ""
    bpy.ops.piebind.select_op_prefix(prefix="object")
    check("选择范围写入状态", wm.piebind_op_prefix == "object", wm.piebind_op_prefix)
    check("选中项落在范围内", str(wm.piebind_op_choice).startswith("object."),
          wm.piebind_op_choice)
    wm.piebind_op_prefix = ""

    section("清单")
    print(f"\nPASSED {len(PASSED)} / FAILED {len(FAILED)}")
    for item in FAILED:
        print("  FAILED:", item)
    if FAILED:
        raise SystemExit(1)
    print("\nALL TESTS PASSED")


try:
    main()
except SystemExit:
    raise
except Exception:
    traceback.print_exc()
    raise SystemExit(1)
