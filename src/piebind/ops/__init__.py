"""操作符层：捕获、绑定、饼、分发、诊断、选择器。

兼容：这里同时再导出常用的小工具与类名（历史代码/测试直接 `ops.xxx` 访问）。
"""

from ..core.keyspec import (
    COMMON_KEYMAPS,
    keymap_rows,
    make_keymap_identifier,
    parse_key_text,
    split_keymap_identifier,
)
from . import bindings, capture, common, diag, dispatch, pickers, pie_ops, presets, settings, sidekeys
from .bindings import (
    PIEBIND_OT_apply,
    PIEBIND_OT_check_binding,
    PIEBIND_OT_create_binding,
    PIEBIND_OT_delete_binding,
    PIEBIND_OT_toggle_binding,
    PIEBIND_OT_unapply,
)
from .capture import PIEBIND_OT_capture_key
from .common import (
    ICON_ITEMS,
    SLOT_POS_ITEMS,
    WM_PROPS,
    _operator_choices,
    _refresh_keymap_items,
    _refresh_pie_items,
    _refresh_slot_pos,
    register_wm_props,
    unregister_wm_props,
)
from .diag import PIEBIND_OT_copy_diagnostics, PIEBIND_OT_export_diagnostics
from .dispatch import PIEBIND_OT_dispatch, PIEBIND_OT_slot_missing
from .sidekeys import (PIEBIND_OT_arm_side_listener, PIEBIND_OT_side_listener, register_side_keymap, unregister_side_keymap)
from .pickers import (
    PIEBIND_MT_keymaps,
    PIEBIND_MT_operators,
    PIEBIND_MT_op_prefixes,
    PIEBIND_MT_op_prefixes_all,
    PIEBIND_MT_pies,
    PIEBIND_OT_pick_operator,
    PIEBIND_OT_select_keymap,
    PIEBIND_OT_select_op_prefix,
    PIEBIND_OT_select_pie,
)
from .presets import PIEBIND_MT_slot_presets, PIEBIND_OT_apply_slot_preset
from .pie_ops import (
    PIEBIND_OT_add_slot,
    PIEBIND_OT_call_pie,
    PIEBIND_OT_create_pie,
    PIEBIND_OT_delete_pie,
    PIEBIND_OT_load_slot,
    PIEBIND_OT_remove_slot,
    PIEBIND_OT_rename_pie,
    PIEBIND_OT_select_slot,
    PIEBIND_OT_test_pie,
)
from .settings import (
    PIEBIND_OT_load_defaults,
    PIEBIND_OT_open_config_dir,
    PIEBIND_OT_save_defaults,
)

CLASSES = (
    # 选择器（菜单类需先于使用它们的界面注册）
    PIEBIND_MT_keymaps,
    PIEBIND_MT_pies,
    PIEBIND_MT_operators,
    PIEBIND_MT_op_prefixes,
    PIEBIND_MT_op_prefixes_all,
    PIEBIND_MT_slot_presets,
    PIEBIND_OT_select_keymap,
    PIEBIND_OT_select_pie,
    PIEBIND_OT_select_op_prefix,
    PIEBIND_OT_pick_operator,
    PIEBIND_OT_apply_slot_preset,
    # 捕获
    PIEBIND_OT_capture_key,
    # 绑定
    PIEBIND_OT_apply,
    PIEBIND_OT_unapply,
    PIEBIND_OT_create_binding,
    PIEBIND_OT_delete_binding,
    PIEBIND_OT_toggle_binding,
    PIEBIND_OT_check_binding,
    # 饼
    PIEBIND_OT_create_pie,
    PIEBIND_OT_rename_pie,
    PIEBIND_OT_delete_pie,
    PIEBIND_OT_add_slot,
    PIEBIND_OT_remove_slot,
    PIEBIND_OT_select_slot,
    PIEBIND_OT_load_slot,
    PIEBIND_OT_test_pie,
    PIEBIND_OT_call_pie,
    # 分发
    PIEBIND_OT_slot_missing,
    PIEBIND_OT_dispatch,
    PIEBIND_OT_side_listener,
    PIEBIND_OT_arm_side_listener,
    # 诊断
    PIEBIND_OT_export_diagnostics,
    PIEBIND_OT_copy_diagnostics,
    # 默认值 / 配置
    PIEBIND_OT_save_defaults,
    PIEBIND_OT_load_defaults,
    PIEBIND_OT_open_config_dir,
)

__all__ = ["CLASSES", "WM_PROPS", "register_wm_props", "unregister_wm_props"]



