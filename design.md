# 相机照片导入自动化系统 - 设计文档

## 一、系统概述

本系统用于自动化备份U盘中的相机照片和视频文件，支持多U盘同时处理，按文件类型分类备份到指定路径。

## 二、配置文件设计

### 2.1 配置文件格式

配置文件为 `config.ini`（INI 格式，支持 `#` / `;` 注释），存放在程序同级目录。仓库提供示例配置 `config.example.ini`，需复制或重命名为 `config.ini` 后修改；`config.ini` 已加入 `.gitignore`，不纳入版本管理。

```ini
# 每个 [strategy.xxx] 段落代表一条备份策略，段落名可自定义
[strategy.1]
suffix = <文件后缀1>, <文件后缀2>
backup_type = <copy|move|delete>
backup_path = <目标备份路径>
target_sub_folder_name_rule = <every_day|every_time>
```

### 2.2 配置字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `suffix` | string | 是 | 文件后缀名，多个用英文逗号（或空格）分隔，不区分大小写，支持多个后缀共享同一策略 |
| `backup_type` | string | 是 | 备份类型：`copy`（复制）、`move`（移动）、`delete`（删除） |
| `backup_path` | string | 否 | 目标备份路径，`delete` 类型时无需填写 |
| `target_sub_folder_name_rule` | string | 否 | 子文件夹命名规则，`delete` 类型时无需填写 |

### 2.3 子文件夹命名规则

#### every_day（按文件修改日期）

**规则**：每个文件根据自身的修改日期生成独立的子文件夹

**格式**：`YYYY.MM.DD`

**逻辑**：
1. 读取文件的 `file_modify_time` 时间戳
2. 转换为 `YYYY.MM.DD` 格式
3. 作为子文件夹名称

**示例**：
```
源文件：photo1.jpg（修改时间 2026-08-03 10:30:00）
源文件：photo2.jpg（修改时间 2026-08-05 14:20:00）

备份结果：
D:\backup\jpg\2026.08.03\photo1.jpg
D:\backup\jpg\2026.08.05\photo2.jpg
```

#### every_time（按时间范围生成子文件夹）

**规则**：相同备份路径（`backup_path`）的所有文件，根据本次备份任务中待备份文件的整体时间范围生成统一的子文件夹

**格式**：根据最早和最晚文件的修改时间动态生成

**适用场景**：无论是单U盘备份还是多U盘备份，都使用相同的规则

**重要特性**：
- **每次备份任务独立**：子文件夹的生成基于每次备份任务中选中的文件，而非程序运行周期内的所有文件
- **单次进程多次备份**：如果单次进程执行多次备份操作，每次备份都会独立计算时间范围并生成新的子文件夹
- **copy 类型的 has_copy 标记**：copy 操作完成的文件会被标记为 `has_copy=1`，下次备份时只处理 `has_copy=0` 的文件；move 和 delete 操作成功后会直接删除数据库记录
- **自定义名称支持**：用户可在备份时输入自定义名称，附加到子文件夹名后
- **查询逻辑差异**：
  - copy 类型：只查询 `has_copy=0` 的文件（待备份文件）
  - move 类型：查询所有文件（move/delete 成功后记录会被删除，剩余的都是待处理的）

**核心逻辑**：
1. **按 backup_path 分组**：将配置中 `target_sub_folder_name_rule` 为 `every_time` 且 `backup_path` 相同的后缀归为一组
2. **计算时间范围**：查询本次备份任务中该组所有后缀的文件，找出整体的最早和最晚修改时间
3. **生成统一文件夹名**：同一组的所有后缀文件共享同一个子文件夹
4. **附加自定义名称**：若用户输入了自定义名称，则在文件夹名后添加空格和自定义名称

**时间范围计算逻辑**：

*单U盘备份时*：
1. 查询该U盘中该组所有后缀的文件（copy 类型只查 has_copy=0）
2. 找出最早和最晚的修改时间
3. 根据时间跨度生成文件夹名

*多U盘备份时*：
1. 遍历所有U盘
2. 对每个U盘，查询该组所有后缀的文件（copy 类型只查 has_copy=0）
3. 合并所有U盘的时间范围，取全局最小值和最大值
4. 根据时间跨度生成文件夹名

*文件夹名格式*：
- 同一天：`YYYY.MM.DD`
- 同月不同日：`YYYY.MM.DD-DD`
- 同年不同月：`YYYY.MM.DD-MM.DD`
- 不同年：`YYYY.MM.DD-YYYY.MM.DD`

*附加自定义名称*：若用户输入了自定义名称，追加到文件夹名后：`{时间范围} {自定义名称}`

**自定义名称规则**：
- 备份操作开始时，提示用户输入此次备份的自定义名称
- 用户可直接回车跳过，使用纯时间范围作为文件夹名
- 若用户输入名称，则在时间范围后添加空格和自定义名称
- 自定义名称对本次备份的所有 every_time 类型文件夹生效

**示例1：同组多后缀（无自定义名称）**
```
配置：{"suffix": ["mov", "mp4"], "backup_path": "D:\\Videos\\Captures", "target_sub_floder_name_rule": "every_time"}
用户输入：（直接回车）

U盘1：video1.mov（修改时间 2026-08-01）
U盘2：video2.mp4（修改时间 2026-08-03）

备份结果：
D:\Videos\Captures\2026.08.01-03\video1.mov
D:\Videos\Captures\2026.08.01-03\video2.mp4
```

**示例2：同组多后缀（有自定义名称）**
```
配置：{"suffix": ["mov", "mp4"], "backup_path": "D:\\Videos\\Captures", "target_sub_floder_name_rule": "every_time"}
用户输入：旅行视频

U盘1：video1.mov（修改时间 2026-08-01）
U盘2：video2.mp4（修改时间 2026-08-03）

备份结果：
D:\Videos\Captures\2026.08.01-03 旅行视频\video1.mov
D:\Videos\Captures\2026.08.01-03 旅行视频\video2.mp4
```

**示例3：不同组独立计算（有自定义名称）**
```
配置1：{"suffix": ["mov", "mp4"], "backup_path": "D:\\Videos\\Captures", "target_sub_floder_name_rule": "every_time"}
配置2：{"suffix": ["dng", "orf"], "backup_path": "D:\\Pictures\\相机", "target_sub_floder_name_rule": "every_time"}
用户输入：周末拍摄

U盘1：video1.mov（修改时间 2026-08-01）、photo1.dng（修改时间 2026-07-28）
U盘2：video2.mp4（修改时间 2026-08-03）、photo2.orf（修改时间 2026-08-02）

备份结果：
D:\Videos\Captures\2026.08.01-03 周末拍摄\video1.mov
D:\Videos\Captures\2026.08.01-03 周末拍摄\video2.mp4
D:\Pictures\相机\2026.07.28-2026.08.02 周末拍摄\photo1.dng
D:\Pictures\相机\2026.07.28-2026.08.02 周末拍摄\photo2.orf
```

### 2.4 配置示例

```ini
[strategy.jpg]
suffix = jpg, jpeg
backup_type = copy
backup_path = D:\backup\jpg
target_sub_folder_name_rule = every_day

[strategy.video]
suffix = mov, mp4
backup_type = move
backup_path = D:\35906\Videos\Captures
target_sub_folder_name_rule = every_time

[strategy.raw]
suffix = dng, orf
backup_type = move
backup_path = D:\35906\Pictures\相机
target_sub_folder_name_rule = every_time

[strategy.delete_lrf]
suffix = lrf
backup_type = delete
```

### 2.5 配置加载逻辑

1. 程序启动时读取 `config.ini`（`configparser` 解析，支持行内注释与 UTF-8 BOM）
2. 若配置文件不存在，不报错：以空策略运行，并提示用户复制 `config.example.ini` 为 `config.ini` 后修改
3. 若配置文件读取失败或段落字段无效（缺少 suffix/backup_type、backup_type 非法等），跳过无效段落并提示；无任何有效策略时按空策略运行
4. 记录当前配置来源（配置文件/未配置）

### 2.6 配置显示格式

显示配置时使用自然语言，而非 JSON 格式：

```
当前生效配置（来源：配置文件/未配置）

备份策略：
1. jpg/jpeg 文件
   - 备份类型：复制
   - 备份路径：D:\backup\jpg
   - 子文件夹规则：按文件修改日期（YYYY.MM.DD）

2. mov/mp4 文件
   - 备份类型：移动
   - 备份路径：D:\Videos\Captures
   - 子文件夹规则：按时间范围生成（同路径文件共享子文件夹）

3. dng/orf 文件
   - 备份类型：移动
   - 备份路径：D:\Pictures\相机
   - 子文件夹规则：按时间范围生成（同路径文件共享子文件夹）

4. lrf 文件
   - 备份类型：删除
```

**说明**：
- 「按时间范围生成（同路径文件共享子文件夹）」表示：相同备份路径的所有文件，根据整体时间范围生成统一的子文件夹
- 无论是单U盘备份还是多U盘备份，都使用相同的规则
- 当没有加载到任何有效策略时，显示"当前没有任何备份策略。"并输出创建配置文件的引导信息

## 三、功能模块

### 3.1 菜单标题信息

#### 3.1.1 统计信息显示规则

| 操作类型 | 显示总文件数 | 显示待备份数 | 说明 |
|----------|--------------|--------------|------|
| copy | 是 | 是 | 需要检查 has_copy 字段，显示待备份（has_copy=0）的数量 |
| move | 是 | 否 | 移动后文件不存在，无需检查 has_copy |
| delete | 是 | 否 | 删除后文件不存在，无需检查 has_copy |

**备份路径显示规则**：

| 子文件夹规则 | 备份路径格式 | 示例 |
|--------------|--------------|------|
| every_time | `{backup_path}/{时间范围}` 或 `{backup_path}/{时间范围} {自定义名称}` | `D:\Videos\Captures\2026.08.01-03` |
| every_day | `{backup_path}/{YYYY.MM.DD}` | `D:\backup\jpg\2026.08.03` |
| delete | 不显示 | - |

#### 3.1.2 主菜单标题格式

```
主菜单

U盘列表：
- E:\ (已初始化，已扫描)
- F:\ (未初始化)

备份统计（所有U盘合计）：
- jpg/jpeg 文件：共 150 个，待备份 20 个，总大小 2.5 GB，操作：copy，路径：D:\backup\jpg\{YYYY.MM.DD}
- mov/mp4 文件：共 50 个，总大小 8.3 GB，操作：move，路径：D:\Videos\Captures\2026.08.01-03
- dng/orf 文件：共 30 个，总大小 15.2 GB，操作：move，路径：D:\Pictures\相机\2026.07.28-2026.08.02
- lrf 文件：共 5 个，总大小 0.3 GB，操作：delete
```

**显示规则**：
- 每个U盘显示盘符和状态（已初始化/未初始化，已扫描/未扫描）
- 未加载到任何有效配置时，标题顶部显示配置提示行（引导复制 config.example.ini 创建 config.ini）
- 统计信息从所有已扫描U盘的数据库中汇总
- copy 类型显示：总文件数量、待备份文件数量、文件总大小、备份路径
- move 类型显示：总文件数量、文件总大小、备份路径
- delete 类型显示：总文件数量、文件总大小
- every_day 类型路径显示占位符 `{YYYY.MM.DD}`，表示按文件日期生成子文件夹
- every_time 类型路径显示实际计算的子文件夹名称
- 未扫描的U盘不参与统计

#### 3.1.3 U盘子菜单标题格式

```
当前在 E:\
本次是否已扫描？是

备份统计：
- jpg/jpeg 文件：共 100 个，待备份 15 个，总大小 1.8 GB，操作：copy，路径：D:\backup\jpg\{YYYY.MM.DD}
- mov/mp4 文件：共 30 个，总大小 5.2 GB，操作：move，路径：D:\Videos\Captures\2026.08.01-03
- dng/orf 文件：共 20 个，总大小 10.1 GB，操作：move，路径：D:\Pictures\相机\2026.07.28-2026.08.02
- lrf 文件：共 5 个，总大小 0.3 GB，操作：delete
```

**显示规则**：
- 显示当前U盘盘符和扫描状态
- copy 类型显示：总文件数量、待备份文件数量（has_copy=0）、文件总大小、备份路径
- move 类型显示：总文件数量、文件总大小、备份路径
- delete 类型显示：总文件数量、文件总大小
- 备份路径格式与主菜单一致

### 3.2 主菜单功能

| 功能 | 显示条件 | 说明 |
|------|----------|------|
| 重新检测U盘 | 始终显示 | 刷新U盘列表 |
| 初始化所有U盘数据库 | 存在未初始化的U盘时显示 | 批量初始化所有未初始化U盘的数据库 |
| 扫描所有U盘文件 | 始终显示 | 扫描所有已连接U盘的文件，记录到数据库 |
| 备份所有U盘文件 | 始终显示 | 将所有U盘文件备份到目标路径 |
| 弹出所有U盘 | 始终显示 | 安全弹出所有U盘 |
| 显示当前配置 | 始终显示 | 以自然语言显示当前生效的配置 |
| 检测目标路径是否存在 | 始终显示 | 遍历所有备份策略中的目标路径，若存在未创建的路径，提示用户创建 |
| <U盘盘符> | 有U盘时显示 | 进入单个U盘菜单 |
| <U盘盘符>(未初始化) | U盘未初始化时显示 | 进入单个U盘菜单 |

### 3.3 U盘子菜单功能（进入单个U盘）

| 功能 | 显示条件 | 说明 |
|------|----------|------|
| 初始化数据库 | U盘未初始化时显示 | 在U盘上创建SQLite数据库 |
| 扫描文件 | 始终显示 | 扫描当前U盘文件 |
| 备份文件 | 始终显示 | 备份当前U盘文件 |
| 弹出U盘 | 始终显示 | 弹出当前U盘 |
| 返回主菜单 | 始终显示 | 返回上级菜单 |

## 四、U盘扫描状态管理

### 4.1 扫描状态记录

- 程序每次运行时，为每个已连接U盘维护一个 `has_scan` 状态（内存变量）
- 初始值为 `False`，执行扫描操作后设为 `True`
- 扫描状态仅在本次程序运行期间有效，程序重启后重置

### 4.2 扫描操作特性

- **幂等性**：扫描操作是幂等的，重复扫描不会产生异常
- **覆盖式更新**：重复扫描时，已有文件记录会被更新，新文件会被添加
- **不影响备份状态**：扫描操作不会修改 `has_copy` 字段（该字段仅 copy 类型使用）

### 4.3 备份前自动扫描

当用户对U盘执行备份操作时，系统会检查该U盘的扫描状态：

```
if not udisk.has_scan:
    自动执行扫描操作
    设置 has_scan = True
执行备份操作
```

### 4.4 扫描状态检查场景

| 场景 | 处理方式 |
|------|----------|
| 单U盘备份 | 检查该U盘是否已扫描，未扫描则自动扫描 |
| 多U盘备份 | 遍历所有U盘，对未扫描的U盘自动执行扫描 |
| 显示统计信息 | 仅显示已扫描U盘的统计数据 |

## 五、数据库设计

### 5.1 file_info 表

```sql
CREATE TABLE file_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path VARCHAR(255),      -- 文件相对路径
    md5 VARCHAR(255) DEFAULT '', -- 文件MD5（预留字段，当前未使用）
    has_copy INTEGER DEFAULT 0,  -- copy操作专用标记：0=未备份，1=已备份（move/delete操作不使用此字段，成功后直接删除记录）
    file_size INTEGER DEFAULT 0, -- 文件大小（字节）
    file_create_time INTEGER DEFAULT 0,  -- 文件创建时间戳
    file_modify_time INTEGER DEFAULT 0,  -- 文件修改时间戳
    suffix VARCHAR(255)          -- 文件后缀名
);
```

**说明**：md5 字段为预留字段，当前使用文件大小和修改时间等数据已满足区分不同文件的需求，无需耗费资源计算 MD5。

### 5.2 backup_log 表

```sql
CREATE TABLE backup_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    log_time INTEGER DEFAULT 0,      -- 日志时间戳
    action_detail VARCHAR(255)       -- 操作结果统计
);
```

## 六、多U盘合并逻辑

### 6.1 合并策略

当执行"扫描所有U盘文件"或"备份所有U盘文件"时：
1. 遍历所有已连接U盘
2. 对每个U盘执行扫描/备份操作
3. **every_time类型文件**：所有U盘的同类型文件共享同一个时间范围子文件夹

### 6.2 时间范围计算

```python
# 计算所有U盘中同备份路径文件的时间范围
def calculate_time_range_for_all_udisks(backup_path_group):
    """
    backup_path_group: 同一 backup_path 下的所有后缀列表，如 ["mov", "mp4"]
    """
    min_time = float('inf')
    max_time = 0
    
    # 构建 IN 查询的占位符
    placeholders = ','.join(['?' for _ in backup_path_group])
    
    # 获取该组的备份类型
    backup_type = get_backup_type_for_group(backup_path_group)
    
    for udisk in udisk_list:
        # 根据备份类型决定查询条件
        if backup_type == 'copy':
            # copy 类型：只查询待备份的文件（has_copy=0）
            query = f"""
                SELECT MIN(file_modify_time), MAX(file_modify_time) 
                FROM file_info 
                WHERE suffix IN ({placeholders}) AND has_copy = 0
            """
        else:
            # move 类型：查询所有文件（move/delete 成功后记录会被删除，剩余的都是待处理的）
            query = f"""
                SELECT MIN(file_modify_time), MAX(file_modify_time) 
                FROM file_info 
                WHERE suffix IN ({placeholders})
            """
        
        cursor.execute(query, backup_path_group)
        result = cursor.fetchone()
        if result and result[0]:
            min_time = min(min_time, result[0])
            max_time = max(max_time, result[1])
    
    return min_time, max_time
```

### 6.3 子文件夹命名生成

```python
def generate_sub_folder_name(min_time, max_time):
    min_ymd = time.strftime("%Y.%m.%d", time.localtime(min_time))
    max_ymd = time.strftime("%Y.%m.%d", time.localtime(max_time))
    
    if min_ymd == max_ymd:
        return min_ymd
    
    min_year, min_month, min_day = min_ymd.split('.')
    max_year, max_month, max_day = max_ymd.split('.')
    
    if min_year != max_year:
        return f"{min_ymd}-{max_ymd}"
    elif min_month != max_month:
        return f"{min_year}.{min_month}.{min_day}-{max_month}.{max_day}"
    else:
        return f"{min_year}.{min_month}.{min_day}-{max_day}"
```

## 七、备份流程

### 7.1 备份前检查（通用）

无论单U盘还是多U盘备份，都需执行以下检查：

```
1. 提示用户输入此次备份的自定义名称（可直接回车跳过）
2. 检查目标备份路径是否存在，不存在则提示用户创建
3. 对每个需要备份的U盘：
   a. 检查数据库是否存在
      - 不存在：初始化数据库
      - 存在但损坏：删除数据库文件，中断备份流程，提示用户重新初始化
   b. 检查该U盘是否已扫描（has_scan），未扫描则自动执行扫描
```

### 7.2 备份执行流程

```
1. 根据配置获取待备份文件列表
2. 按 backup_path 分组（every_time 类型）计算时间范围，生成子文件夹名称
3. 对每组文件执行备份操作：
   a. copy 类型：
      - 复制文件到 {backup_path}/{子文件夹名}/{原始文件名}
      - 同名文件处理见第九章
      - 成功后更新 has_copy=1
   b. move 类型：
      - 移动文件到 {backup_path}/{子文件夹名}/{原始文件名}
      - 同名文件处理见第九章
      - 成功后从数据库删除该文件记录
   c. delete 类型：
      - 删除源文件
      - 成功后从数据库删除该文件记录
4. 记录备份日志
```

### 7.3 单U盘与多U盘的区别

| 项目 | 单U盘备份 | 多U盘合并备份 |
|------|----------|---------------|
| 检查范围 | 仅检查当前U盘 | 遍历所有U盘逐一检查 |
| 时间范围计算 | 仅计算当前U盘的文件时间范围 | 合并所有U盘的文件时间范围 |
| 子文件夹名称 | 基于当前U盘文件生成 | 基于所有U盘文件生成（统一名称） |
| 执行顺序 | 当前U盘立即执行 | 计算统一子文件夹后，依次对每个U盘执行 |

## 八、U盘弹出逻辑

### 8.1 单U盘弹出

```python
def eject_udisk(drive_letter):
    # 使用 DeviceIoControl API 弹出U盘
    # IOCTL_STORAGE_EJECT_MEDIA = 0x2D4808
```

### 8.2 批量弹出

```python
def eject_all_udisks():
    for udisk in udisk_list:
        eject_udisk(udisk['drive_path'][0])
```

## 九、同名文件处理策略

### 9.1 处理规则

当目标路径已存在同名文件时，根据文件大小判断是否为同一文件：

| 场景 | 处理方式 |
|------|----------|
| 目标文件不存在 | 正常复制/移动，使用原始文件名 |
| 目标文件存在且大小相同 | 视为同一文件，跳过并标记为已备份 |
| 目标文件存在但大小不同 | 重命名后复制/移动，添加数字后缀 |

### 9.2 重命名规则

当需要重命名时，按以下规则生成新文件名：

```
原始文件名: photo.jpg
重命名后:  photo_1.jpg
再次冲突:  photo_2.jpg
再次冲突:  photo_3.jpg
...
```

**命名格式**：`{文件名}_{序号}.{扩展名}`

**序号规则**：
- 从 1 开始递增
- 每次检查目标文件是否存在，直到找到不存在的文件名
- 不会出现 `_1_1` 这样的嵌套后缀

### 9.3 处理流程

```
待备份文件: source.jpg
目标目录: D:\backup\jpg\2026.08.03\

1. 构建目标路径: D:\backup\jpg\2026.08.03\source.jpg
2. 检查目标文件是否存在
   ├── 不存在 → 执行复制/移动 → 完成
   └── 存在 → 比较文件大小
       ├── 大小相同 → 跳过，标记为已备份
       └── 大小不同 → 需要重命名
           ├── 检查 source_1.jpg 是否存在
           │   ├── 不存在 → 使用此名称，执行复制/移动
           │   └── 存在 → 比较大小
           │       ├── 大小相同 → 跳过
           │       └── 大小不同 → 检查 source_2.jpg
           │           └── ... 继续递增序号
```

### 9.4 日志记录

| 场景 | 日志级别 | 日志内容 |
|------|----------|----------|
| 正常备份 | INFO | `备份成功：{source} -> {target}` |
| 已存在且大小相同 | INFO | `跳过（已存在且相同）：{source}` |
| 重命名后备份 | INFO | `备份成功（重命名）：{source} -> {target}` |

### 9.5 设计说明

- **为什么需要重命名**：不同相机可能使用相同的文件名（如 DSC_0001.jpg），同一张照片的不同版本（如裁剪、调色）也可能需要保留
- **为什么使用数字后缀**：数字后缀简洁清晰，便于识别文件顺序，不会出现嵌套后缀
- **大小相同视为同一文件**：同一相机拍摄的同一张照片，文件大小通常一致，可安全跳过
- **不覆盖原文件**：避免意外覆盖用户可能已修改的文件，保护数据安全

## 十、错误处理

| 场景 | 处理方式 |
|------|----------|
| U盘已弹出 | 提示用户，返回主菜单 |
| 目标路径不存在 | 提示用户创建路径 |
| 文件复制/移动失败 | 记录错误统计，继续处理其他文件 |
| 数据库损坏 | 删除数据库文件，中断备份流程，提示用户重新初始化 |
| 配置文件不存在 | 不报错：以空策略运行，提示用户复制 config.example.ini 为 config.ini 后修改 |
| 配置文件读取失败/段落无效 | 跳过无效段落并提示，无有效策略时按空策略运行 |
| 未配置有效策略时执行扫描/备份 | 提示先创建并配置 config.ini，不执行操作 |
| 同名文件存在且大小相同 | 跳过，标记为已备份（见第九章） |
| 同名文件存在且大小不同 | 重命名后备份（见第九章） |
