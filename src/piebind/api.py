"""进程内 API：给 agent / 脚本调用，无需网络。

用法::

    import piebind.api as api
    api.call("describe")
    api.call("search_operators", query="bevel")
    api.call("create_pie", label="建模速取", slots=[
        {"pos": "W", "idname": "mesh.bevel"},
        {"pos": "N", "idname": "mesh.fill_holes"},
    ])
    api.call("bind", keymap={"name": "3D View", "space": "VIEW_3D"},
             key={"type": "E", "alt": True},
             target={"kind": "pie", "id": "pie_xxx"}, dry_run=True)
    api.call("apply")
"""

import json

import bpy

from . import config, keymap_engine as ke
from . import ops

API_VERSION = 1

ACTIONS = {
    "describe": "返回本 API 的动作目录与参数说明",
    "list_keymaps": "列出可用 keymap；参数 query, limit",
    "search_operators": "搜索操作符；参数 query, limit",
    "list_pies": "列出饼菜单",
    "create_pie": "新建饼；参数 label, slots=[{pos, idname, text?, props?}]",
    "delete_pie": "删除饼；参数 pie_id",
    "set_slot": "写入/覆盖槽位；参数 pie_id, pos, idname, text?, props?",
    "remove_slot": "清空槽位；参数 pie_id, pos",
    "list_bindings": "列出绑定",
    "bind": "新建绑定；参数 keymap, key, target, force_override?",
    "unbind": "删除绑定；参数 binding_id",
    "set_enabled": "启用/停用绑定；参数 binding_id, enabled",
    "check_conflict": "检测键位冲突；参数 keymap, key",
    "plugin_bindings": "列出所有插件层键位及归属",
    "apply": "应用配置；参数 dry_run?",
    "unapply": "移除键位并复原",
    "export_config": "导出配置；参数 path",
    "import_config": "导入配置；参数 path, apply?",
    "diagnostics": "返回环境/键位诊断快照（路径已脱敏）",
}


def _ok(data=None, **extra):
    payload = {"ok": True, "api_version": API_VERSION}
    if data is not None:
        payload["data"] = data
    payload.update(extra)
    return payload


def _err(code, message, hint=""):
    return {
        "ok": False,
        "api_version": API_VERSION,
        "error": {"code": code, "message": message, "hint": hint},
    }


def describe():
    return _ok({"version": "0.1.0", "actions": ACTIONS})


def list_keymaps(query="", limit=200):
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.active or wm.keyconfigs.user
    out = []
    if kc is None:
        return out
    seen = set()
    q = (query or "").lower()
    for km in kc.keymaps:
        if getattr(km, "is_modal", False):
            continue
        ident = (km.name, km.space_type, km.region_type)
        if ident in seen:
            continue
        seen.add(ident)
        if q and q not in km.name.lower():
            continue
        out.append({"name": km.name, "space": km.space_type, "region": km.region_type})
        if len(out) >= limit:
            break
    return out


def search_operators(query="", limit=20):
    ids = ke.search_operators(query, limit=limit)
    return [{"idname": i, "label": ke.operator_label(i)} for i in ids]


def list_pies():
    return config.load().get("pies", [])


def create_pie(label="新建饼", slots=None):
    data = config.load()
    created = config.create_pie(data, label or "新建饼")
    for slot in slots or []:
        pos = str(slot.get("pos", "")).upper()
        idname = slot.get("idname") or ""
        if pos not in ("W", "E", "S", "N", "NW", "NE", "SW", "SE"):
            continue
        if not ke.has_operator(idname):
            return _err("OP_NOT_FOUND", f"操作符不存在：{idname}", "试试 api.call('search_operators', query=...)")
        config.set_slot(data, created["id"], pos, {
            "kind": "operator",
            "idname": idname,
            "text": slot.get("text") or "",
            "props": slot.get("props") or {},
        })
    config.save(data)
    return _ok(created)


def delete_pie(pie_id):
    data = config.load()
    if config.find_pie(data, pie_id) is None:
        return _err("PIE_NOT_FOUND", f"饼不存在：{pie_id}")
    config.delete_pie(data, pie_id)
    config.save(data)
    return _ok({"deleted": pie_id})


def set_slot(pie_id, pos, idname, text="", props=None):
    data = config.load()
    if config.find_pie(data, pie_id) is None:
        return _err("PIE_NOT_FOUND", f"饼不存在：{pie_id}")
    if not ke.has_operator(idname):
        return _err("OP_NOT_FOUND", f"操作符不存在：{idname}")
    ok = config.set_slot(data, pie_id, str(pos).upper(), {
        "kind": "operator", "idname": idname, "text": text, "props": props or {},
    })
    config.save(data)
    return _ok({"pie_id": pie_id, "pos": pos}) if ok else _err("BAD_SLOT", "槽位写入失败")


def remove_slot(pie_id, pos):
    data = config.load()
    config.set_slot(data, pie_id, str(pos).upper(), None)
    config.save(data)
    return _ok({"pie_id": pie_id, "pos": pos})


def list_bindings():
    return config.load().get("bindings", [])


def _normalize_keymap(keymap):
    if isinstance(keymap, str):
        name = keymap
        for row in list_keymaps(query=name, limit=50):
            if row["name"] == name:
                return row
        return {"name": name, "space": "EMPTY", "region": "WINDOW"}
    if isinstance(keymap, dict) and keymap.get("name"):
        return {
            "name": keymap["name"],
            "space": keymap.get("space") or "EMPTY",
            "region": keymap.get("region") or "WINDOW",
        }
    return None


def bind(keymap, key, target, force_override=False, dry_run=False):
    spec = _normalize_keymap(keymap)
    if spec is None:
        return _err("BAD_KEYMAP", "keymap 需要 {name, space?, region?} 或字符串")
    norm_key = ke.normalize_key(key)
    if norm_key["type"] in ("NONE", ""):
        return _err("BAD_KEY", "key.type 必须给出，例如 ONE / E / LEFTMOUSE")

    kind = (target or {}).get("kind", "operator")
    if kind == "pie":
        data = config.load()
        if config.find_pie(data, target.get("id")) is None:
            return _err("PIE_NOT_FOUND", f"饼不存在：{target.get('id')}")
    else:
        idname = (target or {}).get("id") or ""
        if not ke.has_operator(idname):
            return _err("OP_NOT_FOUND", f"操作符不存在：{idname}")

    occupants = ke.scan_conflict(spec, norm_key)
    data = config.load()
    binding = {
        "id": config.new_id("bd"),
        "enabled": True,
        "force_override": bool(force_override),
        "keymap": spec,
        "key": norm_key,
        "target": dict(target or {}),
    }
    if dry_run:
        return _ok({
            "would_bind": binding,
            "conflicts": occupants,
            "would_mute": [o for o in occupants] if force_override else [],
        })
    data["bindings"].append(binding)
    config.save(data)
    report = ke.apply(data)
    return _ok({"binding": binding, "applied": report})


def unbind(binding_id):
    data = config.load()
    before = len(data["bindings"])
    data["bindings"] = [b for b in data["bindings"] if b.get("id") != binding_id]
    if len(data["bindings"]) == before:
        return _err("BINDING_NOT_FOUND", f"绑定不存在：{binding_id}")
    config.save(data)
    ke.apply(data)
    return _ok({"deleted": binding_id})


def set_enabled(binding_id, enabled=True):
    data = config.load()
    for binding in data["bindings"]:
        if binding.get("id") == binding_id:
            binding["enabled"] = bool(enabled)
            config.save(data)
            ke.apply(data)
            return _ok({"binding_id": binding_id, "enabled": bool(enabled)})
    return _err("BINDING_NOT_FOUND", f"绑定不存在：{binding_id}")


def check_conflict(keymap, key):
    spec = _normalize_keymap(keymap)
    if spec is None:
        return _err("BAD_KEYMAP", "keymap 参数不合法")
    return _ok({"keymap": spec, "key": ke.key_label(key), "conflicts": ke.scan_conflict(spec, key)})


def plugin_bindings():
    return _ok({"rows": ke.scan_all_plugin_bindings()})


def apply(dry_run=False):
    data = config.load()
    return _ok(ke.apply(data, dry_run=bool(dry_run)))


def unapply():
    return _ok(ke.unapply())


def export_config(path):
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(config.load(), fh, ensure_ascii=False, indent=1)
    except Exception as exc:
        return _err("IO_ERROR", str(exc))
    return _ok({"path": path})


def diagnostics_snapshot():
    from . import diagnostics
    return _ok(diagnostics.build_report())


def import_config(path, apply_after=False):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except Exception as exc:
        return _err("IO_ERROR", str(exc))
    data = config._coerce(payload)
    config.save(data)
    if apply_after:
        ke.apply(data)
    return _ok({"path": path, "pies": len(data["pies"]), "bindings": len(data["bindings"])})


_DISPATCH = {
    "describe": lambda **kw: describe(),
    "list_keymaps": lambda **kw: _ok(list_keymaps(kw.get("query", ""), kw.get("limit", 200))),
    "search_operators": lambda **kw: _ok(search_operators(kw.get("query", ""), kw.get("limit", 20))),
    "list_pies": lambda **kw: _ok(list_pies()),
    "create_pie": lambda **kw: create_pie(kw.get("label", "新建饼"), kw.get("slots")),
    "delete_pie": lambda **kw: delete_pie(kw.get("pie_id")),
    "set_slot": lambda **kw: set_slot(kw.get("pie_id"), kw.get("pos"), kw.get("idname", ""),
                                      kw.get("text", ""), kw.get("props")),
    "remove_slot": lambda **kw: remove_slot(kw.get("pie_id"), kw.get("pos")),
    "list_bindings": lambda **kw: _ok(list_bindings()),
    "bind": lambda **kw: bind(kw.get("keymap"), kw.get("key"), kw.get("target"),
                              kw.get("force_override", False), kw.get("dry_run", False)),
    "unbind": lambda **kw: unbind(kw.get("binding_id")),
    "set_enabled": lambda **kw: set_enabled(kw.get("binding_id"), kw.get("enabled", True)),
    "check_conflict": lambda **kw: check_conflict(kw.get("keymap"), kw.get("key")),
    "plugin_bindings": lambda **kw: plugin_bindings(),
    "apply": lambda **kw: apply(kw.get("dry_run", False)),
    "unapply": lambda **kw: unapply(),
    "export_config": lambda **kw: export_config(kw.get("path", "")),
    "import_config": lambda **kw: import_config(kw.get("path", ""), kw.get("apply", False)),
    "diagnostics": lambda **kw: diagnostics_snapshot(),
}


def call(action, **kwargs):
    """单入口调用；永远返回可 JSON 序列化的 dict。"""
    handler = _DISPATCH.get(action)
    if handler is None:
        near = difflib_close(action)
        return _err("UNKNOWN_ACTION", f"未知动作：{action}",
                    f"可用动作见 api.call('describe')；最接近的是：{near}" if near else "")
    try:
        return handler(**kwargs)
    except Exception as exc:
        return _err("INTERNAL_ERROR", f"{type(exc).__name__}: {exc}")


def difflib_close(action):
    import difflib
    matches = difflib.get_close_matches(str(action), list(_DISPATCH), n=1)
    return matches[0] if matches else ""