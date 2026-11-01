# CHANGELOG

倒序记录。每轮迭代追加：`## 日期 · 第N轮：一句话主题`，末尾写「当前状态 / 下一步 / 未验证」。

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