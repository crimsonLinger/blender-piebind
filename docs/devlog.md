# 开发日志

> 这里是开发过程的详细记录（中文、倒序）。用户向的版本更新见
> [CHANGELOG.md](../CHANGELOG.md)（英文）与 [CHANGELOG_zh.md](../CHANGELOG_zh.md)。

每轮迭代追加：`## 日期 · 第N轮：一句话主题`，末尾写「当前状态 / 下一步 / 未验证」。

## 2026-11-06 · 第45轮：槽位按模式变体（同一位置多套操作符）

### 反馈
- 「不能为一个饼菜单中的快捷键添加多个绑定吗，例如隐藏按键都是 Shift+H，每个模式中都一样」——
  选中方案 A：同一槽位按当前模式自动切换操作符。

### 设计
- 槽位新增可选 `variants: [{mode, idname, text, icon, props}]`；基础槽位仍是「所有模式」的回落。
- 解析：`pies.slot_for_mode(slot, context.mode)`，`context.mode` 先归一（`EDIT_MESH` → `EDIT`）。

### 改动
- `core/pies.py`：`MODE_ITEMS` / `normalize_mode()` / `mode_label()` / `slot_for_mode()`；`_draw_slot` 按模式取变体。
- `ops/common.py`：WM 属性 `piebind_edit_mode`；`load_slot_into_form(..., mode)` 读变体（无变体则清空供新建）；
  `save_current_slot` 按模式写 `variants`，且不覆盖基础槽位。
- `ops/pie_ops.py`：`select_edit_mode`、`remove_edit_variant`；切槽位/切饼时重置模式。
- `ops/pickers.py` + `ui/prefs.py`：`PIEBIND_MT_edit_modes` 菜单与「模式：编辑模式」一行按钮 + 「删除该模式」。
- `api.py`：`create_pie` 的槽位支持 `variants`。

### 验证
- headless **145/145**（新增：模式归一、变体写入、基础不被覆盖、模式解析、读回、删除回落）；
- 冒烟 **42 OK / 0 FAIL**（模式菜单 8 项）；
- GUI 实测：`PIEBIND_MT_pie.draw` 在 OBJECT 画出 `object.hide_view_set`，切到 EDIT_MESH 后画出 `mesh.hide`；
  面板截图确认「模式：编辑模式 + 隐藏选中项 [H / SHIFT+H] + Unselected：是」。

## 2026-11-06 · 第44轮：操作符搜索加「范围」前缀过滤

### 反馈
- 建议在搜索前加前缀选择（object / view3d 之类），并把前缀翻译成中文。

### 改动
- `core/keymap.py`：新增 `PREFIX_LABELS`（object→物体、view3d→3D 视图、mesh→网格…）、
  `COMMON_PREFIXES`、`prefix_label()`、`operator_prefixes()`；
  `search_operators(..., prefix="")` 按 `idname.startswith(prefix + ".")` 过滤（键位命中同样受限）。
- `ops/common.py`：新增 WM 属性 `piebind_op_prefix`；查询更新与枚举都带上范围。
- `ops/pickers.py`：新增 `PIEBIND_MT_op_prefixes`（16 个常用 + 「更多…」）与
  `PIEBIND_MT_op_prefixes_all`（全部 78 个模块）、`PIEBIND_OT_select_op_prefix`。
- `ui/pickers.py`：搜索框右侧加「范围：全部/物体/3D 视图」按钮。
- `api.py`：`search_operators` 支持 `prefix` 参数，标签改用中文名。

### 验证
- headless **138/138**（新增：范围标签、空范围、范围过滤、范围+关键词、选择范围写入状态）；
- 冒烟 **41 OK / 0 FAIL**（两个新菜单分别 20 / 78 项）；
- GUI 实测：选 `view3d` 后搜 `view`，10 条命中全部 `view3d.*`。

## 2026-11-06 · 第43轮：按键位搜索 + 修复中文翻译缺失

### 反馈
- 希望「搜索」支持按 Blender 内置键位查操作符；
- 有些操作符明明有中文翻译，但搜索结果里只有英文。

### 定位
- 翻译缺失的根因：Blender 的操作符名字在 **"Operator" 上下文**里翻译，
  而索引构建时用的是不带上下文的 `pgettext_iface(name)`，于是 `Hide Objects`、
  `Frame All`、`Set Object Mode` 这些全部回落成英文（`查看轴向` 这类因同时存在于 iface 目录才碰巧正常）。

### 改动
- `_localized_operator_name()`：先 `pgettext_iface(name, "Operator")`，再退回 iface；索引格式升到 v2
  （文件名与 payload 都带版本，旧缓存自动失效重建）；
- 新增 `shortcut_query_label()` / `shortcut_search()`：把 `h` / `shift+h` / `F8` 归一成标签，
  在 `shortcut_map()` 里找绑定该键的操作符；
- `search_operators()`：键位命中排在前面，文本命中按「前缀优先」排序。

### 验证
- headless **132/132**（新增：按键位搜索、组合键搜索、索引格式版本）；
- GUI 实测：`object.hide_view_set` 标签 `隐藏物体`；搜「隐藏」第 10 位出现它（菜单取 20 条）；
  搜 `h` 命中 `object.hide_view_set`，搜 `shift+h` 同样命中。

## 2026-11-06 · 第42轮：参数预设支持布尔参数（隐藏/显示）

### 反馈
- 用户给 `object.hide_view_set` 打开「参数」下拉，提示「没有可选参数」——因为该操作符只有
  一个布尔属性 `unselected`，而预设此前只枚举 ENUM 属性。

### 改动
- `core/presets.py`：RNA 兜底从「只认枚举」扩展到「枚举 + 布尔」（布尔生成 是/否 两条，带空文字）；
- 新增内置预设：`object.hide_view_set` → 隐藏所选（H）/ 隐藏未选中（Shift+H）；
  `object.hide_view_clear` → 显示全部（Alt+H）/ 显示全部并选中；
- `apply_slot_preset`：预设没有文字时不覆盖槽位文字（布尔预设不冲掉自定义名称）。

### 验证
- headless **129/129**（新增：隐藏操作符带布尔预设、布尔参数自动生成、空文字预设不覆盖）；
- GUI 实测：`presets_for('object.hide_view_set')` 返回两条，套用后槽位写入
  `{"unselected": true}` + 文字「隐藏未选中」。

## 2026-11-06 · 第41轮：操作符列表显示 Blender 自带快捷键

### 反馈
- 用户把「隐藏」绑进视图饼后条目变灰：实际选中的是 `outliner.hide`（大纲视图专用），
  在 3D 视图里 `poll()` 不通过 → Blender 自动把菜单项置灰。
- 追问：搜「隐藏」为什么搜不到 3D 视图的隐藏？因为 `object.hide_view_set` 在这个版本
  没有中文翻译（仍叫 “Hide Objects”），搜索只按翻译名 / 英文名 / idname 匹配。

### 改动
- `core/keymap.py` 新增 `shortcut_map()` / `shortcut_for()`：只读汇总现有键位（30 秒缓存，
  优先 3D 视图 / 全局），不改动任何键位；
- 操作符搜索菜单每条结果显示 `— H / SHIFT+H`，已选操作符按钮显示 `[H / SHIFT+H]`。

### 验证
- headless **126/126**（新增：查询现有键位、搜索结果带快捷键、未知操作符返回空）；
- GUI 实测：`object.hide_view_set => 'H / SHIFT+H'`、`object.hide_view_clear => 'ALT+H'`、
  `outliner.hide => 'H'`、`view3d.view_axis => 'NUM1 / NUM3'`。

### 状态 / 下一步
- 用户侧把视图饼 N 槽改成 `object.hide_view_set` 即可；未发布到 GitHub 的部分随下一提交推送。

## 2026-11-05 · 第40轮：删掉「改动会自动保存」提示行，清空并入标题行

### 反馈
- 「把自动保存那行字删掉，没有用处」。

### 改动
- 删除底部提示行与它所在的整行按钮；「清空」并入「编辑槽位 …」标题行，和「载入」并排。
- 槽位编辑区最终结构：标题行（载入 / 清空）→ 搜索 → 操作符 → 文字/图标 → 参数 → 属性 JSON，改完自动保存。

### 验证
- headless **122/122 PASSED**；冒烟 **39 OK / 0 FAIL**；
- GUI 截图：编辑区不再有多余行，整块在默认窗口里更紧凑；
- 包 52,019 字节，已覆盖安装；**需重启 Blender 生效**。

## 2026-11-05 · 第39轮：去掉「写入槽位」按钮，改成改完自动保存

### 反馈
- 「写入槽位按键过于繁琐，请在每次修改后自动应用一次，并且删除此按键」。

### 改动
- `slot_text / slot_props / slot_icon / op_choice` 四个字段加了 update 回调：改动后 **0.6 秒防抖**写入当前槽位；
- 写盘前四道检查：不在「饼菜单」页签 / 没选饼 / 没选操作符 / JSON 不完整（正打到一半）——都不写；
- 内容与槽位现有内容完全一致时不重复写盘，避免每次点选都刷一次文件；
- 切饼、切槽位之前先 `flush_pending_save()`，手快切走也不会丢刚改的内容；
- 载入槽位、新建饼、清空槽位时用抑制标志，避免把表单内容误写进别的槽位；
- 删除「写入槽位」按钮，底部改成一行「改动会自动保存到该槽位」+「清空」；状态栏回显「已保存槽位 N：xxx」。

### 验证
- headless **122/122 PASSED**（新增：自动保存、无变化不重复写、半截 JSON 不写、JSON 修好后继续、
  文字改动触发、抑制标志、非饼页签不写、切换前 flush）；
- GUI：连续改三个字段，约 2 秒后配置里出现 `view3d.view_axis + {"type":"TOP"} + 顶视图`，
  状态栏显示「已保存槽位 N：顶视图」；
- 冒烟 **39 OK / 0 FAIL**；
- 包 52,048 字节，已覆盖安装；**需重启 Blender 生效**。

### 状态 / 下一步
- `piebind.add_slot` 操作符保留（测试与脚本仍可用），只是界面不再有按钮。

## 2026-11-05 · 第38轮：删掉槽位编辑区里重复的「现有 / 参数」信息行

### 判断
- 用户：「图片中那个现有和参数两个信息框也是重复无用的」——对。
- 点罗盘方位后编辑区已经自动载入该槽位（操作符名、文字、参数 JSON 都在下面的表单里），
  上面两行只是把同样的内容再念一遍，纯占地方。

### 改动
- 删除「现有：…｜idname」与「参数：{…}」两行（连同空槽提示），编辑区只留表单本身；
- 槽位内容仍可从表单直接看到：操作符下拉、文字、参数预设按钮、属性 JSON。

### 验证
- headless **114/114 PASSED**；冒烟 **39 OK / 0 FAIL**；
- GUI 截图：编辑区剩 载入 / 搜索 / 操作符 / 文字图标 / 参数 / JSON / 写入，纵向再省两行；
- 包 51,113 字节，已覆盖安装；**需重启 Blender 生效**。

## 2026-11-05 · 第37轮：删掉饼编辑器里多余的「方位」下拉

### 判断
- 用户：「饼菜单中方位这个选项是无用的」——对。
- 罗盘 3×3 本来就是唯一的选槽入口；下拉框只是重复。上一轮把「切换下拉不自动载入」加上后，
  它还会造成「表单显示 N、实际写入 E」的错位风险，纯属隐患。

### 改动
- 删除槽位编辑区的「方位」下拉；选槽只走罗盘点击（点击即载入该槽位内容）。
- `piebind_slot_pos` 属性保留（罗盘高亮、清空、载入都靠它），只是不再单独出控件。

### 验证
- headless **114/114 PASSED**；冒烟 **39 OK / 0 FAIL**；
- GUI 截图：编辑区只剩 载入 / 现有 / 参数 / 搜索 / 操作符 / 文字图标 / 参数 / JSON / 写入，
  纵向也省下一行；
- 包 51,267 字节，已覆盖安装；**需重启 Blender 生效**。

## 2026-11-04 · 第36轮：编辑已绑定的饼时，能看到并载入每个槽位的现有功能

### 反馈
- 「修改一个，已绑定的饼菜单中我不清楚对应的功能以及其 json 是什么」。

### 改动
- 槽位编辑区顶部新增两行只读信息：`现有：<文字>｜<操作符 id>` 和 `参数：<JSON>`；空槽显示「该槽位为空」；
- 新增「载入」按钮（`piebind.load_slot`）：把当前槽位已有的操作符 / 文字 / 图标 / 参数读回编辑区；
- 点罗盘方位（`select_slot`）、切换饼（`select_pie`）、新建饼、清空槽位后，编辑区自动同步该槽位；
- **故意不做**：切换「方位」下拉不自动载入——避免把正在填的内容冲掉；信息行始终显示该槽位的真实内容，
  要改再点「载入」。

### 验证
- headless **114/114 PASSED**（新增：读入操作符/参数/文字、空槽清空、重载恢复、操作符注册）；
- 冒烟 **39 OK / 0 FAIL / 4 SKIP**（新增 `load_slot`）；
- GUI 截图：选中「南」槽位后显示「现有：编辑模式｜object.mode_set」「参数：{"mode": "EDIT"}」，
  表单同步预填该操作符与参数；
- 包 51,279 字节，已覆盖安装；**需重启 Blender 生效**。

### 状态 / 下一步
- 现在的编辑流程：点罗盘方位 → 看「现有」两行 → 改 → 写入槽位；改乱了点「载入」重读。

## 2026-11-04 · 第35轮：全操作符冒烟 —— 揪出 1 个原生崩溃

### 方法
- 新增 `tests/run_smoke_ops.py`：**31 个操作符逐个执行**（含「预期报错」用例）、
  5 个菜单用桩布局各画一遍、4 个页签各画一遍，输出 `OK / FAIL / SKIP` 与堆栈。

### 发现
1. **后台调用 `wm.call_menu_pie` 会让 Blender 原生崩溃**（`EXCEPTION_ACCESS_VIOLATION`，Python 抓不住）：
   冒烟跑到 `piebind.dispatch`（目标为饼）时进程直接退出。脚本/后台触发绑定、
   或以后 agent API 调 dispatch 都会踩到；
2. 其余 37 项通过：没有 NameError、非法图标、空数据崩溃。

### 修复
- `dispatch.run_binding`：`bpy.app.background` 时不调用 `call_menu_pie`，报错并返回 `CANCELLED`。
  **注意不能用 `context.area is None` 判断**——GUI 的定时器上下文同样没有 area，但弹饼是正常的
  （第一版就是这么误伤的，已改回 `bpy.app.background`）；
- `piebind.test_pie` / `piebind.call_pie` 加同样保护；
- 回归测试：后台 dispatch 饼目标返回 CANCELLED、预览操作符 invoke 被拒。

### 验证
- 冒烟 **38 OK / 0 FAIL / 4 SKIP**（capture_key、side_listener、test_pie、call_pie 需 GUI，已列出原因）；
- headless **108/108 PASSED**；
- GUI 回归：定时器里 `dispatch` 仍能正常弹饼（`{'INTERFACE'}`）；四个页签重绘、参数预设弹层均无异常；
- 包 50,518 字节，已覆盖安装；**需重启 Blender 生效**。

### 状态 / 下一步
- 冒烟脚本留在 `tests/`，以后改动操作符先跑它；
- 仍未覆盖：modal 类（捕获、侧键监听）与两步交互（改名对话框、导入文件选择器）。

## 2026-11-04 · 第34轮：修「保存绑定」NameError（Keymap 下拉有同类隐患）

### 现象（用户截图）
- 点「保存绑定」直接报错：
  `ops/bindings.py:47 spec = split_keymap_identifier(wm.piebind_keymap)` →
  `NameError: name 'split_keymap_identifier' is not defined`。

### 根因
- 第 24 轮拆分 core/ops/ui 时，`bindings.py` 的导入改成了 `from ..core import ... keyspec`，
  但函数体里仍在用裸名 `split_keymap_identifier(...)` / `make_keymap_identifier(...)`；
- `ops/pickers.py` 的 Keymap 下拉里也裸用了 `keymap_rows(...)` —— 三处都是「改了导入、忘了改调用」，
  只有执行到那一行才会炸，而 headless 测试此前没有覆盖 `create_binding`。

### 修复
- `ops/bindings.py` → `keyspec.split_keymap_identifier` / `keyspec.make_keymap_identifier`；
- `ops/pickers.py` → `keyspec.keymap_rows`；
- 新增**静态扫描测试**：遍历全部模块、反汇编每个函数，检查 `LOAD_GLOBAL` 名字都能解析；
  这类「导入改名漏改调用」以后会在测试里直接失败；
- 新增功能测试：完整走一遍 `piebind.create_binding`，并用桩布局画一遍 Keymap 下拉。

### 验证
- headless **106/106 PASSED**（扫描 0 个未定义全局名）；
- GUI 实测：`create_binding` → `{'FINISHED'}`，状态栏「已保存绑定：CTRL+F8 → wm.context_toggle」，
  列表出现「CTRL+F8 · 3D 视图 · Context Toggle」；真实打开 Keymap 下拉返回 `{'INTERFACE'}` 无异常；
- 包 50,272 字节，已覆盖安装；**需重启 Blender 生效**。

### 状态 / 下一步
- 用户的「视图」饼（6 个方位 TOP/BOTTOM/LEFT/RIGHT/FRONT/BACK）已在配置里，重启后可直接保存绑定；
- 该 bug 自第 24 轮重构起存在，此前没有测试覆盖 `create_binding`。

## 2026-11-04 · 第33轮：整体复查 —— 修 3 个潜在崩溃点 + 2 个失效图标

### 复查范围
- 源码 29 个文件（core / ops / ui 全部）、测试 102 项、扩展包内容、安装副本与源码一致性、三份文档的数字。

### 发现并修掉
1. **槽位图标 `EDIT` 失效**：`ICON_ITEMS` 里还留着 Blender 5.2 不存在的 "EDIT"（第 19 轮同类问题），
   一经选中，绘制饼菜单时 `layout.operator(icon="EDIT")` 会抛异常 → 换成 `TOOL_SETTINGS`；
   另加 `pies.safe_icon()`，老配置里的失效图标绘制前回退成 `NONE`；
2. **设置页图标 `SAVE` 失效**：5.2 无 SAVE → 改 `FILE_TICK`；
3. **图标测试漏扫子包**：第 24 轮分层后测试仍只 `glob("*.py")` 扫根目录，core/ops/ui 里的图标字面量
   从未被检查 → 改 `rglob`，并新增 ICON_ITEMS、冲突徽标两处数据校验；
4. **换操作符后旧参数串台**：先套 `{"type":"TOP"}` 再改选别的操作符，JSON 仍留着（会把 TOP 传给 bevel）
   → 选新操作符时清空参数，并在文字仍是自动名时刷新；
5. **写入槽位不校验参数**：旧 JSON 混入不属于该操作符的键 → 写入时过滤并给 WARNING；
6. **分发器 TypeError 兜底缺口**：`op("INVOKE_DEFAULT", **kwargs)` 失败后重试 `op(**kwargs)`，
   若重试再抛 TypeError 会直接冒泡 → 收进同一层 try，改为报错 + CANCELLED。

### 验证
- headless **102/102 PASSED**（新增：换操作符清参数/刷新文字、写入过滤非法参数、分发安全取消、
  图标回退、ICON_ITEMS 与徽标校验、rglob 扫描）；
- GUI 冒烟：四个页签逐个重绘无 Traceback；真实打开 `PIEBIND_MT_slot_presets` 弹层返回 `{'INTERFACE'}` 无异常；
- 包 50,262 字节，已覆盖安装；**需重启 Blender 生效**。

### 状态 / 下一步
- 复查未发现功能回归；用户配置（2 个饼 / 1 条绑定）未被改动。
- 仍未解决（非本轮引入）：侧键执行不稳定、Blender 4.2 兼容未验证、CI 未真跑、未推 GitHub。

## 2026-11-04 · 第32轮：删掉槽位编辑器的「模式」字段（与操作符选择重复）

### 判断
- 用户问：「饼状图的模式与搜索两个功能是不是重复了」——是的。
- 「模式」是最早的快捷方式：一旦选中，写入时会**强制**改成 `object.mode_set` 并忽略上面选的的操作符；
  第 31 轮有了参数预设后，物体模式 7 项已经能从「参数」下拉一键选中，两者完全重叠。

### 改动
- 删除槽位编辑器的「模式」下拉与「已选模式：将忽略操作符」提示；
- `piebind.add_slot` 去掉 mode 覆盖分支，只认「操作符 + 属性 JSON」；
- 移除 `piebind_slot_mode` 窗口属性与 `MODE_ITEMS` 常量；
- `piebind.apply_slot_preset` 删掉「把模式切回 AUTO」的补丁逻辑（字段没了）。

### 验证
- headless **94/94 PASSED**（新增：模式字段已移除、写入槽位只走操作符+JSON）；
- 旧配置不受影响：槽位里存的是具体 `object.mode_set + {"mode": ...}`，不依赖该字段；
- GUI 截图：编辑器只剩 方位 → 搜索 → 操作符 → 文字/图标 → 参数 → JSON → 写入；
- 包 49,255 字节，已覆盖安装；**需重启 Blender 生效**。

### 状态 / 下一步
- 每个槽位现在只有一条路径：选操作符 →（可选）选参数预设 → 写入槽位。
- 模式槽位改法：在「参数」里选「物体模式 / 编辑模式 / 雕刻模式…」，效果与旧「模式」一致。

## 2026-11-04 · 第31轮：属性 JSON 做成「参数预设」下拉

### 背景
- 用户：「能不能把此功能的所有属性 JSON 做成一个下拉框，让用户选择」；
- 原状：槽位编辑器只有自由文本「属性 JSON」，视图方位要手写 `{"type": "TOP"}`，6 个方位就得写 6 遍。

### 改动
- 新增 `core/presets.py`：静态预设表（视图方位 6 项、物体模式 7 项）+ RNA 枚举兜底
  （冷门操作符自动列出最多 2 个枚举属性 × 16 项，无需手写 JSON）；
- 新增菜单 `PIEBIND_MT_slot_presets`（「参数」下拉）与操作符 `piebind.apply_slot_preset`：
  选中即写入属性 JSON、按需补文字、并把「模式」切回不设置（避免覆盖预设）；
- 槽位编辑器新增「参数」行：已匹配预设时显示名称（如「顶视图 ▾」），否则回显 JSON 原文；
- 文字只在为空或仍是操作符自动名时才覆盖，用户自定义的文字不会被冲掉。

### 验证
- headless **92/92 PASSED**（新增 13 条：预设表、RNA 兜底、菜单桩布局 6 项、写 JSON、补文字、模式回落、标签反查）；
- GUI 探针：点预设后「参数」行显示「顶视图 ▾」、JSON 为 `{"type": "TOP"}`；写入槽位后配置为
  `{"idname": "view3d.view_axis", "props": {"type": "TOP"}, "text": "顶视图"}`，罗盘显示「N 顶视图」；
- 包 49,661 字节，已覆盖安装到 `user_default\piebind`；**需重启 Blender 生效**。

### 状态 / 下一步
- 重启后的用法：选中槽位 → 选操作符 → 点「参数」下拉选方位 → 写入槽位（不再需要手写 JSON）。
- 未验证：下拉弹层本身的截图（Blender 截图拍不到弹窗，改用桩布局 + 实际写盘验证）。

## 2026-11-03 · 第30轮：饼菜单可改名（「无法为新饼菜单命名」）

### 反馈
- 用户：「无法为新饼菜单命名」。

### 定位
- 第 12 轮删掉手动键位输入后，饼名只能在创建前那个**无标签的小输入框**里填；
- 建好之后**没有任何改名入口**——用户配置里正好躺着一个叫「新建饼」的空饼，改名无门；
- 实测 `wm.piebind_new_pie_label` 赋值后能被 `piebind.create_pie` 正确使用（`after=['操作符取的名']`），
  说明不是取值链路坏了，是「建完就不能改」的产品缺口。

### 改动
- 新增 `piebind.rename_pie`：选中饼 →「改 名」弹对话框（名称预填当前值，留空=不改），写盘并回显状态；
- 「饼菜单」页签重排：新饼输入框单独一行并显示「新饼名称」；已选饼下方固定显示「当前名称：xxx」+「改 名」；
- `core/config.py` 新增 `rename_pie()`（去首尾空格 / 空名保留 / 未知 id → None）与 `unique_pie_label()`：
  新建同名饼自动加序号（「模式 2」），避免下拉里一列「新建饼」；
- 新增 8 条 headless 测试（改名落盘、空名、未知 id、重名自增、操作符注册与生效）。

### 验证
- headless **79/79 PASSED**（Blender 5.2.3，exit 0）；
- GUI 探针（`tests/gui_probe_pie_name.py`）截图：页签显示「新饼名称 / 当前名称：模式选择 / 改 名」；
- `rename_pie` INVOKE 返回 `RUNNING_MODAL`；直接执行 `before=模式选择 → after=改名后`，
  状态栏「已改名为：改名后」；
- 包 46,558 字节（46.6 KB），已覆盖安装到 `user_default\piebind`；**需重启 Blender 生效**。

### 状态 / 下一步
- 修复已就位待用户确认；旧配置里那个「新建饼」空饼现在可以直接改名或删掉。
- 文档同步：ENVIRONMENT（目录树/测试数）、README 与 README_zh 的测试数已更新。
- 未验证：真实按键下的改名对话框（GUI 截图未捕捉到弹窗，功能用返回值验证）。

## 2026-11-02 · 第29轮：下沉 `projects\`

- 目录：`<中继目录>` → `<项目目录>`（440 文件 / 1.49 MB，`.git` 一并保留）；
- 路径改写：`ENVIRONMENT.md` 5 处旧绝对路径 → 新路径；本文件里的历史记录按规矩**不清理**；
- 验证：headless `PASSED 71 / FAILED 0`（Blender 5.2.3），退出码 0。

当前状态：通过。下一步：无。未验证：GUI 交互（仅 headless）。

## 2026-11-02 · 第28轮：迁入中枢 `<中继目录>`

- 迁移：`<旧目录>` → `<中继目录>`（同盘秒移，440 文件 / 1.5 MB，`.git` 历史保留）；
- 路径改写：7 个 `tests\gui_probe_*.py` 的 `sys.path.insert(0, r"<旧目录>\src")` → 基于 `__file__` 的相对定位（以后再迁移不用改）；`ENVIRONMENT.md` 5 处旧绝对路径 → 新路径；
- 验证：headless `71/71 PASSED`（exit 0，Blender 5.2.3）；全项目旧路径残留 **0**；
- 未做：DSH 工作区注册表里旧条目仍在（幽灵工作区），需在界面删除。

## 2026-11-02 · 第27轮：侧键（M4/M5）执行支持 —— 常驻监听方案，实测不稳定

### 结论
| 环节 | 状态 |
|---|---|
| 捕获侧键 | ✅ 可靠（Blender 把侧键作为 BUTTON4MOUSE~7 事件送给模态，原样记录实测收到 PRESS/RELEASE） |
| 显示 / 解析 | ✅ `M4`~`M7`；`m4`、`mouse4`、`button4`、`side/back/forward` 别名 |
| 触发绑定 | ⚠️ **不稳定**：常驻模态监听，实测 3 次里 1~2 次能触发 |

### 关键实测结论
1. 写进 keymap 的侧键条目**不会被事件分发**：Window 层、3D View keymap、user/active keyconfig 四种放法都试过，
   `piebind.dispatch` 一次都没被调用（`PIEBIND_DEBUG_DISPATCH` 为空）；同样位置放 `LEFTMOUSE` 也不触发。
2. 模态**能**收到侧键（`BUTTON4MOUSE/PRESS`）。
3. 但模态必须在**真实窗口上下文**里挂载；从定时器或 `temp_override` 里挂，会出现
   “立刻收到 WINDOW_DEACTIVATE 然后静默”——这就是不稳定的根因。

### 实现
- `ops/sidekeys.py`：常驻模态 `piebind.side_listener`（只拦侧键，其余 `PASS_THROUGH`），
  按事件查配置里的绑定并执行；捕获期间自动放行（避免把要绑的侧键执行掉）。
- 注册/延迟应用时尝试挂载；`piebind.dispatch` 执行时也补挂一次（真实按键上下文更可靠）。
- 设置页新增「侧键」区块：显示监听状态 + 「重新挂载侧键监听」按钮。
- 清掉测试期间写进用户配置的 9 条 `BUTTON4MOUSE → wm.context_toggle` 假绑定（保留原有 TAB 绑定 1 条）。

### 验证
- headless **71/71**（新增 `same_combo`、按事件反查绑定、侧键标签/解析 4 条）；
- GUI：`side press BUTTON4MOUSE -> hit` → `called wm.context_toggle` → `use_snap` 由 False 变 True（成功样本）；
  同一构建下也有失败样本（只挂上、不收事件），已如实记录。

### 状态 / 下一步
- 侧键“能用但不可靠”。可选方向：①接受尽力而为 + 手动重挂；②改成“先按一次键盘绑定再挂载”的确定性方案；
  ③放弃执行支持，只保留捕获与显示。

## 2026-11-02 · 第26轮：侧键（BUTTON4~7MOUSE）调研与显示支持

### 结论（实测）
- Blender 5.2 事件类型里确有 `BUTTON4MOUSE` ~ `BUTTON7MOUSE`；
- **模态能收到侧键**：原样记录模态的探针收到 `BUTTON4MOUSE/PRESS`、`BUTTON5MOUSE/PRESS`，
  说明捕获侧键在原理上可行；
- **键位绑定暂不可用**：用 Win32 `XBUTTON1/2` 实测了三种放法（Window 层 / 3D View keymap /
  user+active keyconfig），`piebind.dispatch` 都**没有被调用**（`PIEBIND_DEBUG_DISPATCH` 日志为空）。
  同样方式放 `LEFTMOUSE` 条目也不触发（运行期新增的鼠标条目似乎不进入事件分发）；
  而键盘条目在 `keyconfigs.update()` 后是能触发的（此前已验证）。

### 本轮改动
- `key_label` 增加 `BUTTON4MOUSE→M4`、`BUTTON5→M5`、`BUTTON6→M6`、`BUTTON7→M7`；
- `parse_key_text` 增加别名：`m4/m5/m6/m7`、`mouse4..7`、`button4..7`、`side/back/forward`；
- 新增 2 条测试（侧键标签、侧键解析），headless **67/67**。

### 现状 / 下一步
- 键位绑定暂不支持侧键；若要支持，需要在**注册期**就往 keymap 里放条目（而不是运行期新增），
  并让分发器按 `event.type` 反查绑定（不依赖 `binding_id` 属性）。留待下一轮。
- 包 43.1 KB，已覆盖安装并启用。

## 2026-11-02 · 第25轮：键位显示全大写（绕开 Blender 的界面自动翻译）

### 现象
- 绑定列表里 `Tab` 显示成「选项卡」，`Space` 会变「空间」、`Shift` 变「移位」、`Home` 变「主目录」、`Del` 变「删除」。

### 定位（实测）
用弹出菜单逐词验证：Blender 会对**与界面文案完全相同的字符串**做自动翻译。
- 被翻译：`Tab`→选项卡、`Space`→空间、`Enter`→回车、`Shift`→移位、`Home`→主目录、`End`→结束、`Del`→删除、`Any`→任意
- 不翻译：`TAB`、`[Tab]`、`Tab 键`、`Ctrl`、`Alt`、`Esc`、`F8`、`Page Up`、`LMB`

### 修复
- `key_label()` 统一输出**全大写**：`TAB`、`SPACE`、`ENTER`、`ESC`、`HOME`、`END`、`DEL`、`PGUP`、`CTRL+SHIFT+E`、`ALT+LMB`、`F8`、`CTRL+1`。
  大写形式不在翻译表里，显示稳定。
- 捕获标签、绑定列表、导出/诊断里的键位标签同一来源，全部生效。
- 绑定列表新增说明行「每行依次为：键位 · Keymap · 目标」。

### 验证
- headless **65/65**（标签测试同步改为大写）；
- 逐键实测：`TAB / SPACE / CTRL+SHIFT+E / HOME / DEL / CTRL+1 / ALT+LMB / F8` 全部按原样输出；
- 包 43.0 KB，已覆盖安装并启用；页签探针 `TABS DONE` 无异常。

## 2026-11-02 · 第24轮：整体重构为 core / ops / ui 三层 + 页签式面板

### 结构重构
```
piebind/
  core/   config（schema v2）· keymap · keyspec · pies     ← 纯数据与引擎
  ops/    common · capture · bindings · pie_ops · dispatch · pickers · diag · settings
  ui/     prefs（页签面板）· pickers · widgets · io_ops
  api.py / diagnostics.py
  兼容层：config.py / keymap_engine.py / pie.py（PEP 562 别名，0.3 移除）
```

- 依赖方向单向：`ui → ops → core`，`core` 不再 import 界面或操作符。
- `ops.py`（1000 行）拆成 8 个模块；`ui.py`（350 行）拆成 4 个模块。
- 根 `__init__.py` 只保留注册/卸载/延迟应用，面板类 `bl_idname = __package__` 不变。

### 数据模型 v2
- 新增 `settings`：默认 keymap、默认强制覆盖、默认“仅 3D 视口”。
- `_migrate()` 按 `schema_version` 自动补齐；旧配置（v1）可直接加载。
- 新增操作符：`piebind.save_defaults` / `load_defaults` / `open_config_dir`。

### 界面重做（页签）
```
[已应用 N · 绑定 N · 饼 N]            [应用] [复原]
页签： 绑定 | 饼菜单 | 设置 | 体检
```
- **绑定**：列表行（勾选/键位/keymap/目标/冲突/自检/改键/删除）+ 可折叠的「新建绑定」表单；
- **饼菜单**：饼下拉 → 罗盘 3x3（槽位名称带摘要）→ 已填槽位 N/8 → 槽位编辑器 → 预览；
- **设置**：默认值、导入导出、配置目录、关于；
- **体检**：插件键位扫描。
- 选择器统一（keymap / 操作符 / 饼）全部走 `Menu`，不再用动态枚举。

### 验证
- headless **65/65**；
- GUI 探针打开偏好设置并依次切换四个页签，**无 Traceback**（`PREFS SHOWN` → 四个 `TAB ...` → `TABS DONE`）；
- 包 42.8 KB（文件数 26），已覆盖安装并启用。

### 状态 / 下一步
- 未验证：真实按键下的完整流程（绑定→按 Tab→饼→选模式）。
- 待办：模式级限制（mode 字段）、槽位嵌套菜单、移除兼容层。

## 2026-11-02 · 第23轮：饼菜单条目挤在一起的真正原因 —— 少了 `layout.menu_pie()`

### 用户截图
饼菜单中心显示标题 `PieBind` 和一个条目，其余条目不显示 / 挤在一起。

### 根因
- `PIEBIND_MT_pie.draw()` 直接把条目加到 `self.layout` 上；
- Blender 的饼菜单必须用 **`layout.menu_pie()`** 创建饼布局，直接加到根 layout 的条目会被当成普通列，
  挤在饼中心（这正是截图里的样子）。
- 之前用“最小对照实验”也复现了同样现象，当时误判为“截图环境限制”；实际是**对照实验同样漏了 menu_pie()**。

### 修复
- `draw()` 改为 `pie = layout.menu_pie()`，所有槽位（含空槽的 `separator()`）都画进 `pie`；
- 空饼时显示占位提示，不再画空布局。

### 验证（GUI 实机截图）
- 4 槽位（W 编辑 / E 物体 / N 雕刻 / S 姿态）→ 饼四向分布正确；
- 只填 N + SE → 仍准确落在“北”和“右下”，其余槽位保持空白；
- headless 新增 3 条布局回归测试（`menu_pie()` 被调用、8 槽全部占位、只有已填槽位产生操作符），**65/65**；
- 包 32.6 KB，已覆盖安装并启用。

## 2026-11-02 · 第22轮：强制覆盖支持"跨 keymap 回退"，修 `scan_key_owners`

### 用户状态行
```
检查：键位 Tab · keymap 3D View · 接管 1 条 · 冲突 0 条 · 饼 2 个槽位
```
- “接管 1 条”其实是插件自己在 Window 层创建的条目；`Tab` 在 Blender 里注册在 **Object Non-modal**，
  3D View 里根本没有可接管的条目 → 按键仍被原条目消费。

### 修复
- `_patch_takeover(..., allow_fallback=True)`：所选 keymap 里找不到同键条目时，回退接管
  **同空间或全局（space=EMPTY）** keymap 里的同键条目；`apply()` 已默认启用。
- 接管记录改为写入**实际命中的 keymap**（原来写的是用户所选 keymap，回退时会复原不了）。
- 新增 `scan_key_owners(key)`：列出所有 keymap 里占用该组合键的条目（含归属）。
- 自检输出增强：显示“接管在：Object Non-modal”或“所选 keymap 没有这个键；实际绑在：Object Non-modal(object.mode_set)”。
- 修 `scan_key_owners` 里 `resolve_owner(kmi.idname)` 传参错误（应为 kmi 对象）。

### 验证（GUI 实机）
- 配置 `3D View + Tab + 强制覆盖` → `apply` 报告 `patched: 4`；
  实测条目：`Object Non-modal`、`Animation Channels` 的 Tab 均被改写为 `piebind.dispatch` 且 binding_id 正确；
- `unapply` 后 `Object Non-modal` 的 Tab 恢复为 `object.mode_set`。
- headless **62/62**；包 32.5 KB，已覆盖安装并启用。

## 2026-11-02 · 第21轮：饼菜单占位修复 + 绑定自检按钮 + 槽位概览

### 反馈
1. 饼菜单里的选项“全部挤到一起”；
2. 唯一一个饼无法在 3D 视图使用，按键仍是原功能。

### 排查
- 用**最小对照实验**（4 个 `wm.context_toggle` 条目、完全独立于 PieBind）复现了“只显示一个条目”的现象：
  说明在当前的自动化截图环境里，饼菜单本身就无法被正确截取，不能作为判断依据。
- 代码侧确认：`pie.py` 对 8 个方位逐个调用 `layout.operator()`，符合 Blender 饼菜单规则。
- 但发现一个真实缺陷：**可用性检查失败时用 `layout.label()` 占位**，而 label 在饼菜单里不占槽位，
  会导致后面条目前移/挤在一起。已改为统一用操作符占位（不可用的由 Blender 自动置灰；
  操作符不存在时用新增的 `piebind.slot_missing` 占位）。

### 新增自查能力
- 每个绑定行新增 `?` 按钮（`piebind.check_binding`）：在面板顶部状态行报告
  键位 / keymap / **接管条目数** / 冲突数 / 饼槽位数，并给出“未勾强制覆盖”“该 keymap 没有这个键”等提示。
- 饼菜单区域新增“已填槽位（N）：W、E…”概览，便于确认槽位是否真的写进去。

### 验证
- headless **62/62**；偏好设置面板复现 `NO_DRAW_ERROR`；包 31.8 KB，已覆盖安装并启用。

### 未验证
- 饼菜单真实排布（自动化截图不可用，需用户实际按键确认）。

## 2026-11-02 · 第20轮：恢复面板顺序（饼菜单回到键位之后）

### 反馈
- 用户：「显示顺序错了，饼菜单开启后跑到了最上方」。
- 第 18 轮为绕过“编辑槽位看不到”把饼菜单上移；真正的根因是第 19 轮的非法图标，
  顺序调整已无必要。

### 改动
- 面板顺序恢复为：状态 → 绑定列表 → **新建绑定（键位）** → **饼菜单** → 体检；
- 保留空状态提示与下拉菜单。

### 验证
- 编译检查通过；headless **62/62**；偏好设置面板复现脚本 `NO_DRAW_ERROR`；
- 包 30.9 KB，已覆盖安装并启用。

## 2026-11-02 · 第19轮：根因确认 —— `icon="EDIT"` 非法导致面板绘制中断

### 现象
- 用户截图：饼菜单区域正常，但「编辑槽位」不出现，且**后面的「新建绑定（键位）」整块消失**，底部显示「错误（详见控制台）」。

### 复现与定位
用脚本打开偏好设置面板并抓取控制台：
```
File ".../ui.py", line 225, in draw
TypeError: UILayout.label(): error with keyword argument "icon" -
  enum "EDIT" not found in ('NONE', 'CHAR_NOTDEF', ...)
```
- `icon="EDIT"` 不是 Blender 5.2 的合法图标名；
- 它在「编辑槽位」第一行抛异常 → 该区域内剩余内容与后续所有区块都不再绘制，
  所以编辑槽位“消失”、键位区也“消失”。

### 修复
- `icon="EDIT"` → `icon="TOOL_SETTINGS"`；
- 新增**图标合法性测试**：扫描 `src/piebind/*.py` 中所有 `icon="XXX"`，与
  `UILayout.label` 的图标枚举（1033 个）比对，不合法即 FAIL。

### 验证
- headless **62/62**；源码扫描 0 个非法图标；
- 重新打开偏好设置面板的复现脚本 **不再有 Traceback**（`NO_DRAW_ERROR`）；
- 包 30.9 KB，已覆盖安装并启用。

## 2026-11-02 · 第18轮：饼菜单区域上移 + 空状态提示（“看不到编辑槽位”反馈）

### 反馈
- 用户：「没有出现编辑槽位按键」。

### 原因
- 「编辑槽位」整块只在**已选中饼**时才绘制；没选饼时它直接消失，且饼菜单区块位于面板最下方，
  容易被滚动到视线外，看起来就像“功能不存在”。

### 改动
- 把**饼菜单区块整体上移**：状态 → 饼菜单 → 绑定列表 → 新建绑定 → 体检；
- 无饼时显示提示：“输入名称 → 点「新建饼」，这里就会出现方位和功能编辑”；
- 有饼但未选中时显示提示：“点上面的下拉选择要编辑的饼（新建后会自动选中）”；
- 「预览当前饼」移到罗盘下方一行，避免与删除按钮挤在一起。

### 验证
- 模块编译检查通过；headless **61/61**；包 30.9 KB，已覆盖安装并启用。

## 2026-11-02 · 第17轮：Keymap 选择改为「搜索 + 常用优先菜单」

### 反馈
- 用户截图：Keymap 下拉一次列出 280 项，难以选择（“选项众多”）。

### 改动
- `piebind_keymap` 由动态枚举改为 **StringProperty（JSON 标识）+ 菜单**：
  - 新增 `keymap_rows(query)`：去重、支持按名称/编辑器类型搜索；
  - 新增 `PIEBIND_MT_keymaps` 菜单：常用 16 项优先（3D View、Object Non-modal、Mesh、Sculpt、
    Pose、Node Editor、Dopesheet、Sequencer、UV Editor、Console、Text、Image、NLA、Graph、Outliner、Window），
    其余按名字排序；当前项打勾；最多显示 30 条，超出提示用搜索缩小；
  - 新增 `PIEBIND_MT_keymaps` 选择操作符 `piebind.select_keymap`。
- UI：`Keymap 搜索` 输入框 + `Keymap：xxx [VIEW_3D]` 下拉按钮。
- 未选择时保存绑定默认 3D View，并给 WARNING 提示。
- 新增 3 条测试（列表非空、搜索过滤、常用优先）。

### 验证
- headless **61/61** 通过；包 30.8 KB，已覆盖安装并启用。

## 2026-11-02 · 第16轮：改用 Area/Region.tag_redraw 真正刷新偏好设置面板

### 反馈
- 第 15 轮的 `redraw_timer` 方案无效：用户仍反馈“要动一下鼠标才出现”。

### 排查
- `hasattr(bpy.types.Area, "tag_redraw")` 为 False，但**实例上存在**（`bpy.types` 查不出方法）；
- 实测遍历所有窗口：主窗口 `Layout`（4 个区域）+ 偏好设置窗口 `temp`（1 个区域），
  对它们调用 `area.tag_redraw()` 全部成功，共标记 5 个区域。

### 修复
- `_schedule_redraw()` 改为遍历 `wm.windows → screen.areas → regions` 逐个 `tag_redraw()`；
- 没有任何区域可标记时才退回 `redraw_timer` 兜底。

### 验证
- headless **58/58**；包 30.1 KB，已覆盖安装并启用。
- 标记流程单独验证：输出 `SCREEN Layout … / SCREEN temp … / TAGGED 5`。

### 未验证
- 真实按键下的“立即可见”（需用户重启确认）。

## 2026-11-02 · 第15轮：捕获显示慢 = 面板不重绘；加主动强制重绘

### 定位
- 第 14 轮修完崩溃后用户仍反馈“很慢才显示”。
- 结合日志（事件瞬间到达）判断：**捕获本身是瞬间完成的，慢的是偏好设置面板重绘**——
  Blender 的 Preferences 窗口不会因为属性变化自动重绘，只在收到新事件时才画。

### 修复
- 新增 `_schedule_redraw()`：用 0.01s 定时器调用
  `bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)`（带 window 的 context override）。
- 在**捕获开始 / 成功 / 取消**三处都触发一次，保证左侧键位标签立刻刷新。
- 实测验证：计时器上下文中 `redraw_timer` 调用成功（输出 `REDRAW OK`）。

### 验证
- headless **58/58**；包 29.9 KB，已覆盖安装并启用。

### 未验证
- 真实按键下的“立即可见”（需要用户重启后确认）。

## 2026-11-02 · 第14轮：修 `log_path` 未定义导致的捕获崩溃（并补回归测试）

### 现象（用户截图）
```
File ".../ops.py", line 450, in _finish
    if log_path:
NameError: name 'log_path' is not defined
```

### 原因
第 13 轮把「CAPTURED …」日志写进 `_finish`，但 `log_path` 是 `modal()` 的局部变量，
`_finish()` 里没有定义。属于我自己的疏漏。

### 修复
- `_finish()` 内重新 `log_path = os.environ.get("PIEBIND_DEBUG_CAPTURE")`。
- 新增回归测试：直接以桩对象调用 `PIEBIND_OT_capture_key._finish()`，断言不抛异常且写入
  `piebind_key_json`（这类“入口即崩”的错误以后会被 headless 测试拦住）。

### 验证
- headless **58/58** 通过；包 29.7 KB，已覆盖安装并启用。

## 2026-11-02 · 第13轮：按用户日志定位捕获丢键根因 —— 50ms 防抖误伤

### 日志分析（用户提供 `%TEMP%\piebind_capture.log`）
```
MOUSEMOVE/NOTHING
TAB/PRESS
E/PRESS
W/PRESS
F/PRESS
G/PRESS
LEFT_SHIFT/PRESS
D/PRESS
```
- 事件**全部到达**捕获模态，包括 Tab；
- 每段之间都有 `MOUSEMOVE`，说明用户是「点一次捕获 → 按一个键」逐个测；
- 结合“第一次抓不到、再点一次就能抓”，判定是我上一版加的 **50ms 防抖** 把“点完按钮立刻按下的第一个键”当成了点击余波丢掉。

### 修复
- 移除 50ms 防抖（点击残余的鼠标松开事件本来就由 `value` 过滤掉）；
- 显式忽略 `MOUSEMOVE / INBETWEEN_MOUSEMOVE / TIMER / WINDOW_*` 事件；
- 捕获成功时额外写一行 `CAPTURED <按键> <标签>`，下次排查可直接区分“事件没到”与“到了没记”。

### 验证
- headless **56/56**；包 29.7 KB，已覆盖安装并启用。

## 2026-11-02 · 第12轮：饼菜单/操作符改下拉、饼支持删除、去掉手动键位、捕获加防抖与日志

### 用户要求
1. 饼菜单和搜索改成下拉框；
2. 饼菜单加删除；
3. 去掉手动键位输入；
4. 尽量修捕获 bug。

### 改动
- 新增两个菜单类：
  - `PIEBIND_MT_pies`：列出全部饼（当前项打勾）+ 分隔线 + **删除当前饼**；
  - `PIEBIND_MT_operators`：按搜索词列出最多 20 条操作符（中文名 + id）。
  面板里「目标饼」「编辑饼」「操作符」都变成 `row.menu(...)` 下拉按钮。
- 新增 `piebind.delete_pie`：删除饼并停用引用它的绑定；饼标题旁有 `X` 按钮。
- 移除「手动键位」输入框与其属性/操作符（`parse_key_text` 工具函数保留，测试仍在）。
- 捕获加固：
  - 点击按钮后 50ms 内的残余事件被忽略（避免把点击余波当按键）；
  - 新增 `PIEBIND_DEBUG_CAPTURE=<路径>` 环境变量，记录捕获模态收到的每个事件，用于定位"某些键抓不到"。

### 验证
- headless **56/56** 通过；扩展包 29.7 KB，已覆盖安装并启用。
- 用截图验证下拉菜单渲染正常：`选择饼 ▾` → 模式/建模速取/材质/对齐 + 删除当前饼。

### 未解决
- 捕获偶发失败的根因仍未定位（需要日志复现）。

## 2026-11-02 · 第11轮：手动键位输入 + 饼菜单完整列表

### 反馈
1. 点「捕获」后部分键位第一次抓不到，再点一次就能抓到（T/X 正常，Tab 这类慢）。
2. 饼菜单的「编辑」用一排按钮，饼多了后面的会被截断。

### 改动
- 新增**手动键位**输入：`parse_key_text()` 支持 `TAB` / `ctrl+shift+e` / `F8` / `1` / `alt+LMB` 等写法，
  面板「手动键位 + 应用」直接写入捕获结果；不依赖 modal 捕获，作为稳定兜底。
- 饼菜单区域改成**纵向列表**（所有饼逐个列出、点击选中、当前项高亮），新建绑定里的「目标饼」同样改成列表；
  偏好设置面板本身可滚动，不再截断。
- 新增 6 条解析测试。

### 验证
- headless **56/56** 通过；扩展包 29.3 KB，已覆盖安装并启用。

### 未解决
- 捕获的「第一次抓不到」尚未定位根因（怀疑首帧事件/焦点）；先用手动输入兜底，等用户补充复现细节再修。

## 2026-11-02 · 第10轮：修捕获键位崩溃 + 新增「仅 3D 视口」作用域

### 崩溃（用户实测）
```
AttributeError: 'WorkSpace' object has no attribute 'status_text_clear'
  File ".../ops.py", line 269, in _finish
```
- 5.2 的 `WorkSpace` **没有** `status_text_clear`（实测 `hasattr == False`）。改为兼容封装
  `_clear_status()`：依次尝试 `status_text_clear()` → `status_text_set(None)` → `status_text_set("")`，
  并给 `_set_status()` 同样加降级。
- 捕获 Tab 时因此抛异常；修复后 modal 正常返回 FINISHED。

### 新增作用域
- 绑定可选 `keymap.area`（UI 勾选「仅 3D 视口」）：分发器在区域匹配时才执行，避免全局键在其他编辑器误触发。
- `api.bind()` 的 keymap 参数同样接受 `area` 字段。

### 顺带结论（查证）
- Blender 里**普通 Tab** 注册在 `Object Non-modal`（space=EMPTY），不是 `3D View`；
  想用 Tab 呼出饼，应选该 keymap + 强制覆盖（+ 仅 3D 视口）。

### 验证
- headless **50/50** 通过；扩展包重建（27.7 KB）并覆盖安装、启用。

## 2026-11-02 · 第9轮：操作符搜索支持中文（复用 Blender 自带 UI 翻译）

### 结论
- 新增「id → 英文名 → 本地化名」索引：`operator_index()`，2677 条，首次构建 **78 ms**，缓存到
  `config/piebind/op_index_<blender版本>_<语言>.json`；换语言/版本自动重建（文件名带 key）。
- `search_operators()` 现在同时匹配 **idname / 英文名 / 中文名**；实测：
  - `倒角` → `mesh.bevel`
  - `细分` → `armature.subdivide` / `curve.subdivide` …
  - `合并` → `anim.merge_animation` / `grease_pencil.layer_merge` …
  - `uv` / `bevel` 仍可搜。
- UI 结果按钮显示「中文名 - id」，选中后自动把**中文名**填进槽位文字；饼菜单里也用中文名兜底。
- `invalidate_cache()`（体检页"重新扫描"）会删掉索引文件，强制按当前语言重建。

### 验证
- headless **50/50** 通过（新增中文搜索用例；en 环境自动跳过）。
- 中文环境单独验证：`LOCALE zh_HANS`、索引 2677 条 78 ms、上述四个查询均命中。

### 状态 / 下一步
- 已重新构建（27.4 KB）并手动解压安装到扩展目录、启用并保存偏好（扩展 CLI 的覆盖安装遇到
  `WinError 5` 重命名失败，手动解压绕开）。
- 需要用户**重启 Blender** 才能加载新代码。

## 2026-11-02 · 第8轮：修操作符选择器乱码（动态枚举不可靠 → 改为按钮列表）

### 现象
用户在偏好设置面板截图反馈：`操作符` 下拉显示乱码 `ºÙ 3`（无意义的无效枚举值）。

### 排查
- 存值本身是干净的 ASCII（`action.bake_keys`），`operator_label` 返回的也是 ASCII（`Bevel`）。
- 用弹出菜单复现：同一个动态枚举控件渲染成**空**，且 items 回调在绘制时**根本没有被调用**（加了调试打印，零输出）。
- 结论：在 `bpy.types.WindowManager` 上运行时注册的 `EnumProperty(items=回调)`，下拉绘制时不会重新求值 items；当存值与缓存项不匹配时显示垃圾值。

### 修复
- `piebind_op_choice` 由动态枚举改为 **StringProperty**，配套：
  - 搜索框下方直接列出**结果按钮**（最多 6 条，点击即选中，`piebind.pick_operator`）；
  - 保留“操作符 ID”文本框，允许手填；
  - 选中后自动填槽位文字。
- 其余动态枚举（keymap/pie/方位/图标）加 `options={"SKIP_SAVE"}`，避免跨会话残留无效值。
- `operator_label()` 增加 ASCII 兜底：非 ASCII 标签回退为 idname 派生名。

### 验证
- headless **48/48** 通过。
- 已重新构建（26.8 KB）、覆盖安装到用户扩展目录并启用。

### 状态 / 下一步
- 需要用户重启 Blender 加载新代码后确认面板；如仍有问题继续修。
- 未验证：重启后的面板渲染（我无法截取偏好设置窗口）。

## 2026-11-02 · 第7轮：覆盖机制改为「就地接管」，真实按键端到端全部验证通过

### 结论
- 新增 `_patch_takeover()`：`force_override` 时不再静音，而是把命中的既有条目**就地改写**为
  `piebind.dispatch`（`KeyMapItem.idname` 实测可写），并把原操作符 + 属性快照记进 journal，复原时写回。
- 原因（实测）：区域 keymap 里**被静音的条目仍会消费按键**，Window 层条目接不到，所以只能改写入键条目本身。
- 真实按键验证（`tests/gui_probe_override.py`，Shift+Tab 覆盖内置吸附开关）：
  - 接管：`patched: 2`（`Blender` + `Blender user` 两层同时改写）
  - 按下后：`use_snap_rotate=True`、`use_snap=False` → **我们的目标执行，原功能未被触发**
  - 分发器日志：`enter binding=bd_override area=VIEW_3D` → `called wm.context_toggle -> {'FINISHED'}`
  - 自动复原后无残留。
- 生命周期验证（`tests/gui_probe_lifecycle.py`，隔离配置目录）：扩展启用 → 应用 → 分发器执行 → 禁用 → **残留 0**。
- headless 测试 **48/48** 通过（覆盖改为接管语义后同步更新）。

### 当前状态
- v0.1 的核心承诺全部有实测证据：体检 / 覆盖（可逆）/ 饼菜单调用 / 复原 / 生命周期清理 / agent API。
- 扩展包 `dist/piebind-0.1.0.zip`（约 26 KB），manifest 校验通过。

### 下一步
1. 建 GitHub 仓库并推送、打 tag、Release 挂 zip。
2. CI 首跑（4.2 风险最高）。
3. 真实安装后重启一次，确认无残留（journal/owned 已覆盖，但未做真实重启验证）。

### 未验证
- Blender 4.2 兼容；GitHub Actions 实跑；真实重启后的残留检查。

## 2026-11-02 · 第6轮：端到端打通（`keyconfigs.update()` 是缺失的一环）

### 结论
- 真实按键 → 分发器 → 目标操作，**首次完整验证通过**：
  - 分发器日志：`enter binding=bd_a area=VIEW_3D` → `called wm.context_toggle -> {'FINISHED'}`
  - 探针判定：`运行时按键链路可用 hit=['A']`（按 F8 触发），随后自动复原并退出。
- 根因：向 keyconfig 新增条目后必须调用 **`wm.keyconfigs.update()`** 重新合并键位层，否则条目"存在但不会被事件系统使用"——这解释了此前所有"按了没反应"。
- 副作用（已记录）：`update()` 会把条目**镜像进 `Blender user` 层**（同一 keymap 出现两份）。`purge()/unapply()` 按 `owned.json` 签名跨层清理，重复应用前先清理，测试 49/49 仍全绿。

### 附带改动
- `_deferred()` 增加幂等保护：启动时已应用过且无 journal 残留时**不再 purge 重建**（重建会打断已生效的条目）。
- 新增 `PIEBIND_NO_DEFERRED` 环境变量，供探针隔离定时器影响。
- 新增 `tests/gui_probe_final.py`（双键端到端探针）、`gui_probe_direct.py`（直调分发器）、`gui_probe_layers.py`（分层诊断）等验证脚本。

### 当前状态
- v0.1 逻辑层 + GUI 按键链路**全部验证通过**；扩展包可构建可安装。
- 未验证：Blender 4.2 兼容、GitHub Actions 实跑、卸载后重启的残留检查（有测试覆盖但未做真实重启）。

### 下一步
1. 推 GitHub（仓库地址 + tag + Release 挂 zip）。
2. CI 首跑排查（4.2 最可能出问题）。
3. 真实安装后重启一次，确认无残留。

## 2026-11-02 · 第5轮：运行时绑定改挂 Window 层 + 分发器；修掉三个真 bug；49 项测试全绿

### 关键发现（实测）
- **写进 `keyconfigs.addon` 的运行时条目在当前进程不会被分发**（`keyconfigs.update()` 也不会合并进 active/user 的 keymap_items）。
- **写进 `active` 层的 Window keymap 会被立即分发**（用自定义 `probe.mark` 操作符验证：按下即调用）。
- **写进 `active` 层的区域 keymap（3D View）不会被分发**（覆盖后原功能静音、我们的条目活跃，按键毫无反应）。

### 设计变更
- 所有动态绑定统一挂到 **active keyconfig 的 Window 键位层**，指向分发器 `piebind.dispatch(binding_id)`；
  分发器读取配置、按 `keymap.space` 做区域判断（`context.area` 为 None 时不否决，交由目标 poll），
  再执行目标：饼菜单走 `wm.call_menu_pie`，操作符走 `bpy.ops(...)`。
- 冲突扫描/静音同时覆盖“目标区域 keymap”和 Window keymap；`owned.json` 签名含**操作符属性快照**，避免误删同操作符不同参数的条目。

### 修掉的真 bug
1. `ops.py` 缺 `import os` → 分发器一被调用就抛 `NameError`，表现为“按键毫无反应”；
2. 区域判断过严（`context.area is None` 直接 CANCELLED）→ 窗口级分发普遍被否决；
3. `_new_item` 全量显式传参（`any/oskey/key_modifier/repeat`）与手工验证过的写法不一致 → 改为只传非默认值。

### 验证
- headless 测试 **49/49** 通过（条目落在 active/Window、携带 binding_id、重放不重复、静音/复原、owned 签名、诊断）。
- GUI 直调验证（`tests/gui_probe_direct.py`）：分发器执行目标（`use_snap_rotate=True`）、打开饼菜单（`{'INTERFACE'}`）、复原清理均通过。
- **未完成**：真实按键 → 分发器的端到端确认（多次人工按键未命中，期间发现的 bug 已修复）。

### 当前状态
- v0.1 功能齐备并通过逻辑层测试；GUI 按键链路仅差最后一步确认。
- 副作用：绑定落在 active 层，卸载/崩溃依赖 `unapply` + `owned.json` 清理（已有测试覆盖）。

### 下一步
1. 环境合适时跑 `tests/gui_probe_engine.py`（按 F8）确认端到端。
2. 推送 GitHub、跑 CI。

### 未验证
- 真实按键端到端；Blender 4.2 兼容；GitHub Actions 实跑。

## 2026-11-01 · 第4轮：工程化（README/许可证/CI/诊断）+ 40 项测试全绿 + 仓库初始化

### 结论
- **文档**：新增英文 [README.md](README.md) 与中文 [README_zh.md](README_zh.md)，含功能、安装、快速开始、**诚实版已知限制**、agent API 示例、诊断说明、开发命令、路线图；顶部即写明"不是 Pie Menu Editor 替代品"。
- **许可证**：`LICENSE` = GPL-3.0 全文（35,149 字节，来自 gnu.org），与 manifest 的 `SPDX:GPL-3.0-or-later` 一致。
- **CI**：`.github/workflows/ci.yml`，矩阵 **Blender 4.2 / 4.5 / 5.2**；运行时从 download.blender.org 解析最新补丁版 → 缓存 → 解压 → 跑 headless 测试 → 构建并校验扩展包 → 上传产物。
- **诊断导出**（发 issue 用）：`diagnostics.py` 生成环境快照（版本、三层 keymap 规模、插件键位归属、绑定、重复键、addons 列表），**本地路径脱敏为 `~`**；三种调用方式：面板「诊断」按钮（复制到剪贴板）、`piebind.export_diagnostics`（存文件）、`api.call("diagnostics")`。
- **issue 模板**：`.github/ISSUE_TEMPLATE/bug_report.yml`，强制填 Blender 版本/系统/安装方式，勾选是否附诊断。
- **仓库**：`.gitattributes`（统一 LF）+ 本地 git 初始化并提交，21 文件 / 4028 行。

### 验证
- headless 测试 **40/40 通过**（新增：诊断快照可用、含层信息、路径脱敏）。
- 扩展包重建 `dist/piebind-0.1.0.zip`（23,064 字节），`Success parsing TOML`。
- CI 尚未在 GitHub 上真实跑过（本地无 GitHub 仓库/凭据）。

### 当前状态
- v0.1 代码、文档、打包、测试、CI 配置齐备，**唯一缺口是 GUI 实按验收**（显卡驱动崩溃未恢复）。
- `dist/` 已被 .gitignore 排除，发布时作为 Release 附件上传。

### 下一步
1. 环境恢复 → `tests\run_gui_probe.ps1` 拿实按证据。
2. 建远程仓库、推 main、打 `v0.1.0` tag、挂 zip；观察 CI 首跑（4.2 可能出现 API 差异，需按日志修）。
3. v0.2 视反馈决定：宏 / 嵌套菜单 / 参数表单。

### 未验证
- GitHub Actions 实跑结果（尤其 Blender 4.2 的 `keymap_items.new` 参数差异）。
- 面板渲染与实按行为。
- `ubuntu-24.04` runner 上 Blender 后台模式所需系统库是否齐全。

## 2026-11-01 · 第3轮：交互打磨（罗盘点选/改键/图标/体检页）+ 37 项测试全绿

### 结论
- 测试从 26 → **37 项全绿**，新增覆盖：WM 属性注册、UI 动态枚举回调（keymap/饼/方位/操作符）、重复键识别、apply 报告含 duplicates。
- 键位引擎：操作符 id 与标签**缓存**（`invalidate_cache()` 在体检页"重新扫描"时清空），搜索列表从每次全量遍历改为缓存列表。
- 新增 `duplicate_bindings()`：检测我们自己的绑定互相撞键，并写进 `apply()` 报告的 `duplicates`，面板顶部直接告警。
- 面板重做：
  - **罗盘可点选**：3×3 九宫格，点方位即选中该槽（`piebind.select_slot`），当前槽高亮；
  - **槽位编辑器**：搜索 + 操作符 + 文字 + **图标**（30 个常用图标）+ 写入/清空；选操作符时自动填文字；
  - **绑定行**：按 keymap+键位排序，显示操作符**可读名**（不再只显示 idname）、冲突徽章按严重度取图标、被占用者单独一行、行内 `REC` 按钮**就地改键**（捕获后直接写回并重新应用）；
  - **新建绑定**：撞键且未勾强制覆盖时给出明确提示（"这条绑定很可能不会生效"）；
  - **体检页**：按来源统计（`kekit×3` 这类）、标记与本插件同键的条目、`重新扫描` 按钮；
  - 顶部状态行：已应用/静音/绑定数 + 撞键告警。
- 扩展包重建并校验通过：`dist/piebind-0.1.0.zip`（21.5 KB）。

### 阻塞（未变）
- GUI 仍无法启动：`nvoglv64.dll` / `DrvPresentBuffers`，22:25 再次复测仍崩溃。因此**实按验证与面板截图仍未取得**。

### 当前状态
- 代码侧 v0.1 功能齐备：捕获、重绑、饼（8 槽/图标/置灰）、冲突检测与归因、强制覆盖 + journal 复原、导入导出、agent API、体检页、扩展打包。
- 缺：README/LICENSE/CI/诊断导出/i18n（M4），以及 GUI 实按验收。

### 下一步
1. 环境恢复后跑 `tests\run_gui_probe.ps1`（脚本已就绪，90s 等待 + 焦点校验）。
2. M4：README（中英）+ LICENSE + GitHub Actions（headless 矩阵 4.2/4.5/5.2）+ 诊断导出。
3. 可选：面板内"自检"按钮，让用户一键验证覆盖是否生效（把探针逻辑搬进插件）。

### 未验证
- 面板实际渲染效果（无 GUI 无法截图）。
- 真实键位按下瞬间的覆盖行为。
- 4.2 LTS 兼容。

## 2026-11-01 · 第2轮：headless 测试 26/26 通过，扩展包可构建可安装；GUI 实按验证被 GPU 驱动崩溃阻塞

### 结论
- `tests/run_headless.py` 全绿 **26/26**：配置持久化、键位标签、应用/复原、dry-run 不落库、强制覆盖静音与恢复、journal 写入与清理、缺失操作符降级、API 动作与结构化错误。
- 修掉两个真实缺陷：
  1. `bpy.ops` 的属性访问永远不报错，`hasattr` 判不出操作符是否存在 → 改用 `get_rna_type()` 校验（`piebind.nonexistent_op` 现在能正确跳过）；
  2. `dry_run` 原本只跳过静音、仍会真实创建键位 → 现在 dry-run 完全不建项、不建 keymap。
- `apply()` 重入前先恢复上一轮静音，避免反复应用导致状态漂移。
- 扩展包链路打通：`--command extension build` → `validate` 通过 → 解压到隔离目录 + `BLENDER_USER_EXTENSIONS` → `addon_enable` 成功、`addons[mod].preferences` 为 PieBind 实例、`addon_disable` 干净退出。产物 `dist/piebind-0.1.0.zip`（19.5 KB）。
- manifest 两处被官方校验卡住并修正：`permissions.files` 理由必须 ≤64 字符；`tags` 只能用官方枚举（`Interface` 无效，改用 `User Interface`/`Pipeline`）。

### 阻塞
- **GUI 实按验证当前无法进行**：本机 Blender 5.2.3 启动即 `EXCEPTION_ACCESS_VIOLATION`（`nvoglv64.dll` / `DrvPresentBuffers`），空脚本、`--factory-startup`、`--gpu-backend vulkan`、关闭 Auto HDR 均复现；同一命令在 22:04–22:10 曾正常，属驱动/显示会话侧问题，与插件代码无关。
- `tests/gui_probe.py` + `run_gui_probe.ps1` 已就绪（含 90s 等待、焦点校验、防误输入），等环境恢复即可一键执行。

### 当前状态
- 可用：配置模型、键位引擎（应用/静音/复原/journal 自愈）、单一静态饼菜单类、捕获器、偏好面板、`api.call` 单入口、扩展打包。
- 未做：README/LICENSE/CI、i18n、诊断导出、GUI 实按验收。

### 下一步
1. 环境恢复后执行 `powershell -File tests\run_gui_probe.ps1`，拿到「静音内置 T → 实按 T → use_snap 翻转 → 复原」的证据。
2. M2：面板交互打磨（槽位编辑、冲突徽章、体检页）。
3. M4：README（双语）+ LICENSE + GitHub Actions（headless 测试矩阵）。

### 未验证
- 真实键位上的覆盖是否在**按下瞬间**生效（结构性证据已具备：内置项 inactive + 我们的项 active + journal 落盘）。
- Blender 4.2 LTS 兼容性（本机仅 5.2.3）。
- 崩溃后 journal 自愈的真实进程级场景（脚本内已模拟并通过）。

## 2026-11-01 · 第1轮：立项 + 键位引擎与饼菜单骨架

### 结论
- 确定定位：**键位体检 + 可逆覆盖 + 轻量饼（8 槽）+ 进程内 agent API**，不做 PME 平替。
- 实测确认关键技术前提（Blender 5.2.3）：三层键位共 6467 条、全量扫描 8.8 ms；插件键位归因 6/6 成功；饼菜单槽位顺序为 W/E/S/N/NW/NE/SW/SE。
- 关键设计决策：
  1. 单一静态菜单类 `PIEBIND_MT_pie` + 调用态传参（避免动态注册 `bl_idname` 冲突）；
  2. 覆盖 = 把同 combo 的既有条目 `active=False` 并写 journal，复原按「仍处于我们造成的静音状态」判定；
  3. 配置存 JSON（原子写 + 备份），放弃 addon preferences PropertyGroup，原因是嵌套饼/槽结构在 RNA 里表达成本高且不利于 api/导入导出；
  4. 冲突扫描覆盖 active / user / addon 三层并去重。
- 首版代码：`config.py` / `keymap_engine.py` / `pie.py` / `ops.py` / `ui.py` / `api.py` / `__init__.py`。

### 当前状态
- headless 端到端测试：见文末结果。
- GUI 探针：验证「静音内置项 → 我们的项生效 → 复原」。

### 下一步
- M2：捕获器与冲突提示 UI 打磨、饼编辑罗盘化。
- M3：`api.call` 动作补齐 dry-run 事务与回滚。
- M4：manifest / CI / i18n / README / 诊断导出。

### 未验证
- Blender 4.2 LTS 兼容性（本机只有 5.2.3）。
- 崩溃后 journal 自愈（需强杀进程测试）。
- 跨用户/跨机器的配置导入导出。