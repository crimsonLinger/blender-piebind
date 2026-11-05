"""键位引擎：应用绑定、静音冲突项、复原、冲突扫描、归属判定。

设计要点
- 我们自己的键位写入 ``keyconfigs.addon``（禁用插件时 Blender 自动清理）。
- 覆盖 = 把同 combo 的既有条目 ``active=False``，并记录到 journal 以便复原。
- 复原只在「该项当前仍是我们造成的静音状态」时进行，避免拆别的插件的台。
"""

import time

import bpy

from . import config, keyspec

OWN_PREFIX = "piebind."
PIE_MENU_ID = "PIEBIND_MT_pie"
CALL_PIE_IDNAME = "piebind.call_pie"
DISPATCH_IDNAME = "piebind.dispatch"

# 动态绑定统一挂在 Window 键位层：区域 keymap（3D View 等）在运行时新增的条目
# 不会被分发（实测），而 Window 层会，所以用一个带区域判断的分发器落地。
WINDOW_SPEC = {"name": "Window", "space": "EMPTY", "region": "WINDOW"}

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


def same_combo(a, b):
    """两个 key 字典是否表示同一个组合（忽略 value / repeat）。"""
    ka, kb = normalize_key(a), normalize_key(b)
    fields = ("type", "ctrl", "shift", "alt", "oskey", "key_modifier")
    return all(ka.get(name) == kb.get(name) for name in fields)


_DISPLAY = {
    # 全部用大写：Blender 会把与界面文案完全相同的字符串自动翻译
    # （实测 Tab→选项卡、Space→空间、Shift→移位、Home→主目录、Del→删除），
    # 大写形式不在翻译表里，能稳定按原样显示。
    "LEFTMOUSE": "LMB", "RIGHTMOUSE": "RMB", "MIDDLEMOUSE": "MMB",
    "BUTTON4MOUSE": "M4", "BUTTON5MOUSE": "M5",
    "BUTTON6MOUSE": "M6", "BUTTON7MOUSE": "M7",
    "WHEELUPMOUSE": "WHEELUP", "WHEELDOWNMOUSE": "WHEELDOWN",
    "SPACE": "SPACE", "RET": "ENTER", "NUMPAD_ENTER": "NUM ENTER",
    "ESC": "ESC", "TAB": "TAB", "BACKSPACE": "BACKSPACE", "DEL": "DEL",
    "HOME": "HOME", "END": "END", "PAGEUP": "PGUP", "PAGEDOWN": "PGDN",
    "UP_ARROW": "UP", "DOWN_ARROW": "DOWN", "LEFT_ARROW": "LEFT", "RIGHT_ARROW": "RIGHT",
}
_DIGITS = {
    "ONE": "1", "TWO": "2", "THREE": "3", "FOUR": "4", "FIVE": "5",
    "SIX": "6", "SEVEN": "7", "EIGHT": "8", "NINE": "9", "ZERO": "0",
}


def key_label(key):
    k = normalize_key(key)
    parts = []
    if k["ctrl"]:
        parts.append("CTRL")
    if k["shift"]:
        parts.append("SHIFT")
    if k["alt"]:
        parts.append("ALT")
    if k["oskey"]:
        parts.append("OS")
    name = k["type"]
    if name in _DISPLAY:
        label = _DISPLAY[name]
    elif name.startswith("NUMPAD_"):
        tail = name[7:]
        label = "NUM" + _DIGITS.get(tail, tail.upper())
    elif name in _DIGITS:
        label = _DIGITS[name]
    elif len(name) == 1:
        label = name.upper()
    else:
        label = name.replace("_", " ").upper()
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


# ------------------------------------------------------- 内置快捷键（只读展示）
_SHORTCUT_CACHE = {"map": None, "built": 0.0}
_SHORTCUT_TTL = 30.0


def shortcut_map(refresh=False):
    """idname -> [(keymap 名, 键位标签)]，只读地汇总 Blender 现有键位。

    结果缓存 30 秒；优先 3D 视图 / 全局（跨度 EMPTY）的条目。
    """
    now = time.time()
    cached = _SHORTCUT_CACHE["map"]
    if cached is not None and not refresh and (now - _SHORTCUT_CACHE["built"]) < _SHORTCUT_TTL:
        return cached

    order = {"Blender": 0, "Blender user": 1, "Blender addon": 2}
    try:
        configs = sorted(
            bpy.context.window_manager.keyconfigs, key=lambda kc: order.get(kc.name, 9)
        )
    except Exception:
        configs = []

    collected = {}
    for kc in configs:
        for km in kc.keymaps:
            preferred = km.space_type in ("EMPTY", "VIEW_3D")
            for kmi in km.keymap_items:
                try:
                    if not kmi.active or not kmi.idname:
                        continue
                except Exception:
                    continue
                label = key_label({
                    "type": kmi.type,
                    "ctrl": kmi.ctrl,
                    "shift": kmi.shift,
                    "alt": kmi.alt,
                    "oskey": kmi.oskey,
                })
                rank = 0 if preferred else 1
                collected.setdefault(kmi.idname, []).append((rank, km.name, label))

    result = {}
    for idname, rows in collected.items():
        rows.sort(key=lambda row: (row[0], row[1]))
        seen_labels = set()
        pairs = []
        for _rank, km_name, label in rows:
            if label in seen_labels:
                continue
            seen_labels.add(label)
            pairs.append((km_name, label))
        result[idname] = pairs
    _SHORTCUT_CACHE.update(map=result, built=now)
    return result


def shortcut_for(idname, limit=2):
    """返回该操作符在 Blender 键位里已存在的快捷键（只读展示）；没有则空串。"""
    rows = shortcut_map().get(idname or "") or []
    labels = []
    for _km_name, label in rows:
        if label not in labels:
            labels.append(label)
        if len(labels) >= limit:
            break
    return " / ".join(labels)


def shortcut_query_label(text):
    """把 'h' / 'shift+h' / 'F8' 归一成展示用标签；不像按键写法时返回空串。"""
    try:
        parsed = keyspec.parse_key_text(text)
    except Exception:
        return ""
    if not parsed or not parsed.get("type"):
        return ""
    return key_label(parsed)


def shortcut_search(query):
    """按内置键位搜索操作符：'H' / 'SHIFT+H' / 'F8' …"""
    label = shortcut_query_label(query)
    if not label:
        return []
    hits = []
    for idname, rows in shortcut_map().items():
        for _km_name, row_label in rows:
            if row_label == label:
                hits.append(idname)
                break
    return hits


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


def target_keyconfig():
    """运行时绑定必须写进 active —— 写 addon 层的条目在当前进程不会参与分发。"""
    wm = bpy.context.window_manager
    return wm.keyconfigs.active or wm.keyconfigs.addon


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
    global _OP_INDEX, _OP_INDEX_BY_ID
    _OP_CACHE["map"] = None
    _OP_CACHE["classes"] = None
    _OP_CACHE["ids"] = None
    _OP_CACHE["labels"].clear()
    _OP_INDEX = None
    _OP_INDEX_BY_ID = None
    try:
        import os as _os
        _os.remove(_index_path())
    except Exception:
        pass


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
    # 只保留 ASCII 标签：某些语言/字体组合下非 ASCII 的枚举标签会显示成乱码
    if not label.isascii():
        label = idname.split(".", 1)[-1].replace("_", " ").title()
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


# ------------------------------------------------------------------ op index
# 中文搜索需要「id -> 英文名 -> 本地化名」的索引；一次性构建后缓存到磁盘。
_OP_INDEX = None
_OP_INDEX_BY_ID = None
_INDEX_FORMAT = 2


def _index_path():
    locale = getattr(bpy.app.translations, "locale", "en") or "en"
    return config.path_of(f"op_index_v{_INDEX_FORMAT}_{bpy.app.version_string}_{locale}.json")


def _localized_operator_name(english):
    """操作符名字在 Blender 的 "Operator" 上下文里翻译；先试上下文再退回 iface。"""
    if not english:
        return ""
    try:
        translations = bpy.app.translations
    except Exception:
        return english
    for context in ("Operator", None):
        try:
            text = translations.pgettext_iface(english, context) if context else \
                translations.pgettext_iface(english)
        except Exception:
            text = ""
        if text and text != english:
            return text
    return english


def _build_index():
    rows = []
    for idname in iter_operator_ids():
        english = idname
        try:
            mod_name, op_name = idname.split(".", 1)
            op = getattr(getattr(bpy.ops, mod_name), op_name)
            english = op.get_rna_type().name or idname
        except Exception:
            pass
        localized = _localized_operator_name(english)
        rows.append([idname, english, localized])
    return rows


def operator_index():
    global _OP_INDEX, _OP_INDEX_BY_ID
    if _OP_INDEX is not None:
        return _OP_INDEX
    path = _index_path()
    try:
        import json as _json
        with open(path, "r", encoding="utf-8") as fh:
            payload = _json.load(fh)
        if payload.get("format") != _INDEX_FORMAT:
            raise ValueError("stale operator index")
        rows = payload.get("rows") or []
        if rows:
            _OP_INDEX = rows
            _OP_INDEX_BY_ID = {row[0]: row for row in rows}
            return _OP_INDEX
    except Exception:
        pass
    _OP_INDEX = _build_index()
    _OP_INDEX_BY_ID = {row[0]: row for row in _OP_INDEX}
    try:
        import json as _json
        with open(path, "w", encoding="utf-8") as fh:
            _json.dump({
                "format": _INDEX_FORMAT,
                "version": bpy.app.version_string,
                "locale": getattr(bpy.app.translations, "locale", "en"),
                "rows": _OP_INDEX,
            }, fh, ensure_ascii=False)
    except Exception:
        pass
    return _OP_INDEX


def operator_label_zh(idname):
    operator_index()
    row = _OP_INDEX_BY_ID.get(idname) if _OP_INDEX_BY_ID else None
    if row and row[2]:
        return row[2]
    return operator_label(idname)


def search_operators(query="", limit=40):
    raw = (query or "").strip()
    q = raw.casefold()
    hits = []
    # 键位写法（H / SHIFT+H / F8）先把绑定在这些键上的操作符排在前面
    if q:
        for idname in shortcut_search(raw):
            if idname not in hits:
                hits.append(idname)
            if len(hits) >= limit:
                return hits
    # 文本匹配：前缀命中优先，其余按索引顺序
    scored = []
    for order, (idname, english, localized) in enumerate(operator_index()):
        if q:
            low_id = idname.casefold()
            low_en = str(english).casefold()
            low_loc = str(localized).casefold()
            if q not in low_id and q not in low_en and q not in low_loc:
                continue
            prefix = (low_loc.startswith(q) or low_en.startswith(q) or low_id.startswith(q))
            score = 0 if prefix else 1
        else:
            score = 0
        scored.append((score, order, idname))
    scored.sort(key=lambda row: (row[0], row[1]))
    for _score, _order, idname in scored:
        if idname in hits:
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
        active_others = [kmi for kmi in bucket if kmi.active and not is_ours_item(km, kmi)]
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
    """与手工验证过的写法保持一致：只显式传非默认值。

    实测（Blender 5.2）用最小 kwargs 写进 active/Window 的条目能被正常分发；
    全量显式传参的版本行为未确认，因此这里保守处理。
    """
    k = normalize_key(key)
    value = k["value"] if k["value"] != "ANY" else "PRESS"
    kwargs = {}
    if k["any"]:
        kwargs["any"] = True
    if k["shift"]:
        kwargs["shift"] = True
    if k["ctrl"]:
        kwargs["ctrl"] = True
    if k["alt"]:
        kwargs["alt"] = True
    if k["oskey"]:
        kwargs["oskey"] = True
    if k["key_modifier"] not in ("NONE", ""):
        kwargs["key_modifier"] = k["key_modifier"]
    if k["repeat"]:
        kwargs["repeat"] = True
    try:
        return km.keymap_items.new(idname, k["type"], value, **kwargs)
    except TypeError:
        for extra in ("key_modifier", "repeat", "oskey"):
            kwargs.pop(extra, None)
        return km.keymap_items.new(idname, k["type"], value, **kwargs)


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


# 我们创建的条目签名（目标可能是原生操作符，idname 不带 piebind. 前缀）
_OWNED = []


def refresh_owned():
    global _OWNED
    _OWNED = config.read_owned()


def _props_snapshot(kmi):
    """记录条目的操作符属性，用于区分「同一操作符但参数不同」的键位。"""
    out = {}
    try:
        rna = kmi.properties.bl_rna
    except Exception:
        return out
    for prop in rna.properties:
        if prop.identifier in ("rna_type",):
            continue
        try:
            value = getattr(kmi.properties, prop.identifier)
        except Exception:
            continue
        if isinstance(value, (bool, int, float, str)):
            out[prop.identifier] = value
    return out


def _signature(km, kmi):
    return {
        "keymap": km.name,
        "region": km.region_type,
        "type": kmi.type,
        "value": kmi.value,
        "ctrl": bool(kmi.ctrl),
        "shift": bool(kmi.shift),
        "alt": bool(kmi.alt),
        "oskey": bool(getattr(kmi, "oskey", False)),
        "any": bool(getattr(kmi, "any", False)),
        "key_modifier": getattr(kmi, "key_modifier", "NONE") or "NONE",
        "idname": kmi.idname,
        "props": _props_snapshot(kmi),
    }


def signature_matches(sig, km, kmi):
    if sig.get("keymap") != km.name:
        return False
    if sig.get("idname") != kmi.idname:
        return False
    if sig.get("type") != kmi.type or sig.get("value") != kmi.value:
        return False
    for name in ("ctrl", "shift", "alt", "oskey", "any"):
        if bool(sig.get(name)) != bool(getattr(kmi, name, False)):
            return False
    if (sig.get("key_modifier") or "NONE") != (getattr(kmi, "key_modifier", "NONE") or "NONE"):
        return False
    expected = sig.get("props") or {}
    current = _props_snapshot(kmi)
    if expected and current != expected:
        return False
    return True


def is_ours_item(km, kmi):
    if is_own(kmi):
        return True
    for sig in _OWNED:
        if signature_matches(sig, km, kmi):
            return True
    return False


def _mute(records, spec, key, dry_run, skip_ids=None):
    """把冲突项静音；返回记录。dry_run 时只收集不修改。

    skip_ids: {(keymap_name, item_id)} —— 我们自己刚创建的条目，绝不能静音自己。
    """
    skip_ids = skip_ids or set()
    for layer, kc in iter_layers():
        km = find_keymap(kc, spec)
        if km is None:
            continue
        for kmi in list(km.keymap_items):
            if is_own(kmi) or not kmi.active:
                continue
            if (km.name, kmi.id) in skip_ids:
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


def _patch_takeover(binding_id, spec, key, allow_fallback=False):
    """就地接管：把命中的既有条目改写成分发器，原样记录以便复原。

    实测：区域 keymap 里被静音的条目仍会消费按键，因此不能靠「静音 + Window 层」覆盖，
    只能直接改写入键条目本身。

    allow_fallback：所选 keymap 里没有这个键时，退一步接管「同空间或全局」keymap 里的同键条目
    （例如 Tab 实际注册在 Object Non-modal，而用户选的是 3D View）。
    """
    def candidates(strict):
        for _layer, kc in iter_layers():
            if strict:
                km = find_keymap(kc, spec)
                if km is None:
                    continue
                yield kc, km, "exact"
            else:
                want_space = spec.get("space") or "EMPTY"
                for km in kc.keymaps:
                    if getattr(km, "is_modal", False):
                        continue
                    if km.space_type not in (want_space, "EMPTY"):
                        continue
                    yield kc, km, "fallback"

    def collect(strict):
        found = []
        for kc, km, mode in candidates(strict):
            for kmi in list(km.keymap_items):
                if not kmi.active or is_own(kmi):
                    continue
                if not combo_match(kmi, key):
                    continue
                found.append((kc, km, kmi))
        return found

    matches = collect(True)
    if not matches and allow_fallback:
        matches = collect(False)

    patched = []
    for kc, km, kmi in matches:
        record = {
            "kc": kc.name,
            "keymap": {"name": km.name, "space": km.space_type, "region": km.region_type},
            "key": normalize_key(key),
            "binding_id": binding_id,
            "orig_idname": kmi.idname,
            "orig_props": _props_snapshot(kmi),
        }
        try:
            kmi.idname = DISPATCH_IDNAME
            setattr(kmi.properties, "binding_id", binding_id)
        except Exception:
            continue
        patched.append(record)
    return patched


def scan_key_owners(key):
    """列出所有 keymap 里占用这个组合键的条目（用于诊断“键实际绑在哪”）。"""
    rows = []
    for kc in bpy.context.window_manager.keyconfigs:
        for km in kc.keymaps:
            if getattr(km, "is_modal", False):
                continue
            for kmi in km.keymap_items:
                try:
                    if not kmi.active or not combo_match(kmi, key):
                        continue
                except Exception:
                    continue
                rows.append({
                    "keymap": km.name,
                    "space": km.space_type,
                    "idname": kmi.idname,
                    "owner": resolve_owner(kmi),
                    "ours": is_own(kmi),
                })
    return rows


def restore_patches(records):
    """把被就地接管的条目写回原操作符与参数。"""
    restored = 0
    wm = bpy.context.window_manager
    for record in records or []:
        for kc in list(wm.keyconfigs):
            if kc.name != record.get("kc"):
                continue
            km = find_keymap(kc, record.get("keymap") or {})
            if km is None:
                continue
            for kmi in list(km.keymap_items):
                if kmi.idname != DISPATCH_IDNAME:
                    continue
                if getattr(kmi.properties, "binding_id", None) != record.get("binding_id"):
                    continue
                if not combo_match(kmi, record.get("key") or {}):
                    continue
                try:
                    kmi.idname = record["orig_idname"]
                    for name, value in (record.get("orig_props") or {}).items():
                        try:
                            setattr(kmi.properties, name, value)
                        except Exception:
                            pass
                    restored += 1
                except Exception:
                    pass
                break
    return restored


def apply(data, dry_run=False):
    """应用全部启用中的绑定；幂等。"""
    if not dry_run:
        # 重新应用前先复原上一轮的就地接管与静音，避免状态漂移
        if APPLIED.get("patched"):
            restore_patches(APPLIED["patched"])
            APPLIED["patched"] = []
        journal = config.read_journal() or {}
        if journal.get("patched"):
            restore_patches(journal["patched"])
        if APPLIED.get("muted"):
            restore_entries(APPLIED["muted"])
            APPLIED["muted"] = []
        purge()

    report = {"created": [], "muted": [], "skipped": [], "dry_run": bool(dry_run),
              "duplicates": duplicate_bindings(data)}
    wm = bpy.context.window_manager
    kc = target_keyconfig()
    if kc is None:
        report["skipped"].append({"reason": "no keyconfig available"})
        return report

    created = []
    muted = []
    patched = []
    created_ids = set()
    owned_sigs = []

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
        else:
            target_id = target.get("id") or ""
            if not has_operator(target_id):
                report["skipped"].append({"binding": binding.get("id"), "reason": f"operator missing: {target_id}"})
                continue

        spec = binding.get("keymap") or {}
        if not spec.get("name"):
            report["skipped"].append({"binding": binding.get("id"), "reason": "keymap missing"})
            continue
        key = normalize_key(binding.get("key") or {})

        # 强制覆盖：优先就地接管既有条目（区域 keymap 的静音项仍会吃掉按键）
        patched_here = []
        if binding.get("force_override"):
            if dry_run:
                patched_here = []
                for _layer, layer_kc in iter_layers():
                    layer_km = find_keymap(layer_kc, spec)
                    if layer_km is None:
                        continue
                    patched_here += [
                        {"kc": layer_kc.name, "orig_idname": kmi.idname}
                        for kmi in layer_km.keymap_items
                        if kmi.active and not is_own(kmi) and combo_match(kmi, key)
                    ]
            else:
                patched_here = _patch_takeover(binding.get("id"), spec, key, allow_fallback=True)
        if patched_here:
            patched.extend(patched_here)
            report["created"].append({
                "binding": binding.get("id"),
                "idname": DISPATCH_IDNAME,
                "key": key_label(key),
                "keymap": f'{spec.get("name")} [{spec.get("space", "")}]',
                "patched": len(patched_here),
            })
            continue

        km = find_keymap(kc, WINDOW_SPEC) if dry_run else ensure_keymap(kc, WINDOW_SPEC)
        if km is None:
            report["skipped"].append({"binding": binding.get("id"), "reason": "window keymap unavailable"})
            continue
        entry = {
            "binding": binding.get("id"),
            "idname": DISPATCH_IDNAME,
            "key": key_label(key),
            "keymap": f'{spec.get("name")} [{spec.get("space", "")}]',
        }
        if not dry_run:
            try:
                kmi = _new_item(km, DISPATCH_IDNAME, key)
            except Exception as exc:
                report["skipped"].append({"binding": binding.get("id"), "reason": f"new item failed: {exc}"})
                continue
            _set_props(kmi, {"binding_id": binding.get("id")})
            created.append({"kc": kc.name, "keymap": dict(WINDOW_SPEC), "key": key, "idname": DISPATCH_IDNAME})
            created_ids.add((km.name, kmi.id))
            owned_sigs.append(_signature(km, kmi))
        report["created"].append(entry)

        if binding.get("force_override"):
            _mute(muted, spec, key, dry_run, created_ids)
            _mute(muted, WINDOW_SPEC, key, dry_run, created_ids)

    report["muted"] = [
        {"owner": m.get("owner"), "idname": m["idname"], "kc": m["kc"], "key": key_label(m["key"])}
        for m in muted
    ]

    if dry_run:
        report["would_mute"] = len(muted)
        return report

    APPLIED["items"] = created
    APPLIED["muted"] = muted
    APPLIED["patched"] = patched
    APPLIED["applied_at"] = time.time()
    config.write_owned(owned_sigs)
    refresh_owned()
    if muted or patched:
        config.write_journal({
            "version": 1,
            "entries": _journal_entries(muted),
            "patched": patched,
        })
    else:
        config.clear_journal()
    # 让键位层重新合并一次；否则运行中途新增的条目可能不参与分发
    try:
        bpy.context.window_manager.keyconfigs.update()
    except Exception:
        pass
    return report


def purge():
    """清理我们自己的键位条目（幂等注册的关键）。

    条目可能落在 active / user / addon 任意一层（目标为原生操作符时 idname
    不带前缀），统一按 owned.json 的签名识别并移除。
    """
    removed = 0
    refresh_owned()
    for _layer, kc in list(iter_layers()):
        for km in list(kc.keymaps):
            for kmi in list(km.keymap_items):
                if not is_ours_item(km, kmi):
                    continue
                try:
                    km.keymap_items.remove(kmi)
                    removed += 1
                except Exception:
                    pass
    APPLIED["items"] = []
    config.clear_owned()
    refresh_owned()
    return removed


def unapply():
    """移除我们的键位、写回被接管的条目、恢复被静音的条目。"""
    journal = config.read_journal() or {}
    restored = restore_patches(
        (APPLIED.get("patched") or []) + (journal.get("patched") or [])
    )

    removed = 0
    refresh_owned()
    for _layer, kc in list(iter_layers()):
        for km in list(kc.keymaps):
            for kmi in list(km.keymap_items):
                if not is_ours_item(km, kmi):
                    continue
                try:
                    km.keymap_items.remove(kmi)
                    removed += 1
                except Exception:
                    pass

    entries = list(journal.get("entries") or [])
    entries.extend(_journal_entries(APPLIED.get("muted") or []))
    restored += restore_entries(entries)

    APPLIED["items"] = []
    APPLIED["muted"] = []
    APPLIED["patched"] = []
    config.clear_owned()
    refresh_owned()
    config.clear_journal()
    return {"removed": removed, "restored": restored}


def reconcile_journal():
    """启动时按 journal 恢复残留（就地接管写回 + 静音恢复）。"""
    journal = config.read_journal()
    if not journal:
        return {"restored": 0, "pending": 0}
    restored = restore_patches(journal.get("patched") or [])
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