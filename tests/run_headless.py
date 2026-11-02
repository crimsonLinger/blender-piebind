"""Headless 端到端测试。

运行：
  & 'D:\\Blender\\blender.exe' -b --factory-startup --python-exit-code 1 \
      --python 'E:\\blender插件\\tests\\run_headless.py'
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

    section("键位标签")
    label = ke.key_label({"type": "E", "alt": True, "shift": True})
    check("标签格式", label == "SHIFT+ALT+E", label)
    label = ke.key_label({"type": "ONE", "ctrl": True})
    check("数字键标签", label == "CTRL+1", label)
    check("侧键标签", ke.key_label({"type": "BUTTON4MOUSE"}) == "M4",
          ke.key_label({"type": "BUTTON4MOUSE"}))
    check("侧键解析", (ops.parse_key_text("m5") or {}).get("type") == "BUTTON5MOUSE",
          ops.parse_key_text("m5"))

    section("图标合法性")
    import re as _re
    import pathlib as _pathlib
    _icons = {
        item.identifier
        for item in bpy.types.UILayout.bl_rna.functions["label"].parameters["icon"].enum_items
    }
    _bad = []
    for _path in _pathlib.Path(__file__).resolve().parent.parent.joinpath("src", "piebind").glob("*.py"):
        _text = _path.read_text(encoding="utf-8")
        for _m in _re.finditer(r'icon\s*=\s*"([A-Z0-9_]+)"', _text):
            if _m.group(1) not in _icons:
                _bad.append(f"{_path.name}:{_text[:_m.start()].count(chr(10)) + 1}:{_m.group(1)}")
    check("源码中图标名全部合法", not _bad, _bad[:5])

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
    check("捕获操作符已注册", hasattr(bpy.types, "PIEBIND_OT_capture_key"))
    check("选择槽位操作符已注册", hasattr(bpy.types, "PIEBIND_OT_select_slot"))
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
