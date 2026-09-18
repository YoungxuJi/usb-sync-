# 相机照片导入自动化系统

一个运行于 Windows 的交互式命令行工具，用于自动备份 U 盘中的相机照片和视频文件。程序会扫描插入的可移动 U 盘，根据文件后缀执行复制、移动或删除操作，并按日期或时间范围自动归类到指定目标路径，支持多 U 盘合并处理与增量备份。

## 功能特性

- **自动检测 U 盘**：枚举所有已插入且可访问的可移动驱动器
- **基于后缀的备份策略**：不同文件类型可配置不同的操作（复制 / 移动 / 删除）与目标路径
- **灵活的目录组织**：
  - `every_day`：按每个文件自身的修改日期归档（`YYYY.MM.DD`）
  - `every_time`：按本次备份文件的整体时间范围生成统一子文件夹，相同目标路径的文件共享同一文件夹，支持附加自定义名称
- **增量备份**：复制完成的文件会标记为已备份，下次只处理新增或发生变化的文件
- **同名文件智能处理**：目标已存在同名文件时，大小相同视为同一文件自动跳过；大小不同则自动追加数字后缀（`photo_1.jpg`），不覆盖任何已有文件
- **多 U 盘合并处理**：一次性扫描 / 备份 / 弹出所有 U 盘，`every_time` 类型文件跨 U 盘共享统一时间范围子文件夹
- **U 盘本地数据库**：每个 U 盘在 `.auto_backup_data/sqlite.db` 中维护文件索引与备份日志，实现去重与审计
- **安全弹出 U 盘**：通过 Windows DeviceIoControl API 弹出设备

## 环境要求

- Windows 操作系统（依赖 pywin32 与 Windows API，无法跨平台运行）
- Python 3.x

## 安装

安装第三方依赖 pywin32（其余均为 Python 标准库）：

```bash
pip install pywin32
```

## 快速开始

**第一步：创建配置文件**

将示例配置 `config.example.ini` 复制或重命名为 `config.ini`，并按文件内注释修改备份策略（详见[配置说明](#配置说明)）：

```bash
copy config.example.ini config.ini
```

**第二步：运行程序**

```bash
python main.py
```

典型使用流程：

1. 插入 U 盘，运行程序
2. 首次使用时先初始化 U 盘数据库（主菜单或 U 盘菜单中均有入口）
3. 扫描文件（执行备份时若未扫描会自动扫描）
4. 执行备份，可按提示输入自定义名称（直接回车跳过）
5. 备份完成后安全弹出 U 盘

## 配置说明

配置文件为程序同级目录下的 `config.ini`（INI 格式，支持 `#` / `;` 注释）。仓库中提供示例配置 `config.example.ini`，首次使用请：

1. 将 `config.example.ini` 复制或重命名为 `config.ini`
2. 按文件内注释修改备份策略
3. 重新运行程序使配置生效

> - `config.ini` 已被 `.gitignore` 忽略，不会被 git 记录；程序不会自动创建配置文件
> - 若启动时未找到 `config.ini`，程序不报错：以空策略运行（不扫描、不备份任何文件），并提示创建方法
> - 配置修改后需重启程序生效

### 配置格式

```ini
# 每个 [strategy.xxx] 段落代表一条备份策略，可自由增加、删除或调整顺序
[strategy.jpg]
suffix = jpg, jpeg
backup_type = copy
backup_path = D:\Backup\Photos
target_sub_folder_name_rule = every_day

[strategy.video]
suffix = mov, mp4
backup_type = move
backup_path = %USERPROFILE%\Videos\Captures
target_sub_folder_name_rule = every_time

[strategy.raw]
suffix = dng, orf
backup_type = move
backup_path = %USERPROFILE%\Pictures\相机
target_sub_folder_name_rule = every_time

[strategy.delete_lrf]
suffix = lrf
backup_type = delete
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `suffix` | string | 是 | 文件后缀名，多个用英文逗号（或空格）分隔，不区分大小写，多个后缀可共享同一策略 |
| `backup_type` | string | 是 | 操作类型：`copy`（复制）、`move`（移动）、`delete`（删除） |
| `backup_path` | string | 否 | 目标备份路径，`delete` 类型无需填写；支持环境变量（如 `%USERPROFILE%`）与 `~` 前缀，加载时自动展开为实际路径 |
| `target_sub_folder_name_rule` | string | 否 | 子文件夹命名规则：`every_day` / `every_time`，`delete` 类型无需填写 |

### 子文件夹命名规则

**every_day（按文件修改日期）**

每个文件根据自身修改日期归入独立子文件夹：

```
D:\backup\jpg\2026.08.03\photo1.jpg
D:\backup\jpg\2026.08.05\photo2.jpg
```

**every_time（按时间范围）**

相同 `backup_path` 的所有文件根据本次备份任务中文件的整体时间范围（最早 ~ 最晚修改时间）生成统一子文件夹，多 U 盘备份时合并计算：

| 时间跨度 | 文件夹名格式 | 示例 |
|----------|--------------|------|
| 同一天 | `YYYY.MM.DD` | `2026.08.03` |
| 同月不同日 | `YYYY.MM.DD-DD` | `2026.08.01-03` |
| 同年不同月 | `YYYY.MM.DD-MM.DD` | `2026.07.28-08.02` |
| 不同年 | `YYYY.MM.DD-YYYY.MM.DD` | `2025.12.30-2026.01.02` |

备份时若输入自定义名称，将追加到文件夹名后：`2026.08.01-03 旅行视频`

### 备份类型行为差异

| 行为 | copy | move | delete |
|------|------|------|--------|
| 源文件保留 | 保留 | 移走 | 删除 |
| 数据库记录 | 标记 `has_copy=1`，下次跳过 | 删除记录 | 删除记录 |
| 支持同名冲突处理 | 是 | 是 | - |

## 使用说明

程序为多级菜单交互，在任意菜单输入 `q` 退出。

**主菜单**

| 选项 | 说明 |
|------|------|
| 重新检测 U 盘 | 刷新 U 盘列表 |
| 初始化所有 U 盘数据库 | 为未初始化的 U 盘批量创建数据库 |
| 扫描所有 U 盘文件 | 扫描所有已连接 U 盘并记录到数据库 |
| 备份所有 U 盘文件 | 将所有 U 盘文件按策略备份到目标路径 |
| 弹出所有 U 盘 | 安全弹出全部 U 盘 |
| 显示当前配置 | 以自然语言显示当前生效的备份策略 |
| 检测目标路径是否存在 | 检查并提示创建缺失的备份目录 |
| `<U 盘盘符>` | 进入单个 U 盘子菜单 |

**U 盘子菜单**：初始化数据库（未初始化时）、扫描文件、备份文件、弹出 U 盘、返回主菜单。

菜单标题会实时显示 U 盘初始化/扫描状态，以及各类型文件的数量、待备份数量、总大小和目标路径等统计信息。

## 数据存储

每个 U 盘根目录下维护 `.auto_backup_data/sqlite.db` 数据库：

- **file_info 表**：文件索引，记录相对路径、大小、创建/修改时间、后缀及 `has_copy` 备份标记，用于增量去重
- **backup_log 表**：备份日志，每次备份后记录一次汇总统计（复制/移动/删除/跳过/失败数量）

> 删除 `.auto_backup_data` 目录即可重置该 U 盘的备份状态。

## 同名文件处理策略

| 场景 | 处理方式 |
|------|----------|
| 目标文件不存在 | 正常复制/移动 |
| 目标文件存在且大小相同 | 视为同一文件，跳过并标记为已备份 |
| 目标文件存在但大小不同 | 重命名后备份：`photo.jpg` → `photo_1.jpg` → `photo_2.jpg` ... |

## 项目结构

```
.
├── main.py             # 主程序：配置加载、U 盘管理、扫描、备份、统计、弹出
├── MenuSystem.py       # 通用命令行菜单框架
├── config.example.ini  # 示例配置：复制或重命名为 config.ini 后修改
├── config.ini          # 备份策略配置（需手动创建，已被 git 忽略）
└── design.md           # 设计文档
```

## 注意事项

- 程序仅识别 `DRIVE_REMOVABLE` 类型的可移动驱动器，不会处理固定硬盘
- 程序不会自动创建配置文件：未找到 `config.ini` 时以空策略运行，并按提示复制 `config.example.ini` 创建
- 扫描是幂等的：重复扫描会更新已有记录、补充新文件，并将发生变化的文件重新标记为待备份
- 备份前若目标路径不存在，程序会提示创建；选择不创建则中断本次备份
- 备份过程中单个文件失败不会中断整体流程，结束后会汇总显示失败数量
