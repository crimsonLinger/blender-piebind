"""纯逻辑：键位组合解析、keymap 标识符。"""

import json

import bpy


def split_keymap_identifier(value):
    try:
        name, space, region = json.loads(value)
        return {"name": name, "space": space, "region": region}
    except Exception:
        return None


def make_keymap_identifier(name, space, region):
    return json.dumps([name, space, region], ensure_ascii=False)


COMMON_KEYMAPS = [
    "3D View", "Object Non-modal", "Mesh", "Sculpt", "Pose", "Node Editor",
    "Dopesheet", "Sequencer", "UV Editor", "Console", "Text", "Image",
    "NLA Editor", "Graph Editor", "Outliner", "Window",
]


def keymap_rows(query=""):
    """返回 keymap 行：[{id, label, name, space, region}]；常用项优先。"""
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.active or wm.keyconfigs.user
    rows = []
    seen = set()
    if kc is not None:
        for km in kc.keymaps:
            if getattr(km, "is_modal", False):
                continue
            ident = (km.name, km.space_type, km.region_type)
            if ident in seen:
                continue
            seen.add(ident)
            rows.append({
                "id": make_keymap_identifier(km.name, km.space_type, km.region_type),
                "name": km.name,
                "space": km.space_type,
                "region": km.region_type,
                "label": f"{km.name}  [{km.space_type}]" if km.space_type != "EMPTY" else km.name,
            })

    q = (query or "").strip().lower()
    if q:
        rows = [r for r in rows if q in r["name"].lower() or q in r["space"].lower()]

    def rank(row):
        try:
            return (0, COMMON_KEYMAPS.index(row["name"]), row["name"])
        except ValueError:
            return (1, 0, row["name"])

    rows.sort(key=rank)
    return rows


def parse_key_text(text):
    """把 'ctrl+shift+e' / 'tab' / 'F8' 解析成 key 字典。"""
    tokens = [t for t in str(text or "").replace("+", " ").split() if t]
    if not tokens:
        return None
    key = {"value": "PRESS", "ctrl": False, "shift": False, "alt": False,
           "oskey": False, "any": False, "key_modifier": "NONE"}
    key_type = None
    for token in tokens:
        low = token.lower()
        if low in _MOD_ALIASES:
            key[_MOD_ALIASES[low]] = True
            continue
        if low in _DIGIT_TYPES:
            key_type = _DIGIT_TYPES[low]
        elif low in _KEY_ALIASES:
            key_type = _KEY_ALIASES[low]
        elif low.startswith("numpad") and low[6:].isdigit():
            key_type = "NUMPAD_" + _DIGIT_TYPES.get(low[6:], low[6:].upper())
        elif len(token) == 1 and token.isalpha():
            key_type = token.upper()
        else:
            key_type = token.upper().replace("-", "_").replace(" ", "_")
    if not key_type:
        return None
    key["type"] = key_type
    return key


_DIGIT_TYPES = {
    "1": "ONE", "2": "TWO", "3": "THREE", "4": "FOUR", "5": "FIVE",
    "6": "SIX", "7": "SEVEN", "8": "EIGHT", "9": "NINE", "0": "ZERO",
}


_KEY_ALIASES = {
    "tab": "TAB", "space": "SPACE", "spacebar": "SPACE",
    "enter": "RET", "return": "RET", "numpadenter": "NUMPAD_ENTER",
    "esc": "ESC", "escape": "ESC", "backspace": "BACKSPACE", "del": "DEL",
    "delete": "DEL", "home": "HOME", "end": "END",
    "pageup": "PAGEUP", "pagedown": "PAGEDOWN", "insert": "INSERT",
    "up": "UP_ARROW", "down": "DOWN_ARROW", "left": "LEFT_ARROW", "right": "RIGHT_ARROW",
    "lmb": "LEFTMOUSE", "rmb": "RIGHTMOUSE", "mmb": "MIDDLEMOUSE",
    "m4": "BUTTON4MOUSE", "m5": "BUTTON5MOUSE", "m6": "BUTTON6MOUSE", "m7": "BUTTON7MOUSE",
    "mouse4": "BUTTON4MOUSE", "mouse5": "BUTTON5MOUSE",
    "mouse6": "BUTTON6MOUSE", "mouse7": "BUTTON7MOUSE",
    "button4": "BUTTON4MOUSE", "button5": "BUTTON5MOUSE",
    "button6": "BUTTON6MOUSE", "button7": "BUTTON7MOUSE",
    "side": "BUTTON4MOUSE", "back": "BUTTON4MOUSE", "forward": "BUTTON5MOUSE",
    "wheelup": "WHEELUPMOUSE", "wheeldown": "WHEELDOWNMOUSE",
    "menu": "APP", "quote": "QUOTE", "grave": "ACCENT_GRAVE",
}


_MOD_ALIASES = {
    "ctrl": "ctrl", "control": "ctrl",
    "shift": "shift",
    "alt": "alt", "option": "alt",
    "os": "oskey", "cmd": "oskey", "win": "oskey", "super": "oskey",
}

