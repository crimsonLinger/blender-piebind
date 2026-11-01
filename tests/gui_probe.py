"""GUI 覆盖探针：验证强制覆盖在真实内置键位上是否生效。

目标键位：3D View 里 Shift+Tab（`wm.context_toggle` → tool_settings.use_snap）。
我们的绑定：同一组合键，但切换 `scene.tool_settings.use_snap_rotate`。

判据：按下后
- 覆盖生效 → use_snap_rotate == True 且 use_snap == False
- 覆盖失效 → use_snap == True（原功能抢走了键）

由 tests/run_gui_probe.ps1 启动；同时写 ready.json 供外部 SendKeys 使用。
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

SENDKEYS_NAMES = {"TAB": "{TAB}", "RET": "{ENTER}", "ESC": "{ESC}", "SPACE": " "}
DIGITS = {"ONE": "1", "TWO": "2", "THREE": "3", "FOUR": "4", "FIVE": "5",
          "SIX": "6", "SEVEN": "7", "EIGHT": "8", "NINE": "9", "ZERO": "0"}


def record(name, ok, detail=""):
    RESULTS.append({"name": name, "ok": bool(ok), "detail": str(detail)[:400]})
    print(f"[PROBE] {'OK  ' if ok else 'FAIL'} {name}  {detail}")


def save_results():
    with open(RESULT, "w", encoding="utf-8") as fh:
        json.dump(RESULTS, fh, ensure_ascii=False, indent=1)


def to_sendkeys(key):
    mods = ""
    if key.get("ctrl"):
        mods += "^"
    if key.get("shift"):
        mods += "+"
    if key.get("alt"):
        mods += "%"
    name = key.get("type", "")
    if name in SENDKEYS_NAMES:
        token = SENDKEYS_NAMES[name]
    elif name in DIGITS:
        token = DIGITS[name]
    elif name.startswith("F") and name[1:].isdigit():
        token = "{" + name + "}"
    elif len(name) == 1:
        token = name.lower()
    else:
        token = "{TAB}"
    return mods + token


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
        if data_path != "tool_settings.use_snap":
            continue
        if kmi.ctrl or kmi.alt:
            continue
        return target_km, kmi
    return target_km, None


def quit_later():
    bpy.ops.wm.quit_blender()


def setup():
    piebind.register()
    scene = bpy.context.scene
    wm = bpy.context.window_manager
    target_km, target_kmi = find_target()
    if target_kmi is None:
        record("找到内置键位", False, "3D View 里没有 use_snap 的 context_toggle")
        save_results()
        bpy.app.timers.register(quit_later, first_interval=0.3)
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
    })
    record(
        "找到内置键位", True,
        f"{ke.key_label(combo)} → {target_kmi.idname} "
        f"({getattr(target_kmi.properties, 'data_path', '')})",
    )

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
            "props": {"data_path": "scene.tool_settings.use_snap_rotate"},
        },
    })
    config.save(data)
    report = ke.apply(data)
    STATE["report"] = report

    record("创建我们的键位", len(report["created"]) == 1 and not report["skipped"], report)
    record("内置项被静音", target_kmi.active is False, f"active={target_kmi.active}")
    record("覆盖记录已写入", len(report["muted"]) >= 1, report["muted"])
    record("journal 已落盘", config.read_journal() is not None)

    mirrors = {}
    for kc in wm.keyconfigs:
        count = 0
        for km in kc.keymaps:
            for kmi in km.keymap_items:
                if (kmi.idname or "").startswith("piebind."):
                    count += 1
        mirrors[kc.name] = count
    record("镜像层统计", True, mirrors)

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

    payload = {
        "pid": os.getpid(),
        "key": combo,
        "label": ke.key_label(combo),
        "sendkeys": to_sendkeys(combo),
        "expect": "use_snap_rotate == True and use_snap == False",
    }
    with open(READY, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)

    bpy.app.timers.register(wait_for_key, first_interval=0.2)


def _focus_note():
    try:
        with open(os.path.join(OUT, "focus.json"), "r", encoding="utf-8") as fh:
            info = json.load(fh)
        return f"focus={info.get('focused')}"
    except Exception:
        return "focus=unknown"


def wait_for_key():
    scene = STATE.get("scene")
    if os.path.exists(STOP):
        rotate = bool(scene.tool_settings.use_snap_rotate) if scene else None
        snap = bool(scene.tool_settings.use_snap) if scene else None
        record(
            "实按热键后我们的操作生效",
            rotate is True and snap is False,
            f"use_snap_rotate={rotate} use_snap={snap} {_focus_note()}"
            + ("（use_snap=True 说明原功能抢走了键）" if snap else ""),
        )
        phase_cleanup()
        return None
    if time.time() - STATE["started"] > 120:
        record("等待按键", False, "120s 超时，未收到外部按键信号")
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
    bpy.app.timers.register(quit_later, first_interval=0.2)


def main():
    try:
        setup()
    except Exception:
        record("探针启动", False, traceback.format_exc()[:600])
        save_results()
        bpy.app.timers.register(quit_later, first_interval=0.3)


main()