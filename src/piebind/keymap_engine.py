"""键位引擎：应用绑定、静音冲突项、复原、冲突扫描、归属判定。

设计要点
- 我们自己的键位写入 ``keyconfigs.addon``（禁用插件时 Blender 自动清理）。
- 覆盖 = 把同 combo 的既有条目 ``active=False``，并记录到 journal 以便复原。
- 复原只在「该项当前仍是我们造成的静音状态」时进行，避免拆别的插件的台。
"""

import time

import bpy

from . import config

OWN_PREFIX = "piebind."
PIE_MENU_ID = "PIEBIND_MT_pie"
CALL_PIE_IDNAME = "piebind.call_pie"

MOD_KEYS = ("ctrl", "shift", "alt", "oskey")
KEY_TEMPLATE = {
    "ctrl": False,
    "shift": False,
    "alt": False,
    "oskey": False,
    "any": False,
    "repeat": False,
    "key_modifier": "NONE",
}

# 运行时状态（不序列化）
APPLIED = {"items": [], "muted": [], "applied_at": 0.0}


# ------------------------------------------------------------------ keys
def normalize_key(key):
    out = dict(KEY_TEMPLATE)
    for name in ("ctrl", "shift", "alt", "oskey", "any", "repeat"):
        out[name] = bool(key.get(name, False))
    kmod = key.get("key_modifier") or "NONE"
    out["key_modifier"] = kmod if isinstance(kmod, str) else "NONE"
    out["type"] = str(key.get("type") or "NONE").upper()
    out["value"] = str(key.get("value") or "PRESS").upper()
    return out


_DISPLAY = {
    "LEFTMOUSE": "LMB", "RIGHTMOUSE": "RMB", "MIDDLEMOUSE": "MMB",
    "WHEELUPMOUSE": "WheelUp", "WHEELDOWNMOUSE": "WheelDown",
    "SPACE": "Space", "RET": "Enter", "NUMPAD_ENTER": "NumEnter",
    "ESC": "Esc", "TAB": "Tab", "BACKSPACE": "Backspace", "DEL": "Del",
    "HOME": "Home", "END": "End", "PAGEUP": "PgUp", "PAGEDOWN": "PgDn",
    "UP_ARROW": "Up", "DOWN_ARROW": "Down", "LEFT_ARROW": "Left", "RIGHT_ARROW": "Right",
}
_DIGITS = {
    "ONE": "1", "TWO": "2", "THREE": "3", "FOUR": "4", "FIVE": "5",
    "SIX": "6", "SEVEN": "7", "EIGHT": "8", "NINE": "9", "ZERO": "0",
}


def key_label(key):
    k = normalize_key(key)
    parts = []
    if k["ctrl"]:
        parts.append("Ctrl")
    if k["shift"]:
        parts.append("Shift")
    if k["alt"]:
        parts.append("Alt")
    if k["oskey"]:
        parts.append("OS")
    name = k["type"]
    if name in _DISPLAY:
        label = _DISPLAY[name]
    elif name.startswith("NUMPAD_"):
        tail = name[7:]
        label = "Num" + _DIGITS.get(tail, tail.title())
    elif name in _DIGITS:
        label = _DIGITS[name]
    elif len(name) == 1:
        label = name
    else:
        label = name.replace("_", " ").title()
    parts.append(label)
    if k["value"] not in ("PRESS", "ANY"):
        parts.append(f"({k['value'].lower()})")
    if k["key_modifier"] not in ("NONE", ""):
        parts.append(f"+{k['key_modifier']}")
    return "+".join(parts)


def combo_match(kmi, key):
    k = normalize_key(key)
    if kmi.type != k["type"]:
        return False
    if k["value"] not in ("ANY",) and kmi.value != k["value"]:
        return False
    for name in MOD_KEYS:
        if bool(getattr(kmi, name, False)) != k[name]:
            return False
    if bool(getattr(kmi, "any", False)) != k["any"]:
        return False
    if (getattr(kmi, "key_modifier", "NONE") or "NONE") != k["key_modifier"]:
        return False
    return True


# ------------------------------------------------------------------ layers
def iter_layers():
    wm = bpy.context.window_manager
    seen = set()
    for kc in (wm.keyconfigs.active, wm.keyconfigs.user, wm.keyconfigs.addon):
        if kc is None or kc.name in seen:
            continue
        seen.add(kc.name)
        yield kc.name, kc


def find_keymap(kc, spec):
    if kc is None or not isinstance(spec, dict):
        return None
    for km in kc.keymaps:
        if km.name != spec.get("name"):
            continue
        if spec.get("space") and km.space_type != spec["space"]:
            continue
        if spec.get("region") and km.region_type != spec["region"]:
            continue
        return km
    return None


def ensure_keymap(kc, spec):
    km = find_keymap(kc, spec)
    if km is not None:
        return km
    kwargs = {"name": spec["name"], "space_type": spec.get("space") or "EMPTY"}
    if spec.get("region"):
        kwargs["region_type"] = spec["region"]
    try:
        return kc.keymaps.new(**kwargs)
    except TypeError:
        return kc.keymaps.new(name=spec["name"], space_type=spec.get("space") or "EMPTY")


def is_own(kmi):
    return (kmi.idname or "").startswith(OWN_PREFIX)


def item_props_name(kmi):
    try:
        return getattr(kmi.properties, "name", None)
    except Exception:
        return None


def items_in(kc, spec):
    km = find_keymap(kc, spec)
    return list(km.keymap_items) if km is not None else []


def find_matching_items(kc, spec, key, skip_own=True):
    found = []
    for kmi in items_in(kc, spec):
        if skip_own and is_own(kmi):
            continue
        if combo_match(kmi, key):
            found.append(kmi)
    return found


# ------------------------------------------------------------------ operators
_OP_CACHE = {"map": None, "classes": None, "ids": None, "labels": {}}
_MENU_BASES = ("Menu", "Panel", "Operator", "Header")


def invalidate_cache():
    """插件启停 / 文件加载后清缓存（新操作符可能刚注册）。"""
    _OP_CACHE["map"] = None
    _OP_CACHE["classes"] = None
    _OP_CACHE["ids"] = None
    _OP_CACHE["labels"].clear()


def _operator_map():
    if _OP_CACHE["map"] is None:
        mapping = {}
        for cls in bpy.types.Operator.__subclasses__():
            bid = getattr(cls, "bl_idname", None)
            if bid and bid not in mapping:
                mapping[bid] = cls
        _OP_CACHE["map"] = mapping
    return _OP_CACHE["map"]


def _class_by_idname(bl_idname):
    if not bl_idname:
        return None
    if _OP_CACHE["classes"] is None:
        mapping = {}
        for base_name in _MENU_BASES:
            base = getattr(bpy.types, base_name, None)
            if base is None:
                continue
            for cls in base.__subclasses__():
                bid = getattr(cls, "bl_idname", None)
                if bid and bid not in mapping:
                    mapping[bid] = cls
        _OP_CACHE["classes"] = mapping
    return _OP_CACHE["classes"].get(bl_idname)


def resolve_owner(kmi):
    """尽量判断一条键位来自哪个插件；判断不了就返回 Blender 内置。"""
    idname = kmi.idname or ""
    if idname.startswith(OWN_PREFIX):
        return "PieBind"
    cls = None
    if idname in ("wm.call_menu", "wm.call_menu_pie", "wm.call_panel"):
        cls = _class_by_idname(item_props_name(kmi))
    if cls is None:
        cls = _operator_map().get(idname)
    module = getattr(cls, "__module__", "") if cls is not None else ""
    if not module:
        return "Blender 内置"
    try:
        addons = list(bpy.context.preferences.addons.keys())
    except Exception:
        addons = []
    for addon in sorted(addons, key=len, reverse=True):
        if module == addon or module.startswith(addon + "."):
            return addon.split(".")[-1]
    head = module.split(".")[0]
    return "Blender 内置" if head in ("bpy", "bl_operators", "bl_ui", "bl_utils") else head


def has_operator(idname):
    """bpy.ops 的属性访问不会报错，必须用 get_rna_type() 才能真正校验。"""
    if not idname or "." not in idname:
        return False
    mod_name, op_name = idname.split(".", 1)
    try:
        getattr(getattr(bpy.ops, mod_name), op_name).get_rna_type()
        return True
    except Exception:
        return False


def operator_label(idname):
    cached = _OP_CACHE["labels"].get(idname)
    if cached:
        return cached
    label = idname
    try:
        mod_name, op_name = idname.split(".", 1)
        module = getattr(bpy.ops, mod_name)
        op = getattr(module, op_name)
        label = op.get_rna_type().name or idname
    except Exception:
        pass
    _OP_CACHE["labels"][idname] = label
    return label


def poll_ok(idname):
    try:
        mod_name, op_name = idname.split(".", 1)
        op = getattr(getattr(bpy.ops, mod_name), op_name)
        return bool(op.poll())
    except Exception:
        return True


def iter_operator_ids():
    if _OP_CACHE["ids"] is None:
        ids = []
        for category in dir(bpy.ops):
            if category.startswith("_"):
                continue
            try:
                module = getattr(bpy.ops, category)
            except Exception:
                continue
            for name in dir(module):
                if name.startswith("_"):
                    continue
                ids.append(f"{category}.{name}")
        _OP_CACHE["ids"] = ids
    return iter(_OP_CACHE["ids"])


def search_operators(query="", limit=40):
    query = (query or "").strip().lower()
    hits = []
    for idname in iter_operator_ids():
        if query and query not in idname.lower():
            continue
        hits.append(idname)
        if len(hits) >= limit:
            break
    return hits


def duplicate_bindings(data):
    """检测我们自己的绑定之间是否撞键。"""
    seen = {}
    dups = []
    for binding in data.get("bindings", []):
        if not binding.get("enabled", True):
            continue
        spec = binding.get("keymap") or {}
        key = normalize_key(binding.get("key") or {})
        signature = (
            spec.get("name"), spec.get("space"), spec.get("region"),
            key["type"], key["value"], key["ctrl"], key["shift"],
            key["alt"], key["oskey"], key["any"], key["key_modifier"],
        )
        first = seen.get(signature)
        if first is None:
            seen[signature] = binding.get("id")
        else:
            dups.append({"first": first, "second": binding.get("id"), "key": key_label(key)})
    return dups


# ------------------------------------------------------------------ conflict
def scan_conflict(spec, key):
    """返回可能抢占该 combo 的条目列表（已跨层去重）。"""
    key = normalize_key(key)
    occupants = []
    seen = set()
    for layer, kc in iter_layers():
        km = find_keymap(kc, spec)
        if km is None:
            continue
        bucket = [kmi for kmi in km.keymap_items if combo_match(kmi, key)]
        active_others = [kmi for kmi in bucket if kmi.active and not is_own(kmi)]
        for kmi in active_others:
            dedupe = (kmi.idname, item_props_name(kmi))
            if dedupe in seen:
                continue
            seen.add(dedupe)
            occupants.append({
                "layer": layer,
                "owner": resolve_owner(kmi),
                "idname": kmi.idname,
                "label": getattr(kmi, "name", "") or kmi.idname,
                "modal": bool(getattr(km, "is_modal", False)),
                "severity": "warning" if len(bucket) > 1 else "blocker",
            })
    occupants.sort(key=lambda o: (o["severity"] != "blocker", o["owner"]))
    return occupants


def scan_all_plugin_bindings():
    """列出所有插件层键位，供体检页使用。"""
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    rows = []
    if kc is None:
        return rows
    for km in kc.keymaps:
        if getattr(km, "is_modal", False):
            continue
        for kmi in km.keymap_items:
            if not kmi.active:
                continue
            rows.append({
                "keymap": km.name,
                "space": km.space_type,
                "key": key_label({
                    "type": kmi.type,
                    "value": kmi.value,
                    "ctrl": kmi.ctrl,
                    "shift": kmi.shift,
                    "alt": kmi.alt,
                    "oskey": getattr(kmi, "oskey", False),
                    "any": getattr(kmi, "any", False),
                    "key_modifier": getattr(kmi, "key_modifier", "NONE"),
                }),
                "idname": kmi.idname,
                "owner": resolve_owner(kmi),
            })
    rows.sort(key=lambda r: (r["owner"], r["keymap"], r["key"]))
    return rows


# ------------------------------------------------------------------ apply
def _set_props(kmi, props):
    if not props:
        return
    for name, value in props.items():
        try:
            setattr(kmi.properties, name, value)
        except Exception:
            continue


def _new_item(km, idname, key):
    k = normalize_key(key)
    kwargs = dict(
        type=k["type"],
        value=k["value"] if k["value"] != "ANY" else "PRESS",
        any=k["any"],
        shift=k["shift"],
        ctrl=k["ctrl"],
        alt=k["alt"],
        oskey=k["oskey"],
        key_modifier=k["key_modifier"],
        repeat=k["repeat"],
    )
    try:
        return km.keymap_items.new(idname, **kwargs)
    except TypeError:
        kwargs.pop("repeat", None)
        kwargs.pop("key_modifier", None)
        return km.keymap_items.new(idname, **kwargs)


def _journal_entries(muted):
    entries = []
    for record in muted:
        entries.append({
            "kc": record["kc"],
            "keymap": record["keymap"],
            "key": record["key"],
            "idname": record["idname"],
            "props_name": record.get("props_name"),
        })
    return entries


def _locate_items(entry):
    """按 journal 记录找到当前仍存在的键位条目。"""
    wm = bpy.context.window_manager
    for kc in list(wm.keyconfigs):
        if kc.name != entry.get("kc"):
            continue
        km = find_keymap(kc, entry.get("keymap") or {})
        if km is None:
            continue
        for kmi in km.keymap_items:
            if kmi.idname != entry.get("idname"):
                continue
            if not combo_match(kmi, entry.get("key") or {}):
                continue
            expected = entry.get("props_name")
            if expected is not None and item_props_name(kmi) != expected:
                continue
            yield km, kmi


def restore_entries(entries):
    """恢复指定 journal 条目；只恢复仍处于静音状态的项。"""
    restored = 0
    for entry in entries or []:
        for _km, kmi in _locate_items(entry):
            if not kmi.active:
                try:
                    kmi.active = True
                    restored += 1
                except Exception:
                    pass
    return restored


def _mute(records, spec, key, dry_run):
    """把冲突项静音；返回记录。dry_run 时只收集不修改。"""
    for layer, kc in iter_layers():
        km = find_keymap(kc, spec)
        if km is None:
            continue
        for kmi in list(km.keymap_items):
            if is_own(kmi) or not kmi.active:
                continue
            if not combo_match(kmi, key):
                continue
            records.append({
                "kc": kc.name,
                "keymap": dict(spec),
                "key": normalize_key(key),
                "idname": kmi.idname,
                "props_name": item_props_name(kmi),
                "owner": resolve_owner(kmi),
            })
            if not dry_run:
                try:
                    kmi.active = False
                except Exception:
                    pass
    return records


def apply(data, dry_run=False):
    """应用全部启用中的绑定；幂等。"""
    if not dry_run:
        # 重新应用前先把上一轮造成的静音恢复，避免状态漂移
        if APPLIED.get("muted"):
            restore_entries(APPLIED["muted"])
            APPLIED["muted"] = []
        purge()

    report = {"created": [], "muted": [], "skipped": [], "dry_run": bool(dry_run),
              "duplicates": duplicate_bindings(data)}
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc is None:
        report["skipped"].append({"reason": "addon keyconfig unavailable"})
        return report

    created = []
    muted = []

    for binding in data.get("bindings", []):
        if not binding.get("enabled", True):
            continue
        target = binding.get("target") or {}
        kind = target.get("kind", "operator")
        props = target.get("props") or {}

        if kind == "pie":
            pie = config.find_pie(data, target.get("id"))
            if pie is None:
                report["skipped"].append({"binding": binding.get("id"), "reason": "pie missing"})
                continue
            idname = CALL_PIE_IDNAME
            props = {"pie_id": pie["id"]}
        else:
            idname = target.get("id") or ""
            if not has_operator(idname):
                report["skipped"].append({"binding": binding.get("id"), "reason": f"operator missing: {idname}"})
                continue

        spec = binding.get("keymap") or {}
        if not spec.get("name"):
            report["skipped"].append({"binding": binding.get("id"), "reason": "keymap missing"})
            continue
        key = normalize_key(binding.get("key") or {})

        km = find_keymap(kc, spec) if dry_run else ensure_keymap(kc, spec)
        entry = {
            "binding": binding.get("id"),
            "idname": idname,
            "key": key_label(key),
            "keymap": f'{spec.get("name")} [{spec.get("space", "")}]',
        }
        if not dry_run:
            try:
                kmi = _new_item(km, idname, key)
            except Exception as exc:
                report["skipped"].append({"binding": binding.get("id"), "reason": f"new item failed: {exc}"})
                continue
            _set_props(kmi, props)
            created.append({"kc": kc.name, "keymap": dict(spec), "key": key, "idname": idname})
        report["created"].append(entry)

        if binding.get("force_override"):
            _mute(muted, spec, key, dry_run)

    report["muted"] = [
        {"owner": m.get("owner"), "idname": m["idname"], "kc": m["kc"], "key": key_label(m["key"])}
        for m in muted
    ]

    if dry_run:
        report["would_mute"] = len(muted)
        return report

    APPLIED["items"] = created
    APPLIED["muted"] = muted
    APPLIED["applied_at"] = time.time()
    if muted:
        config.write_journal({"version": 1, "entries": _journal_entries(muted)})
    else:
        config.clear_journal()
    return report


def purge():
    """清理我们自己的键位条目（幂等注册的关键）。"""
    wm = bpy.context.window_manager
    removed = 0
    kc = wm.keyconfigs.addon
    if kc is not None:
        for km in list(kc.keymaps):
            for kmi in list(km.keymap_items):
                if is_own(kmi):
                    try:
                        km.keymap_items.remove(kmi)
                        removed += 1
                    except Exception:
                        pass
    APPLIED["items"] = []
    return removed


def unapply():
    """移除我们的键位并恢复被静音的条目。"""
    wm = bpy.context.window_manager
    removed = 0
    restored = 0

    kc = wm.keyconfigs.addon
    if kc is not None:
        for km in list(kc.keymaps):
            for kmi in list(km.keymap_items):
                if not is_own(kmi):
                    continue
                try:
                    km.keymap_items.remove(kmi)
                    removed += 1
                except Exception:
                    pass

    entries = []
    journal = config.read_journal()
    if journal:
        entries.extend(journal.get("entries") or [])
    entries.extend(_journal_entries(APPLIED.get("muted") or []))

    restored = restore_entries(entries)

    APPLIED["items"] = []
    APPLIED["muted"] = []
    config.clear_journal()
    return {"removed": removed, "restored": restored}


def reconcile_journal():
    """启动时按 journal 恢复残留静音（崩溃自愈）。"""
    journal = config.read_journal()
    if not journal:
        return {"restored": 0, "pending": 0}
    restored = 0
    for entry in journal.get("entries") or []:
        for _km, kmi in _locate_items(entry):
            if not kmi.active:
                try:
                    kmi.active = True
                    restored += 1
                except Exception:
                    pass
    config.clear_journal()
    return {"restored": restored}