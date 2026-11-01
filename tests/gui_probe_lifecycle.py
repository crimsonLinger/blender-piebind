"""生命周期探针：扩展安装目录 + 独立配置目录，验证 启用→应用→禁用→无残留。

以 GUI 方式运行（需要窗口才有完整 keymap），全程使用临时 BLENDER_USER_CONFIG /
BLENDER_USER_EXTENSIONS，不触碰用户真实配置。
"""

import json
import os
import sys

import bpy

OUT = os.path.join(os.environ.get("TEMP", "/tmp"), "piebind_gui_probe")
os.makedirs(OUT, exist_ok=True)
RESULT = os.path.join(OUT, "result_lifecycle.json")
LOG = os.path.join(OUT, "lifecycle.log")
os.environ.setdefault("PIEBIND_CONFIG_DIR", os.path.join(OUT, "cfg_lifecycle"))
os.makedirs(os.environ["PIEBIND_CONFIG_DIR"], exist_ok=True)

RESULTS = []
MODULE = "bl_ext.user_default.piebind"


def record(name, ok, detail=""):
    RESULTS.append({"name": name, "ok": bool(ok), "detail": str(detail)[:500]})
    line = f"[LIFE] {'OK  ' if ok else 'FAIL'} {name}  {detail}"
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def count_ours():
    wm = bpy.context.window_manager
    rows = []
    for kc in wm.keyconfigs:
        for km in kc.keymaps:
            for kmi in km.keymap_items:
                if (kmi.idname or "").startswith("piebind."):
                    rows.append({"kc": kc.name, "keymap": km.name, "idname": kmi.idname})
    return rows


def quit_later():
    bpy.ops.wm.quit_blender()


def main():
    try:
        bpy.ops.preferences.addon_enable(module=MODULE)
        record("扩展启用", MODULE in bpy.context.preferences.addons, MODULE)
    except Exception as exc:
        record("扩展启用", False, f"{type(exc).__name__}: {exc}")
        dump_and_quit()
        return

    import importlib
    pkg = importlib.import_module(MODULE)
    record("模块可导入", True, pkg.__name__)

    data = pkg.config.default_data()
    data["bindings"].append({
        "id": "bd_life",
        "enabled": True,
        "force_override": False,
        "keymap": {"name": "3D View", "space": "VIEW_3D", "region": "WINDOW"},
        "key": {"type": "F7", "value": "PRESS", "ctrl": True, "shift": True, "alt": True},
        "target": {"kind": "operator", "id": "wm.context_toggle",
                   "props": {"data_path": "scene.tool_settings.use_snap_rotate"}},
    })
    pkg.config.save(data)
    report = pkg.keymap_engine.apply(data)
    record("应用绑定", len(report["created"]) == 1, report)

    rows = count_ours()
    record("应用后条目存在", len(rows) >= 1, rows)

    scene = bpy.context.scene
    scene.tool_settings.use_snap_rotate = False
    try:
        bpy.ops.piebind.dispatch(binding_id="bd_life")
        record("分发器可执行", bool(scene.tool_settings.use_snap_rotate),
               f"use_snap_rotate={scene.tool_settings.use_snap_rotate}")
    except Exception as exc:
        record("分发器可执行", False, f"{type(exc).__name__}: {exc}")

    try:
        bpy.ops.preferences.addon_disable(module=MODULE)
        record("扩展禁用", MODULE not in bpy.context.preferences.addons)
    except Exception as exc:
        record("扩展禁用", False, f"{type(exc).__name__}: {exc}")

    leftover = count_ours()
    record("禁用后无残留", leftover == [], leftover)

    dump_and_quit()


def dump_and_quit():
    with open(RESULT, "w", encoding="utf-8") as fh:
        json.dump(RESULTS, fh, ensure_ascii=False, indent=1)
    bpy.app.timers.register(quit_later, first_interval=0.5)


try:
    main()
except Exception:
    import traceback
    record("探针异常", False, traceback.format_exc()[:600])
    dump_and_quit()