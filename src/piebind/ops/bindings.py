"""绑定：应用 / 复原 / 增删改 / 自检。"""

import json

import bpy

from ..core import config, keymap as ke, keyspec, pies as pie
from .common import WM_PROPS


class PIEBIND_OT_apply(bpy.types.Operator):
    bl_idname = "piebind.apply"
    bl_label = "应用键位"
    bl_description = "把配置写入键位并静音冲突项（会写 journal 以便复原）"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        data = config.load()
        report = ke.apply(data)
        msg = f"已创建 {len(report['created'])} 条绑定，静音 {len(report['muted'])} 条冲突项"
        context.window_manager.piebind_status = msg
        self.report({"INFO"}, msg)
        return {"FINISHED"}


class PIEBIND_OT_unapply(bpy.types.Operator):
    bl_idname = "piebind.unapply"
    bl_label = "全部复原"
    bl_description = "移除本插件键位并恢复被静音的条目"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        result = ke.unapply()
        msg = f"移除 {result['removed']} 条，恢复 {result['restored']} 条"
        context.window_manager.piebind_status = msg
        self.report({"INFO"}, msg)
        return {"FINISHED"}


class PIEBIND_OT_create_binding(bpy.types.Operator):
    bl_idname = "piebind.create_binding"
    bl_label = "保存绑定"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        wm = context.window_manager
        spec = split_keymap_identifier(wm.piebind_keymap)
        if spec is None:
            spec = {"name": "3D View", "space": "VIEW_3D", "region": "WINDOW"}
            wm.piebind_keymap = make_keymap_identifier("3D View", "VIEW_3D", "WINDOW")
            self.report({"WARNING"}, "未选择 Keymap，已默认 3D View")
        raw = wm.piebind_key_json
        if not raw:
            self.report({"ERROR"}, "请先捕获快捷键")
            return {"CANCELLED"}
        key = json.loads(raw)
        kind = wm.piebind_target_kind
        if kind == "pie":
            target = {"kind": "pie", "id": wm.piebind_pie, "props": {}}
            if not config.find_pie(config.load(), target["id"]):
                self.report({"ERROR"}, "请选择饼菜单")
                return {"CANCELLED"}
        else:
            idname = wm.piebind_op_choice
            if not ke.has_operator(idname):
                self.report({"ERROR"}, f"操作符不存在：{idname}")
                return {"CANCELLED"}
            target = {"kind": "operator", "id": idname, "props": {}}

        data = config.load()
        binding = {
            "id": config.new_id("bd"),
            "enabled": True,
            "force_override": bool(wm.piebind_force_override),
            "keymap": dict(spec),
            "key": key,
            "target": target,
        }
        if wm.piebind_restrict_view3d:
            binding["keymap"]["area"] = "VIEW_3D"
        data["bindings"].append(binding)
        config.save(data)
        ke.apply(data)
        wm.piebind_status = f"已保存绑定：{ke.key_label(key)} → {target['id']}"
        return {"FINISHED"}


class PIEBIND_OT_delete_binding(bpy.types.Operator):
    bl_idname = "piebind.delete_binding"
    bl_label = "删除绑定"
    bl_options = {"REGISTER", "INTERNAL"}

    binding_id: bpy.props.StringProperty()

    def execute(self, context):
        data = config.load()
        data["bindings"] = [b for b in data["bindings"] if b.get("id") != self.binding_id]
        config.save(data)
        ke.apply(data)
        return {"FINISHED"}


class PIEBIND_OT_toggle_binding(bpy.types.Operator):
    bl_idname = "piebind.toggle_binding"
    bl_label = "启用/停用绑定"
    bl_options = {"REGISTER", "INTERNAL"}

    binding_id: bpy.props.StringProperty()

    def execute(self, context):
        data = config.load()
        for binding in data["bindings"]:
            if binding.get("id") == self.binding_id:
                binding["enabled"] = not binding.get("enabled", True)
                break
        config.save(data)
        ke.apply(data)
        return {"FINISHED"}


class PIEBIND_OT_check_binding(bpy.types.Operator):
    bl_idname = "piebind.check_binding"
    bl_label = "检查此绑定"
    bl_options = {"REGISTER", "INTERNAL"}

    binding_id: bpy.props.StringProperty()

    def execute(self, context):
        wm = context.window_manager
        data = config.load()
        binding = next((b for b in data.get("bindings", []) if b.get("id") == self.binding_id), None)
        if binding is None:
            self.report({"ERROR"}, "找不到该绑定")
            return {"CANCELLED"}

        spec = binding.get("keymap") or {}
        key = binding.get("key") or {}
        patch_count = 0
        patched_keymaps = []
        for kc in wm.keyconfigs:
            for km in kc.keymaps:
                for kmi in km.keymap_items:
                    if kmi.idname != ke.DISPATCH_IDNAME:
                        continue
                    try:
                        if kmi.properties.binding_id == binding["id"]:
                            patch_count += 1
                            patched_keymaps.append(km.name)
                    except Exception:
                        continue

        owners = ke.scan_key_owners(key)
        foreign = [row for row in owners if not row["ours"]]
        chosen_name = spec.get("name", "")
        in_chosen = [row for row in foreign if row["keymap"] == chosen_name]
        elsewhere = sorted({f"{row['keymap']}({row['idname']})" for row in foreign
                            if row["keymap"] != chosen_name})[:3]

        target = binding.get("target") or {}
        slot_info = "-"
        if target.get("kind") == "pie":
            pie_data = config.find_pie(data, target.get("id"))
            if pie_data is None:
                slot_info = "饼已不存在"
            else:
                slot_info = f"{len(pie_data.get('slots') or {})} 个槽位"

        conflicts = ke.scan_conflict(spec, key) if spec else []
        parts = [
            f"键位 {ke.key_label(key)}",
            f"keymap {spec.get('name', '?')}",
            f"接管 {patch_count} 条",
            f"冲突 {len(conflicts)} 条",
            f"饼 {slot_info}",
        ]
        if patched_keymaps:
            parts.append("接管在：" + "、".join(sorted(set(patched_keymaps))[:3]))
        if not chosen_name:
            parts.append("未选择 keymap")
        elif not in_chosen and elsewhere:
            parts.append(f"所选 keymap 没有这个键；实际绑在：{'、'.join(elsewhere)}")
        if not binding.get("enabled", True):
            parts.insert(0, "【已停用】")
        if patch_count == 0 and not binding.get("force_override"):
            parts.append("未勾强制覆盖 → 可能被原键位抢先")
        message = " · ".join(parts)
        wm.piebind_status = f"检查：{message}"
        self.report({"INFO"}, message)
        return {"FINISHED"}
