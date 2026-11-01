"""GUI 覆盖探针：验证强制覆盖在真实内置键位上是否生效。

由 tests/run_gui_probe.ps1 启动；脚本会：
1. 找到 3D View 里真实的 'T'（工具栏开关）键位；
2. 用我们的绑定覆盖它（静音原项）；
3. 写 ready 文件，等待外部 SendKeys 按下 'T'；
4. 若 use_snap 被我们的 context_toggle 翻转，说明覆盖真正生效；
5. 复原 → 模拟崩溃 → journal 自愈校验 → 写结果并退出。
"""

import json
import os
import sys
import tempfile
import time
import traceback

import bpy

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

OUT = os.path.join(tempfile.gettempdir(), "piebind_gui_probe")
os.makedirs(OUT, exist_ok=True)
READY = os.path.join(OUT, "ready.json")
STOP = os.path.join(OUT, "stop.txt")
RESULT = os.path.join(OUT, "result.json")
os.environ["PIEBIND_CONFIG_DIR"] = os.path.join(OUT, "cfg")
os.makedirs(os.environ["PIEBIND_CONFIG_DIR"], exist_ok=True)

for stale in (READY, STOP, RESULT):
    try:
        os.remove(stale)
    except FileNotFoundError:
        pass

import piebind  # noqa: E402
from piebind import config, keymap_engine as ke  # noqa: E402

RESULTS = []
STATE = {"started": time.time()}


def record(name, ok, detail=""):
    RESULTS.append({"name": name, "ok": bool(ok), "detail": str(detail)[:400]})
    print(f"[PROBE] {'OK  ' if ok else 'FAIL'} {name}  {detail}")


def save_results():
    with open(RESULT, "w", encoding="utf-8") as fh:
        json.dump(RESULTS, fh, ensure_ascii=False, indent=1)


def find_target():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.active
    target_km = None
    for km in kc.keymaps:
        if km.name == "3D View" and km.space_type == "VIEW_3D" and not km.is_modal:
            target_km = km
            break
    if target_km is None:
        return None, None
    for kmi in target_km.keymap_items:
        if kmi.idname != "wm.context_toggle":
            continue
        data_path = getattr(kmi.properties, "data_path", "") or ""
        if "show_region_toolbar" not in data_path:
            continue
        if kmi.ctrl or kmi.shift or kmi.alt or getattr(kmi, "oskey", False):
            continue
        return target_km, kmi
    return target_km, None


def setup():
    piebind.register()
    scene = bpy.context.scene
    wm = bpy.context.window_manager
    target_km, target_kmi = find_target()
    if target_kmi is None:
        record("找到 T 键位", False, "未在 3D View 找到 show_region_toolbar 的 T")
        save_results()
        bpy.ops.wm.quit_blender()
        return

    combo = {
        "type": target_kmi.type,
        "value": "PRESS",
        "ctrl": bool(target_kmi.ctrl),
        "shift": bool(target_kmi.shift),
        "alt": bool(target_kmi.alt),
        "oskey": bool(getattr(target_kmi, "oskey", False)),
        "any": False,
        "key_modifier": "NONE",
    }
    STATE.update({
        "scene": scene,
        "target": target_kmi,
        "combo": combo,
        "original_active": target_kmi.active,
        "original_idname": target_kmi.idname,
    })
    record("找到内置键位", True, f"{ke.key_label(combo)} → {target_kmi.idname} ({getattr(target_kmi.properties, 'data_path', '')})")

    data = config.default_data()
    pie = config.create_pie(data, "探针饼")
    config.set_slot(data, pie["id"], "N", {
        "kind": "operator", "idname": "mesh.bevel", "text": "倒角", "props": {},
    })
    data["bindings"].append({
        "id": "bd_probe",
        "enabled": True,
        "force_override": True,
        "keymap": {"name": "3D View", "space": "VIEW_3D", "region": "WINDOW"},
        "key": combo,
        "target": {
            "kind": "operator",
            "id": "wm.context_toggle",
            "props": {"data_path": "scene.tool_settings.use_snap"},
        },
    })
    config.save(data)
    report = ke.apply(data)
    STATE["report"] = report

    record("创建我们的键位", len(report["created"]) == 1 and not report["skipped"], report)
    record("内置项被静音", target_kmi.active is False, f"active={target_kmi.active}")
    record("存在覆盖记录", any(m["owner"] for m in report["muted"]), report["muted"])
    record("journal 已落盘", config.read_journal() is not None)

    # 镜像检查：我们的条目是否同时出现在 user/active 层
    mirrors = {}
    for kc in (wm.keyconfigs.active, wm.keyconfigs.user, wm.keyconfigs.addon):
        if kc is None:
            continue
        count = 0
        for km in kc.keymaps:
            for kmi in km.keymap_items:
                if (kmi.idname or "").startswith("piebind."):
                    count += 1
        mirrors[kc.name] = count
    record("镜像层统计", True, mirrors)

    scene.tool_settings.use_snap = False
    with open(READY, "w", encoding="utf-8") as fh:
        json.dump({"pid": os.getpid(), "key": combo, "label": ke.key_label(combo)}, fh)

    bpy.app.timers.register(wait_for_key, first_interval=0.2)


def wait_for_key():
    scene = STATE.get("scene")
    if os.path.exists(STOP):
        value = bool(scene.tool_settings.use_snap) if scene else None
        record("实按热键后我们的操作生效", value is True,
               f"use_snap={value}（False 说明覆盖未生效/按键没进来）")
        phase_cleanup()
        return None
    if time.time() - STATE["started"] > 90:
        record("等待按键", False, "90s 超时，未收到外部按键信号")
        phase_cleanup()
        return None
    return 0.2


def phase_cleanup():
    target_kmi = STATE.get("target")
    try:
        ke.unapply()
        record("复原后内置项激活", bool(target_kmi.active), f"active={target_kmi.active}")
        record("复原后 journal 清空", config.read_journal() is None)
    except Exception:
        record("复原流程", False, traceback.format_exc()[:300])

    # 模拟崩溃：覆盖后直接删掉我们的条目，留下 journal
    try:
        data = config.load()
        ke.apply(data)
        kc = bpy.context.window_manager.keyconfigs.addon
        if kc is not None:
            for km in list(kc.keymaps):
                for kmi in list(km.keymap_items):
                    if (kmi.idname or "").startswith("piebind."):
                        km.keymap_items.remove(kmi)
        muted_before = bool(target_kmi.active) is False
        heal = ke.reconcile_journal()
        record("模拟崩溃后 journal 自愈", muted_before and bool(target_kmi.active),
               f"muted_before={muted_before} heal={heal} active={target_kmi.active}")
    except Exception:
        record("崩溃自愈", False, traceback.format_exc()[:300])

    try:
        data = config.load()
        ke.apply(data)
        ke.unapply()
    except Exception:
        pass

    save_results()
    try:
        piebind.unregister()
    except Exception:
        pass
    bpy.ops.wm.quit_blender()


def main():
    try:
        setup()
    except Exception:
        record("探针启动", False, traceback.format_exc()[:600])
        save_results()
        bpy.ops.wm.quit_blender()


main()