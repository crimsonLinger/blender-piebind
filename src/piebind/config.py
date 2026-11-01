"""PieBind 配置存储：JSON + 原子写 + 备份 + journal。"""

import json
import os
import shutil
import tempfile
import time
import uuid

import bpy

SCHEMA_VERSION = 1
MAX_BACKUPS = 5


# ---------------------------------------------------------------- paths
def config_dir():
    """配置目录；测试可用 PIEBIND_CONFIG_DIR 覆盖。"""
    override = os.environ.get("PIEBIND_CONFIG_DIR")
    if override:
        path = override
    else:
        try:
            path = bpy.utils.user_resource("CONFIG", path="piebind", create=True)
        except Exception:
            path = os.path.join(tempfile.gettempdir(), "piebind")
    os.makedirs(path, exist_ok=True)
    return path


def path_of(name):
    return os.path.join(config_dir(), name)


def backup_dir():
    path = os.path.join(config_dir(), "backups")
    os.makedirs(path, exist_ok=True)
    return path


# ---------------------------------------------------------------- model
def default_data():
    return {"schema_version": SCHEMA_VERSION, "pies": [], "bindings": []}


def new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def empty_pie(label="新建饼"):
    return {"id": new_id("pie"), "label": label, "slots": {}}


def find_pie(data, pie_id):
    for pie in data.get("pies", []):
        if pie.get("id") == pie_id:
            return pie
    return None


def find_binding(data, binding_id):
    for b in data.get("bindings", []):
        if b.get("id") == binding_id:
            return b
    return None


# ---------------------------------------------------------------- io
def _coerce(data):
    if not isinstance(data, dict):
        return default_data()
    data.setdefault("schema_version", SCHEMA_VERSION)
    if not isinstance(data.get("pies"), list):
        data["pies"] = []
    if not isinstance(data.get("bindings"), list):
        data["bindings"] = []
    cleaned = []
    for pie in data["pies"]:
        if not isinstance(pie, dict) or not pie.get("id"):
            continue
        pie.setdefault("label", "未命名")
        if not isinstance(pie.get("slots"), dict):
            pie["slots"] = {}
        cleaned.append(pie)
    data["pies"] = cleaned
    bindings = []
    for b in data["bindings"]:
        if not isinstance(b, dict) or not b.get("id"):
            continue
        b.setdefault("enabled", True)
        b.setdefault("force_override", False)
        if isinstance(b.get("keymap"), dict) and isinstance(b.get("key"), dict):
            bindings.append(b)
    data["bindings"] = bindings
    return data


def load():
    path = path_of("bindings.json")
    if not os.path.exists(path):
        return default_data()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return _coerce(json.load(fh))
    except Exception:
        # 坏文件：留档后回退默认
        try:
            shutil.copyfile(path, path + f".broken-{int(time.time())}")
        except Exception:
            pass
        return default_data()


def _atomic_write(path, payload):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _rotate_backup(path):
    if not os.path.exists(path):
        return
    try:
        target = os.path.join(backup_dir(), f"bindings-{time.strftime('%Y%m%d-%H%M%S')}.json")
        shutil.copyfile(path, target)
        files = sorted(f for f in os.listdir(backup_dir()) if f.endswith(".json"))
        for stale in files[:-MAX_BACKUPS]:
            os.remove(os.path.join(backup_dir(), stale))
    except Exception:
        pass


def save(data):
    data = _coerce(data)
    path = path_of("bindings.json")
    _rotate_backup(path)
    _atomic_write(path, data)
    return path


# ---------------------------------------------------------------- journal
def read_journal():
    path = path_of("journal.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def write_journal(payload):
    payload = dict(payload)
    payload.setdefault("created", time.strftime("%Y-%m-%dT%H:%M:%S"))
    _atomic_write(path_of("journal.json"), payload)


def clear_journal():
    try:
        os.remove(path_of("journal.json"))
    except FileNotFoundError:
        pass


# ---------------------------------------------------------------- mutations
def create_pie(data, label="新建饼"):
    pie = empty_pie(label)
    data["pies"].append(pie)
    return pie


def delete_pie(data, pie_id):
    data["pies"] = [p for p in data["pies"] if p.get("id") != pie_id]
    for b in data["bindings"]:
        target = b.get("target") or {}
        if target.get("kind") == "pie" and target.get("id") == pie_id:
            b["enabled"] = False


def set_slot(data, pie_id, pos, slot):
    pie = find_pie(data, pie_id)
    if pie is None:
        return False
    if slot is None:
        pie["slots"].pop(pos, None)
    else:
        pie["slots"][pos] = slot
    return True