"""手动按键探针：自动配好「覆盖 Shift+Tab」，等人按键后自动判定。

为什么需要手动：本机 SendKeys 无法驱动 Blender（Window 级绑定也收不到），
属于 Windows 输入注入被拦，不是插件问题。

用法：由外部启动 Blender 运行本脚本，用户在 3D 视口里按 Shift+Tab。
成功判据：scene.tool_settings.use_snap_rotate == True 且 use_snap == False。
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
RESULT = os.path.join(OUT, "result_manual.json")
LOG = os.path.join(OUT, "manual.log")
os.environ["PIEBIND_CONFIG_DIR"] = os.path.join(OUT, "cfg_manual")
os.makedirs(os.environ["PIEBIND_CONFIG_DIR"], exist_ok=True)

for stale in (RESULT,):
    try:
        os.remove(stale)
    except FileNotFoundError:
        pass

import piebind  # noqa: E402
from piebind import config, keymap_engine as ke  # noqa: E402

RESULTS = []
STATE = {"started": time.time()}
TIMEOUT = 900


def record(name, ok, detail=""):
    RESULTS.append({"name": name, "ok": bool(ok), "detail": str(detail)[:400]})
    line = f"[MANUAL] {'OK  ' if ok else 'FAIL'} {name}  {detail}"
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def save_results():
    with open(RESULT, "w", encoding="utf-8") as fh:
        json.dump(RESULTS, fh, ensure_ascii=False, indent=1)


def quit_later():
    bpy.ops.wm.quit_blender()


def find_target():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.active
    km = None
    for candidate in kc.keymaps:
        if candidate.name == "3D View" and candidate.space_type == "VIEW_3D" and not candidate.is_modal:
            km = candidate
            break
    if km is None:
        return None, None
    for kmi in km.keymap_items:
        if kmi.idname != "wm.context_toggle":
            continue
        if (getattr(kmi.properties, "data_path", "") or "") != "tool_settings.use_snap":
            continue
        if kmi.ctrl or kmi.alt:
            continue
        return km, kmi
    return km, None


def setup():
    piebind.register()
    scene = bpy.context.scene
    wm = bpy.context.window_manager
    target_km, target_kmi = find_target()
    if target_kmi is None:
        record("找到内置键位", False, "3D View 里没有 use_snap 的 context_toggle")
        save_results()
        bpy.app.timers.register(quit_later, first_interval=0.5)
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
    STATE.update({"scene": scene, "target": target_kmi, "combo": combo})
    record("找到内置键位", True,
           f"{ke.key_label(combo)} → {target_kmi.idname} "
           f"({getattr(target_kmi.properties, 'data_path', '')})")

    data = config.default_data()
    data["bindings"].append({
        "id": "bd_manual",
        "enabled": True,
        "force_override": True,
        "keymap": {"name": "3D View", "space": "VIEW_3D", "region": "WINDOW"},
        "key": combo,
        "target": {
            "kind": "operator",
            "id": "wm.context_toggle",
            "props": {"data_path": "scene.tool_settings.use_snap_rotate"},
        },
    })
    config.save(data)
    report = ke.apply(data)
    record("创建我们的键位", len(report["created"]) == 1 and not report["skipped"], report)
    record("内置项被静音", target_kmi.active is False, f"active={target_kmi.active}")
    record("覆盖记录已写入", len(report["muted"]) >= 1, report["muted"])

    scene.tool_settings.use_snap = False
    scene.tool_settings.use_snap_rotate = False

    state = []
    for layer, kc in ke.iter_layers():
        kmx = ke.find_keymap(kc, {"name": "3D View", "space": "VIEW_3D", "region": "WINDOW"})
        if kmx is None:
            continue
        for kmi in kmx.keymap_items:
            if not ke.combo_match(kmi, combo):
                continue
            state.append({
                "layer": layer,
                "idname": kmi.idname,
                "active": kmi.active,
                "data_path": getattr(kmi.properties, "data_path", ""),
            })
    record("按下前的键位状态", any(s["active"] for s in state), state)

    try:
        if bpy.context.workspace:
            bpy.context.workspace.status_text_set(
                "PieBind 探针：请把鼠标放到 3D 视口中央，然后按 Shift+Tab"
            )
    except Exception:
        pass

    print("=" * 70, flush=True)
    print("PieBind 探针已就绪：请在 3D 视口内按 Shift+Tab（不要按其它键）", flush=True)
    print("=" * 70, flush=True)

    bpy.app.timers.register(poll, first_interval=0.15)


def poll():
    scene = STATE.get("scene")
    if scene is None:
        return 0.15
    rotate = bool(scene.tool_settings.use_snap_rotate)
    snap = bool(scene.tool_settings.use_snap)

    if rotate:
        record("实按 Shift+Tab 后我们的操作生效", snap is False,
               f"use_snap_rotate={rotate} use_snap={snap}")
        finish()
        return None
    if snap:
        record("实按 Shift+Tab 后我们的操作生效", False,
               "use_snap=True：原功能抢走了键，覆盖未生效")
        finish()
        return None
    if time.time() - STATE["started"] > TIMEOUT:
        record("等待手动按键", False, f"{TIMEOUT}s 内没有检测到按键")
        finish()
        return None
    return 0.15


def finish():
    target_kmi = STATE.get("target")
    try:
        ke.unapply()
        record("复原后内置项激活", bool(target_kmi.active) if target_kmi else False,
               f"active={getattr(target_kmi, 'active', None)}")
        record("复原后 journal 清空", config.read_journal() is None)
    except Exception:
        record("复原流程", False, traceback.format_exc()[:300])
    try:
        if bpy.context.workspace:
            bpy.context.workspace.status_text_clear()
    except Exception:
        pass
    try:
        piebind.unregister()
    except Exception:
        pass
    save_results()
    bpy.app.timers.register(quit_later, first_interval=0.3)


try:
    setup()
except Exception:
    record("探针启动", False, traceback.format_exc()[:600])
    save_results()
    bpy.app.timers.register(quit_later, first_interval=0.5)