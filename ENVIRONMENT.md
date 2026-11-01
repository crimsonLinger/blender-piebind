# PieBind — 环境与依赖

Blender 的键位体检 + 轻量饼菜单插件（自定义快捷键编辑器）。

## 目标环境（本机实测）

| 项 | 值 |
| --- | --- |
| Blender | 5.2.3 LTS（`blender`） |
| Python | 3.13.13（Blender 内置） |
| 操作系统 | Windows |
| 用户配置 | `%APPDATA%\AppData\Roaming\Blender Foundation\Blender\5.2\` |

## 无需下载任何第三方依赖

纯 `bpy` 实现，不使用任何 wheel / 外部库。

| # | 要下载的东西 | 大小 | 为什么需要 | 从哪获取 | 放到哪 | 必须/可选 |
| --- | --- | --- | --- | --- | --- | --- |
| — | 无 | — | 全部使用 Blender 自带 Python 与 bpy | — | — | — |

> 仅当后续需要 GitHub Actions 时，CI 里会下载 Blender 官方压缩包（服务器侧，不影响本机）。

## 目录结构

```
<旧目录>\
├─ src\piebind\          # 插件源码（扩展包根目录）
│  ├─ __init__.py        # 注册/卸载、延迟应用、崩溃对账
│  ├─ config.py          # JSON 存储（原子写 + 备份）
│  ├─ keymap_engine.py   # 键位应用/静音/复原/冲突扫描/归因
│  ├─ pie.py             # 单一静态饼菜单类
│  ├─ ops.py             # 捕获、应用、复原、调用饼
│  ├─ ui.py              # 偏好设置面板
│  ├─ api.py             # agent 可调用 API
│  ├─ i18n.py            # 中英文本
│  └─ blender_manifest.toml
├─ tests\                # headless 测试
├─ scripts\              # 打包脚本
├─ ENVIRONMENT.md
└─ CHANGELOG.md
```

## 自验证命令

```powershell
# 1) headless 端到端测试（不弹窗，40 项）
& 'blender' -b --factory-startup --python-exit-code 1 --python '<旧目录>\tests\run_headless.py'

# 2) 构建 + 校验扩展包（产物在 dist\）
pwsh -File '<旧目录>\scripts\build.ps1'
# 若机器上没有 pwsh，用：
powershell -NoProfile -ExecutionPolicy Bypass -File '<旧目录>\scripts\build.ps1'

# 3) GUI 覆盖探针（会短暂打开 Blender 窗口，并需要屏幕处于解锁状态）
powershell -NoProfile -ExecutionPolicy Bypass -File '<旧目录>\tests\run_gui_probe.ps1'
```

预期：1) 输出 `ALL TESTS PASSED`；2) 输出 `Success parsing TOML` 并生成 `dist\piebind-0.1.0.zip`；3) 输出 `OK 实按热键后我们的操作生效`。

### 已验证（2026-11-01）

| 项 | 结果 |
| --- | --- |
| headless 测试 | 40/40 通过 |
| 扩展包构建 | `dist\piebind-0.1.0.zip`，23 KB |
| 扩展包校验 | `Success parsing TOML` |
| 隔离安装 + 启用 | `BLENDER_USER_EXTENSIONS=<tmp>` 下 `addon_enable` 成功，`addons[mod].preferences` 为 PieBind 实例，禁用干净 |
| GUI 实按验证 | **被本机 NVIDIA 驱动崩溃阻塞**（见下） |

### 已知环境问题（非插件缺陷）

Blender 5.2.3 在本机会话里启动即崩溃：`EXCEPTION_ACCESS_VIOLATION`，模块 `nvoglv64.dll`，栈 `DrvPresentBuffers`。
已排除：空脚本、`--factory-startup`、`--gpu-backend vulkan`、关闭 Auto HDR 注册表项。
22:04–22:10 同命令曾正常运行，22:15 后持续崩溃 → 属显示/驱动会话状态问题。恢复后可重跑探针。

## 项目注意点

1. **键位层**：Blender 5.2 存在 `Blender`（默认层，当前 active）、`Blender user`（用户层）、`Blender addon`（插件层，所有插件共用）三层；插件加的键位**优先级最低**，要覆盖必须把同 combo 的条目 `active=False`。
2. **插件的键位会被镜像进 user 层**：扫描时必须去重，否则冲突提示会重复。
3. **注册瞬间 keyconfig 可能尚未加载**：应用逻辑必须延迟（timer / `load_post`），且幂等。
4. **静音是有副作用的**：必须写 journal，禁用插件或下次启动时恢复；`userpref.blend` 改动前先备份。
5. 后台模式（`-b`）下默认层键位为空，**覆盖类测试只能在 GUI 下做**。

## 对外接口

- 人类：偏好设置 › Add-ons › PieBind 面板（捕获、绑定、饼编辑、体检、诊断）。
- Agent：`import piebind.api as api; api.call("describe")`（进程内，无需网络）。
- 诊断：面板「诊断」按钮复制 JSON；或 `piebind.export_diagnostics` / `api.call("diagnostics")`。

## GitHub / CI

- 仓库已本地初始化（`main`，首次提交含 21 文件）。
- CI：`.github/workflows/ci.yml`，ubuntu-24.04 上按 **4.2 / 4.5 / 5.2** 矩阵解析最新补丁版 → 缓存 → 跑 headless 测试 → 构建 + 校验扩展包 → 上传 artifact。
- 尚未推送远程、未真实跑过 Actions；`.gitattributes` 已统一 LF。