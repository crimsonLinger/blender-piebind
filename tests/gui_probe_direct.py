"""无人工探针：直接调用分发器，验证「配置 -> 引擎 -> 分发器 -> 目标操作」这一段。

键盘投递是否成功属于外部环境问题，单独由 gui_probe_dispatch.py 验证过。
"""

import json
import os
import sys
import tempfile

import bpy

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

OUT = os.path.join(tempfile.gettempdir(), "piebind_gui_probe")
os.makedirs(OUT, exist_ok=True)
RESULT = os.path.join(OUT, "result_direct.json")
LOG = os.path.join(OUT, "direct.log")
os.environ["PIEBIND_CONFIG_DIR"] = os.path.join(OUT, "cfg_direct")
os.makedirs(os.environ["PIEBIND_CONFIG_DIR"], exist_ok=True)

for stale in (RESULT,):
    try:
        os.remove(stale)
    except FileNotFoundError:
        pass

import piebind  # noqa: E402
from piebind import config, keymap_engine as ke  # noqa: E402

RESULTS = []
STATE = {}


def record(name, ok, detail=""):
    RESULTS.append({"name": name, "ok": bool(ok), "detail": str(detail)[:400]})
    line = f"[DIRECT] {'OK  ' if ok else 'FAIL'} {name}  {detail}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def dump():
    with open(RESULT, "w", encoding="utf-8") as fh:
        json.dump(RESULTS, fh, ensure_ascii=False, indent=1)


def quit_later():
    bpy.ops.wm.quit_blender()


def main():
    piebind.register()
    scene = bpy.context.scene
    STATE["scene"] = scene

    data = config.default_data()
    data["bindings"].append({
        "id": "bd_direct",
        "enabled": True,
        "force_override": False,
        "keymap": {"name": "3D View", "space": "VIEW_3D", "region": "WINDOW"},
        "key": {"type": "F8", "value": "PRESS"},
        "target": {"kind": "operator", "id": "wm.context_toggle",
                   "props": {"data_path": "scene.tool_settings.use_snap_rotate"}},
    })
    config.save(data)
    report = ke.apply(data)
    record("应用绑定", len(report["created"]) == 1 and not report["skipped"], report)

    # 先确认条目在哪个 keymap、active 与否
    wm = bpy.context.window_manager
    rows = []
    for kc in (wm.keyconfigs.active, wm.keyconfigs.user):
        for km in kc.keymaps:
            if km.name != "Window":
                continue
            for item in km.keymap_items:
                if item.idname == ke.DISPATCH_IDNAME:
                    rows.append({"kc": kc.name, "active": item.active,
                                 "binding_id": getattr(item.properties, "binding_id", "")})
    record("分发条目存在", len(rows) >= 1, rows)

    scene.tool_settings.use_snap_rotate = False
    try:
        bpy.ops.piebind.dispatch(binding_id="bd_direct")
    except Exception as exc:
        record("直接调用分发器", False, f"{type(exc).__name__}: {exc}")
    record("分发器执行了目标操作", bool(scene.tool_settings.use_snap_rotate),
           f"use_snap_rotate={scene.tool_settings.use_snap_rotate}")

    # 再测一次饼路径（只验证调用不抛错）
    pie = config.create_pie(config.load(), "直调饼")
    config.set_slot(config.load(), pie["id"], "N", {"kind": "operator", "idname": "mesh.bevel"})
    data = config.load()
    data["bindings"] = [{
        "id": "bd_pie",
        "enabled": True,
        "force_override": False,
        "keymap": {"name": "3D View", "space": "VIEW_3D", "region": "WINDOW"},
        "key": {"type": "F7", "value": "PRESS"},
        "target": {"kind": "pie", "id": pie["id"]},
    }]
    config.save(data)
    ke.apply(data)
    try:
        result = bpy.ops.piebind.dispatch("INVOKE_DEFAULT", binding_id="bd_pie")
        record("分发器调用饼菜单", True, str(result))
    except Exception as exc:
        record("分发器调用饼菜单", False, f"{type(exc).__name__}: {exc}")

    ke.unapply()
    record("复原完成", config.read_journal() is None, "")
    dump()
    bpy.app.timers.register(quit_later, first_interval=0.5)


try:
    main()
except Exception:
    import traceback
    record("探针异常", False, traceback.format_exc()[:600])
    dump()
    bpy.app.timers.register(quit_later, first_interval=0.5)