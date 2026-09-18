import os
import sys
import time
import configparser
from MenuSystem import MenuSystem  # 从模块中导入类
import win32api
import win32con
import win32file
import ctypes
import sqlite3


udisk_list = []
current_udisk = None
current_suffix_sub_floder_name_map = {}
config_source = "未配置"

CONFIG_FILE_NAME = 'config.ini'                  # 实际使用的配置文件（已加入 .gitignore，不被git记录）
EXAMPLE_CONFIG_FILE_NAME = 'config.example.ini'  # 示例配置文件（随仓库分发）
__version__ = '1.0.0'                            # 程序版本号（与 git tag、GitHub Release 保持一致，发布新版本时同步修改）

# SUFFIX_SETTING 和相关常量由 load_config() 函数统一管理配置加载
# load_config() 会从 config.ini 加载配置，若不存在则以空策略运行并提示用户创建配置文件
# 这些变量将在 load_config() 中初始化
SCAN_SUFFIX_LIST = []
SAME_PATH_WHIH_EVERY_TIME_SUFFIX = {}
#{
#    backup_path:{
#        old_path:string
#        real_path:string
#        suffix_list:[string]
#        oldest_file_time:int
#        last_file_time:int
#    }
#}
backup_paths_info = {}


def init_backup_paths_info():
    global backup_paths_info
    for suffix in SCAN_SUFFIX_LIST:
        if 'target_sub_floder_name_rule' in SUFFIX_SETTING[suffix] and SUFFIX_SETTING[suffix]['target_sub_floder_name_rule'] == 'every_time':
            if SUFFIX_SETTING[suffix]['backup_path'] in backup_paths_info:
                backup_paths_info[SUFFIX_SETTING[suffix]['backup_path']]['suffix_list'].append(suffix)
            else:
                backup_paths_info[SUFFIX_SETTING[suffix]['backup_path']] = {
                    'old_path': '',
                    'real_path': '',
                    'suffix_list': [suffix],
                    'oldest_file_time': 0,
                    'last_file_time': 0
                }

def get_actual_usb_drives():
    """获取当前插入的可读U盘"""
    actual_drives = []
    bitmask = win32api.GetLogicalDrives()
    
    for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
        if bitmask & 1:
            drive_path = f"{letter}:\\"
            drive_type = win32file.GetDriveType(drive_path)
            
            if drive_type == win32con.DRIVE_REMOVABLE:
                try:
                    # 尝试获取卷标信息，如果失败则说明U盘未实际插入
                    win32api.GetVolumeInformation(drive_path)
                    # 检查是否可访问
                    os.listdir(drive_path)
                    actual_drives.append(drive_path)
                except:
                    # 发生异常说明U盘未插入或不可访问
                    continue
        bitmask >>= 1
    drives_info = []
    for drive_path in actual_drives:
        has_sqlite_flie = os.path.exists(os.path.join(drive_path, '.auto_backup_data/sqlite.db'))
        info = {
            "drive_path": drive_path,
            "has_sqlite_flie": has_sqlite_flie,
        }
        drives_info.append(info)
    return drives_info

def is_drive_ready(drive_letter):
    """检查驱动器是否准备好（未弹出）"""
    drive_letter = drive_letter.upper()
    if not drive_letter.endswith(':'):
        drive_letter += ':'
    
    drive_path = drive_letter + '\\'
    
    try:
        # 检查驱动器类型
        drive_type = win32file.GetDriveType(drive_path)
        if drive_type != win32con.DRIVE_REMOVABLE:
            return False
            
        # 尝试访问驱动器，确认是否真的可用
        os.listdir(drive_path)
        return True
    except Exception as e:
        # 如果发生异常，说明U盘已弹出或不存在
        return False

def action_init_sqlite_db():
    global current_udisk
    sql_path = os.path.join(current_udisk['drive_path'], '.auto_backup_data/sqlite.db')
    sql_dir = os.path.dirname(sql_path)
    if os.path.exists(sql_path):
        print("sqlite.db已存在")
        current_udisk['has_sqlite_flie'] = True
    else:
        #判断目录是否存在，若不存在则创建
        if not os.path.exists(sql_dir):
            os.mkdir(sql_dir)
            print("创建目录成功")

        conn = sqlite3.connect(sql_path)
        cursor = conn.cursor()
        cursor.execute("create table file_info(" \
            "id integer primary key autoincrement," \
            "file_path varchar(255)," \
            "md5 varchar(255) default ''," \
            "has_copy integer default 0," \
            "file_size integer default 0," \
            "file_create_time integer default 0," \
            "file_modify_time integer default 0," \
            "suffix varchar(255))")
        cursor.execute("create table backup_log(id integer primary key autoincrement, log_time integer default 0, batch_index interger default 0 , action_detail varchar(255))" )
        conn.commit()
        cursor.close()
        conn.close()
        current_udisk['has_sqlite_flie'] = True


    return action_into_udisk(current_udisk)
    

def action_pop_udisk():
    """
    操作：弹出当前U盘，并刷新U盘列表
    """
    drive_letter = current_udisk['drive_path'][0]
    try:
        # 使用正确的API来弹出U盘
        # 先尝试使用RemoveDrive工具方法
        result = ctypes.windll.kernel32.GetDriveTypeW(f"{drive_letter}:\\")
        if result != win32con.DRIVE_REMOVABLE:
            print("设备类型不是可移动设备")
            return action_into_main_menu()
            
        # 使用DeviceIoControl方法弹出U盘
        from ctypes import wintypes
        
        # 定义常量
        IOCTL_STORAGE_EJECT_MEDIA = 0x2D4808
        GENERIC_READ_WRITE = 0x80000000 | 0x40000000
        OPEN_EXISTING = 3
        
        # 构造设备路径
        device_path = f"\\\\.\\{drive_letter}:"
        
        # 打开设备
        handle = ctypes.windll.kernel32.CreateFileW(
            device_path,
            GENERIC_READ_WRITE,
            0x1 | 0x2,  # FILE_SHARE_READ | FILE_SHARE_WRITE
            None,
            OPEN_EXISTING,
            0,
            None
        )
        
        if handle == -1:  # INVALID_HANDLE_VALUE
            print("无法打开设备句柄")
            return action_into_main_menu()
            
        # 弹出设备
        bytes_returned = wintypes.DWORD()
        result = ctypes.windll.kernel32.DeviceIoControl(
            handle,
            IOCTL_STORAGE_EJECT_MEDIA,
            None,
            0,
            None,
            0,
            ctypes.byref(bytes_returned),
            None
        )
        
        # 关闭句柄
        ctypes.windll.kernel32.CloseHandle(handle)
        
        if result:
            print(f"已成功弹出U盘 {drive_letter}:\\")
        else:
            print("弹出U盘失败")
            
        return action_refresh_udisk()
        
    except Exception as e:
        print(f"弹出U盘时发生错误: {e}")



def action_refresh_udisk():
    """
    操作：刷新U盘列表
    """
    global udisk_list
    udisk_list = get_actual_usb_drives()
    return action_into_main_menu()

def action_scan_file():
    """
    扫描所有指定后缀的文件，记录信息到数据库
    """
    global current_udisk
    if not SCAN_SUFFIX_LIST:
        print(f"当前没有可用的备份策略，无法扫描文件（请先创建并配置 {CONFIG_FILE_NAME}）")
        print_config_guide()
        return action_into_udisk(current_udisk)
    sql_path = os.path.join(current_udisk['drive_path'], '.auto_backup_data/sqlite.db')
    conn = sqlite3.connect(sql_path)
    cursor = conn.cursor()
    # 遍历file_info表每条数据，如路径对应的文件不存在则删除这条数据
    cursor.execute("SELECT id, file_path FROM file_info")
    rows = cursor.fetchall()
    drive_path = current_udisk['drive_path']
    for row in rows:
        file_id, file_path = row
        full_file_path = os.path.join(drive_path, file_path)
        if not os.path.exists(full_file_path):
            cursor.execute("DELETE FROM file_info WHERE id = ?", (file_id,))
    new_file_count = 0
    old_file_count = 0
    change_file_count = 0
    for root, dirs, files in os.walk(drive_path):
        for file in files:
            file_suffix = os.path.splitext(file)[1].lower().lstrip('.')
            if file_suffix in SCAN_SUFFIX_LIST:
                file_path = os.path.join(root, file)
                file_path_without_drive = file_path.replace(drive_path, '').replace('\\', '/').lstrip('/')
                full_file_path = os.path.join(drive_path, file_path_without_drive)

                file_size = os.path.getsize(full_file_path)
                file_modify_time = os.path.getmtime(full_file_path)
                file_create_time = os.path.getctime(full_file_path)
                # 根据file_path查询数据库，若不存在则插入数据，若存在则更新数据，并且如果更新了file_size或者file_modify_time，则需要把has_copy设置为0
                cursor.execute("SELECT id, file_size, file_modify_time FROM file_info WHERE file_path = ?", 
                              (file_path_without_drive,))
                row = cursor.fetchone()
                
                if row is None:
                    cursor.execute("""
                        INSERT INTO file_info 
                        (file_path, file_size, file_create_time, file_modify_time, suffix) 
                        VALUES (?, ?, ?, ?, ?)
                    """, (file_path_without_drive, file_size, file_create_time, file_modify_time, file_suffix))
                    new_file_count += 1
                else:
                    # 文件已存在，检查是否需要更新
                    file_id, db_file_size, db_file_modify_time = row
                    if db_file_size != file_size or db_file_modify_time != file_modify_time:
                        # 文件有变化，更新记录并将has_copy设为0
                        cursor.execute("""
                            UPDATE file_info 
                            SET file_size = ?, file_modify_time = ?, file_create_time = ?, has_copy = 0, suffix = ?
                            WHERE id = ?
                        """, (file_size, file_modify_time, file_create_time, file_suffix, file_id))
                        change_file_count += 1
                    else:
                        # 文件无变化，只更新基本信息
                        cursor.execute("""
                            UPDATE file_info 
                            SET file_size = ?, file_modify_time = ?, file_create_time = ?, suffix = ?
                            WHERE id = ?
                        """, (file_size, file_modify_time, file_create_time, file_suffix, file_id))
                        old_file_count += 1
    
    conn.commit()
    cursor.close()
    conn.close()

    current_udisk['has_scan'] = True
    print("文件扫描完成")
    print(f"新文件数：{new_file_count}")
    print(f"旧文件数：{old_file_count}")
    if(change_file_count > 0):
        print(f"文件发生变更的数量：{change_file_count}")
    return action_into_udisk(current_udisk,"action_scan_file")

def get_udisk_data_from_db(sql_path):
    """
    从U盘数据库获取统计数据
    
    Args:
        sql_path: 数据库文件路径
    
    Returns:
        dict: {
            'suffix_stats': {suffix: {'count': int, 'pending_count': int, 'total_size': int}},
            'every_time_ranges': {backup_path: {'min_time': float, 'max_time': float}}
        }
    """
    if not os.path.exists(sql_path):
        return None
    
    suffix_stats = {}
    every_time_ranges = {}
    
    try:
        conn = sqlite3.connect(sql_path)
        cursor = conn.cursor()
        
        # 获取每种后缀的文件数量和总大小
        cursor.execute("SELECT suffix, COUNT(*), SUM(file_size) FROM file_info GROUP BY suffix")
        result = cursor.fetchall()
        
        for suffix, count, total_size in result:
            suffix_stats[suffix] = {
                'count': count,
                'pending_count': 0,
                'total_size': total_size or 0
            }
            
            # 对于copy类型，获取待备份数量
            if suffix in SUFFIX_SETTING and SUFFIX_SETTING[suffix]['backup_type'] == 'copy':
                cursor.execute("SELECT COUNT(*) FROM file_info WHERE suffix = ? AND has_copy = 0", (suffix,))
                pending = cursor.fetchone()[0]
                suffix_stats[suffix]['pending_count'] = pending
        
        # 获取every_time类型的文件时间范围
        for backup_path, suffix_list in SAME_PATH_WHIH_EVERY_TIME_SUFFIX.items():
            suffix_list_str = ','.join(['?' for _ in suffix_list])
            backup_type = SUFFIX_SETTING[suffix_list[0]]['backup_type']
            
            if backup_type == 'copy':
                cursor.execute(f"SELECT MIN(file_modify_time), MAX(file_modify_time) FROM file_info WHERE suffix IN ({suffix_list_str}) AND has_copy = 0", suffix_list)
            else:
                cursor.execute(f"SELECT MIN(file_modify_time), MAX(file_modify_time) FROM file_info WHERE suffix IN ({suffix_list_str})", suffix_list)
            
            result = cursor.fetchone()
            if result and result[0] is not None:
                every_time_ranges[backup_path] = {
                    'min_time': result[0],
                    'max_time': result[1]
                }
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"读取数据库失败: {e}")
        return None
    
    return {
        'suffix_stats': suffix_stats,
        'every_time_ranges': every_time_ranges
    }

def merge_udisk_data(udisk_data_list):
    """
    合并多个U盘的统计数据
    
    Args:
        udisk_data_list: U盘数据列表
    
    Returns:
        dict: 合并后的统计数据
    """
    merged_stats = {}
    merged_ranges = {}
    
    for data in udisk_data_list:
        if data is None:
            continue
        
        # 合并后缀统计
        for suffix, stats in data['suffix_stats'].items():
            if suffix not in merged_stats:
                merged_stats[suffix] = {'count': 0, 'pending_count': 0, 'total_size': 0}
            merged_stats[suffix]['count'] += stats['count']
            merged_stats[suffix]['pending_count'] += stats['pending_count']
            merged_stats[suffix]['total_size'] += stats['total_size']
        
        # 合并时间范围
        for backup_path, time_range in data['every_time_ranges'].items():
            if backup_path not in merged_ranges:
                merged_ranges[backup_path] = {
                    'min_time': float('inf'),
                    'max_time': 0
                }
            merged_ranges[backup_path]['min_time'] = min(merged_ranges[backup_path]['min_time'], time_range['min_time'])
            merged_ranges[backup_path]['max_time'] = max(merged_ranges[backup_path]['max_time'], time_range['max_time'])
    
    return {
        'suffix_stats': merged_stats,
        'every_time_ranges': merged_ranges
    }

def calculate_every_time_sub_folder_names(every_time_ranges):
    """
    计算every_time类型的子文件夹名称
    
    Args:
        every_time_ranges: 时间范围数据
    
    Returns:
        dict: {suffix: sub_folder_name}
    """
    suffix_sub_folder_map = {}
    
    for backup_path, time_range in every_time_ranges.items():
        if time_range['min_time'] != float('inf') and time_range['max_time'] != 0:
            sub_folder_name = generate_sub_folder_name(time_range['min_time'], time_range['max_time'])
            for suffix in SAME_PATH_WHIH_EVERY_TIME_SUFFIX[backup_path]:
                suffix_sub_folder_map[suffix] = sub_folder_name
    
    return suffix_sub_folder_map

def format_statistics_text(suffix_stats, suffix_sub_folder_map, display_mode='detail'):
    """
    格式化统计文本
    
    Args:
        suffix_stats: 后缀统计数据
        suffix_sub_folder_map: 后缀到子文件夹名的映射
        display_mode: 显示模式，'detail' 详细模式（单个U盘），'summary' 摘要模式（所有U盘合计）
    
    Returns:
        str: 格式化后的统计文本
    """
    if not suffix_stats:
        return ""
    
    if display_mode == 'summary':
        text = "备份统计（所有U盘合计）："
    else:
        text = ""
    
    # 按配置顺序分组显示
    shown_suffixes = set()
    
    for suffix in SUFFIX_SETTING:
        if suffix in shown_suffixes or suffix not in suffix_stats:
            continue
        
        # 找出同组的后缀（相同备份类型和路径）
        config = SUFFIX_SETTING[suffix]
        backup_type = config['backup_type']
        backup_path = config.get('backup_path', '')
        rule = config.get('target_sub_folder_name_rule', '')
        
        # 找出所有相同配置的后缀
        group_suffixes = []
        for s in SUFFIX_SETTING:
            if (SUFFIX_SETTING[s]['backup_type'] == backup_type and 
                SUFFIX_SETTING[s].get('backup_path', '') == backup_path and
                SUFFIX_SETTING[s].get('target_sub_folder_name_rule', '') == rule):
                if s in suffix_stats:
                    group_suffixes.append(s)
                    shown_suffixes.add(s)
        
        if not group_suffixes:
            continue
        
        # 汇总该组数据
        total_count = sum(suffix_stats[s]['count'] for s in group_suffixes)
        total_size = sum(suffix_stats[s]['total_size'] for s in group_suffixes)
        total_pending = sum(suffix_stats[s]['pending_count'] for s in group_suffixes)
        total_size_gb = round(total_size / 1024 / 1024 / 1024, 2)
        
        # 生成后缀字符串
        if display_mode == 'summary':
            suffix_str = "/".join(group_suffixes)
            line = f"\n- {suffix_str} 文件：共 {total_count} 个"
        else:
            line = f"\n- {group_suffixes[0]} 文件：共 {total_count} 个"
        
        # copy类型显示待备份数量
        if backup_type == 'copy':
            line += f"，待备份 {total_pending} 个"
        
        line += f"，总大小 {total_size_gb} GB"
        
        if display_mode == 'detail':
            line += f"，操作：{backup_type}"
        else:
            line += f"，操作：{backup_type}"
        
        # 显示备份路径
        if backup_path:
            if rule == 'every_day':
                line += f"，路径：{backup_path}/{{YYYY.MM.DD}}"
            elif rule == 'every_time':
                if group_suffixes[0] in suffix_sub_folder_map:
                    line += f"，路径：{backup_path}/{suffix_sub_folder_map[group_suffixes[0]]}"
                else:
                    line += f"，路径：{backup_path}"
        
        text += line
    
    return text

def refresh_udisk_statistic():
    """
    获取当前U盘统计信息（单个U盘）
    """
    global current_suffix_sub_floder_name_map
    
    if not SUFFIX_SETTING:
        return ""
    
    sql_path = os.path.join(current_udisk['drive_path'], '.auto_backup_data/sqlite.db')
    data = get_udisk_data_from_db(sql_path)
    
    if data is None:
        return ""
    
    # 计算子文件夹名称
    suffix_sub_folder_map = calculate_every_time_sub_folder_names(data['every_time_ranges'])
    current_suffix_sub_floder_name_map = suffix_sub_folder_map
    
    # 格式化统计文本
    return format_statistics_text(data['suffix_stats'], suffix_sub_folder_map, 'detail')

def get_all_udisks_statistic():
    """
    汇总所有已扫描U盘的统计信息
    
    Returns:
        str: 统计文本
    """
    if not SUFFIX_SETTING:
        return ""
    
    # 收集所有已扫描U盘的数据
    udisk_data_list = []
    
    for udisk in udisk_list:
        if not udisk.get('has_scan', False):
            continue
        
        sql_path = os.path.join(udisk['drive_path'], '.auto_backup_data/sqlite.db')
        data = get_udisk_data_from_db(sql_path)
        if data:
            udisk_data_list.append(data)
    
    if not udisk_data_list:
        return ""
    
    # 合并数据
    merged_data = merge_udisk_data(udisk_data_list)
    
    # 计算子文件夹名称
    suffix_sub_folder_map = calculate_every_time_sub_folder_names(merged_data['every_time_ranges'])
    
    # 格式化统计文本
    return format_statistics_text(merged_data['suffix_stats'], suffix_sub_folder_map, 'summary')

def get_unique_file_path(target_dir, source_file_name, source_file_size):
    """
    获取唯一的文件路径，处理同名文件
    
    Args:
        target_dir: 目标目录
        source_file_name: 源文件名
        source_file_size: 源文件大小
    
    Returns:
        (target_path, action_type): 目标路径和操作类型
        action_type: 'copy' - 正常复制, 'skip' - 跳过(已存在且相同), 'rename' - 重命名后复制
    """
    # 分离文件名和扩展名
    name, ext = os.path.splitext(source_file_name)
    
    # 检查目标文件是否存在
    target_path = os.path.join(target_dir, source_file_name)
    
    if not os.path.exists(target_path):
        # 目标文件不存在，正常复制
        return target_path, 'copy'
    
    # 目标文件存在，比较大小
    try:
        target_size = os.path.getsize(target_path)
        if target_size == source_file_size:
            # 大小相同，视为同一文件，跳过
            return target_path, 'skip'
    except OSError:
        pass
    
    # 大小不同，需要重命名
    counter = 1
    while True:
        new_name = f"{name}_{counter}{ext}"
        new_target_path = os.path.join(target_dir, new_name)
        
        if not os.path.exists(new_target_path):
            # 新文件名不存在，使用它
            return new_target_path, 'rename'
        
        # 检查重命名后的文件大小
        try:
            new_target_size = os.path.getsize(new_target_path)
            if new_target_size == source_file_size:
                # 大小相同，跳过
                return new_target_path, 'skip'
        except OSError:
            pass
        
        counter += 1
        if counter > 1000:  # 防止无限循环
            print(f"警告：无法为文件 {source_file_name} 找到唯一名称")
            return None, 'error'

def log_backup_action(udisk_info, action_detail):
    """
    记录备份日志
    
    Args:
        udisk_info: U盘信息
        action_detail: 操作详情
    """
    sql_path = os.path.join(udisk_info['drive_path'], '.auto_backup_data/sqlite.db')
    if not os.path.exists(sql_path):
        return
    
    try:
        conn = sqlite3.connect(sql_path)
        cursor = conn.cursor()
        log_time = int(time.time())
        cursor.execute("INSERT INTO backup_log (log_time, action_detail) VALUES (?, ?)", 
                      (log_time, action_detail))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"记录备份日志失败: {e}")

def get_custom_name():
    """
    获取自定义名称
    
    Returns:
        自定义名称字符串，如果用户直接回车则返回空字符串
    """
    custom_name = input("请输入此次备份的自定义名称（可为空）: ").strip()
    return custom_name

def generate_sub_folder_name(min_time, max_time, custom_name=""):
    """
    生成子文件夹名称
    
    Args:
        min_time: 最早时间戳
        max_time: 最晚时间戳
        custom_name: 自定义名称
    
    Returns:
        子文件夹名称
    """
    min_ymd = time.strftime("%Y.%m.%d", time.localtime(min_time))
    max_ymd = time.strftime("%Y.%m.%d", time.localtime(max_time))
    
    if min_ymd == max_ymd:
        base_name = min_ymd
    else:
        min_year, min_month, min_day = min_ymd.split('.')
        max_year, max_month, max_day = max_ymd.split('.')
        
        if min_year != max_year:
            base_name = f"{min_ymd}-{max_ymd}"
        elif min_month != max_month:
            base_name = f"{min_year}.{min_month}.{min_day}-{max_month}.{max_day}"
        else:
            base_name = f"{min_year}.{min_month}.{min_day}-{max_day}"
    
    if custom_name:
        return f"{base_name} {custom_name}"
    else:
        return base_name

def action_into_udisk(udisk_info,last_action = None):
    """
    操作：进入U盘菜单
    """
    #检测当前U盘是否已弹出
    if not is_drive_ready(udisk_info['drive_path'][0]):
        print('U盘已弹出！请重新选择')
        return action_refresh_udisk()

    global current_udisk
    current_udisk = udisk_info
    statistics = refresh_udisk_statistic()
    title = "当前在"+udisk_info['drive_path']+""
    is_scan = "是" if udisk_info.get('has_scan',False) else "否"
    title += f"\n本次是否已扫描？{is_scan}"
    title += statistics
    next_menu_options = []
    if not udisk_info['has_sqlite_flie']:
        next_menu_options.append({'description': '初始化数据库', 'callback': action_init_sqlite_db})
    if(last_action == "action_scan_file"):
        next_menu_options.append({'description': '扫描文件(刚刚已执行)','callback': action_scan_file})
    else:
        next_menu_options.append({'description': '扫描文件','callback': action_scan_file})
    if(last_action == "action_backup_file"):
        next_menu_options.append({'description': '备份文件(刚刚已执行)', 'callback': action_backup_file})
    else:
        next_menu_options.append({'description': '备份文件', 'callback': action_backup_file})
    next_menu_options.append({'description': '弹出U盘', 'callback': action_pop_udisk})
    next_menu_options.append({'description': '返回主菜单', 'callback': action_into_main_menu})
    return (title,next_menu_options)

def action_backup_file():
    """备份当前U盘文件"""
    global current_udisk
    
    if not SUFFIX_SETTING:
        print(f"当前没有可用的备份策略，无法备份文件（请先创建并配置 {CONFIG_FILE_NAME}）")
        print_config_guide()
        return action_into_udisk(current_udisk)
    
    # 获取自定义名称
    custom_name = get_custom_name()
    
    # 检查是否已扫描
    has_scan_file = current_udisk.get('has_scan', False)
    if not has_scan_file:
        print("U盘未扫描，正在自动扫描...")
        action_scan_file()
    
    # 检查备份目录
    if not check_backup_dir():
        return action_into_udisk(current_udisk)
    
    # 获取备份统计
    sql_path = os.path.join(current_udisk['drive_path'], '.auto_backup_data/sqlite.db')
    if not os.path.exists(sql_path):
        print("数据库文件不存在，请先初始化数据库")
        return action_into_udisk(current_udisk)
    
    conn = sqlite3.connect(sql_path)
    cursor = conn.cursor()
    
    # 获取每种后缀的文件列表
    backup_stats = {'copy': 0, 'move': 0, 'delete': 0, 'skip': 0, 'error': 0}
    
    # 按备份类型和路径分组处理
    for suffix, config in SUFFIX_SETTING.items():
        backup_type = config['backup_type']
        backup_path = config.get('backup_path', '')
        rule = config.get('target_sub_folder_name_rule', '')
        
        # 获取该后缀的文件列表
        if backup_type == 'copy':
            # copy类型：只处理待备份的文件
            cursor.execute("SELECT id, file_path, file_size, file_modify_time FROM file_info WHERE suffix = ? AND has_copy = 0", (suffix,))
        else:
            # move/delete类型：处理所有文件
            cursor.execute("SELECT id, file_path, file_size, file_modify_time FROM file_info WHERE suffix = ?", (suffix,))
        
        files = cursor.fetchall()
        
        if not files:
            continue
        
        print(f"\n处理 {suffix} 文件（共 {len(files)} 个）...")
        
        # 确定目标目录
        if rule == 'every_day':
            # every_day类型：每个文件根据修改日期生成子目录
            for file_id, file_path, file_size, file_modify_time in files:
                # 生成日期子目录
                date_str = time.strftime("%Y.%m.%d", time.localtime(file_modify_time))
                target_dir = os.path.join(backup_path, date_str)
                os.makedirs(target_dir, exist_ok=True)
                
                # 获取文件名
                file_name = os.path.basename(file_path)
                source_path = os.path.join(current_udisk['drive_path'], file_path)
                
                # 处理同名文件
                target_path, action = get_unique_file_path(target_dir, file_name, file_size)
                
                if action == 'skip':
                    print(f"跳过（已存在且相同）：{file_path}")
                    backup_stats['skip'] += 1
                    # 对于copy类型，标记为已备份
                    if backup_type == 'copy':
                        cursor.execute("UPDATE file_info SET has_copy = 1 WHERE id = ?", (file_id,))
                elif action == 'error':
                    backup_stats['error'] += 1
                else:
                    # 执行复制或移动
                    try:
                        if backup_type == 'copy':
                            import shutil
                            shutil.copy2(source_path, target_path)
                            cursor.execute("UPDATE file_info SET has_copy = 1 WHERE id = ?", (file_id,))
                            backup_stats['copy'] += 1
                            if action == 'rename':
                                print(f"备份成功（重命名）：{file_path} -> {os.path.basename(target_path)}")
                            else:
                                print(f"备份成功：{file_path}")
                        elif backup_type == 'move':
                            import shutil
                            shutil.move(source_path, target_path)
                            cursor.execute("DELETE FROM file_info WHERE id = ?", (file_id,))
                            backup_stats['move'] += 1
                            if action == 'rename':
                                print(f"移动成功（重命名）：{file_path} -> {os.path.basename(target_path)}")
                            else:
                                print(f"移动成功：{file_path}")
                        elif backup_type == 'delete':
                            os.remove(source_path)
                            cursor.execute("DELETE FROM file_info WHERE id = ?", (file_id,))
                            backup_stats['delete'] += 1
                            print(f"删除成功：{file_path}")
                    except Exception as e:
                        print(f"操作失败：{file_path} - {e}")
                        backup_stats['error'] += 1
        
        elif rule == 'every_time':
            # every_time类型：同一路径的文件共享子目录
            # 计算时间范围
            if backup_type == 'copy':
                cursor.execute("SELECT MIN(file_modify_time), MAX(file_modify_time) FROM file_info WHERE suffix = ? AND has_copy = 0", (suffix,))
            else:
                cursor.execute("SELECT MIN(file_modify_time), MAX(file_modify_time) FROM file_info WHERE suffix = ?", (suffix,))
            
            result = cursor.fetchone()
            if result and result[0] is not None:
                min_time, max_time = result
                sub_folder_name = generate_sub_folder_name(min_time, max_time, custom_name)
                target_dir = os.path.join(backup_path, sub_folder_name)
                os.makedirs(target_dir, exist_ok=True)
                
                for file_id, file_path, file_size, file_modify_time in files:
                    file_name = os.path.basename(file_path)
                    source_path = os.path.join(current_udisk['drive_path'], file_path)
                    
                    # 处理同名文件
                    target_path, action = get_unique_file_path(target_dir, file_name, file_size)
                    
                    if action == 'skip':
                        print(f"跳过（已存在且相同）：{file_path}")
                        backup_stats['skip'] += 1
                        if backup_type == 'copy':
                            cursor.execute("UPDATE file_info SET has_copy = 1 WHERE id = ?", (file_id,))
                    elif action == 'error':
                        backup_stats['error'] += 1
                    else:
                        try:
                            if backup_type == 'copy':
                                import shutil
                                shutil.copy2(source_path, target_path)
                                cursor.execute("UPDATE file_info SET has_copy = 1 WHERE id = ?", (file_id,))
                                backup_stats['copy'] += 1
                                if action == 'rename':
                                    print(f"备份成功（重命名）：{file_path} -> {os.path.basename(target_path)}")
                                else:
                                    print(f"备份成功：{file_path}")
                            elif backup_type == 'move':
                                import shutil
                                shutil.move(source_path, target_path)
                                cursor.execute("DELETE FROM file_info WHERE id = ?", (file_id,))
                                backup_stats['move'] += 1
                                if action == 'rename':
                                    print(f"移动成功（重命名）：{file_path} -> {os.path.basename(target_path)}")
                                else:
                                    print(f"移动成功：{file_path}")
                        except Exception as e:
                            print(f"操作失败：{file_path} - {e}")
                            backup_stats['error'] += 1
        
        else:
            # 没有子文件夹规则（如delete类型）
            for file_id, file_path, file_size, file_modify_time in files:
                source_path = os.path.join(current_udisk['drive_path'], file_path)
                try:
                    if backup_type == 'delete':
                        os.remove(source_path)
                        cursor.execute("DELETE FROM file_info WHERE id = ?", (file_id,))
                        backup_stats['delete'] += 1
                        print(f"删除成功：{file_path}")
                except Exception as e:
                    print(f"删除失败：{file_path} - {e}")
                    backup_stats['error'] += 1
    
    conn.commit()
    cursor.close()
    conn.close()
    
    # 记录备份日志
    action_detail = f"复制:{backup_stats['copy']},移动:{backup_stats['move']},删除:{backup_stats['delete']},跳过:{backup_stats['skip']},失败:{backup_stats['error']}"
    log_backup_action(current_udisk, action_detail)
    
    print(f"\n备份完成！")
    print(f"复制: {backup_stats['copy']} 个文件")
    print(f"移动: {backup_stats['move']} 个文件")
    print(f"删除: {backup_stats['delete']} 个文件")
    print(f"跳过: {backup_stats['skip']} 个文件")
    if backup_stats['error'] > 0:
        print(f"失败: {backup_stats['error']} 个文件")
    
    input("\n按回车键继续...")
    return action_into_udisk(current_udisk, "action_backup_file")

# 主菜单选项
def action_into_main_menu():
    global current_udisk
    current_udisk = None
    next_menu_options = [
        {'description': '重新检测U盘', 'callback': action_refresh_udisk},
        {'description': '扫描所有U盘文件', 'callback': action_scan_all_udisks},
        {'description': '备份所有U盘文件', 'callback': action_backup_all_udisks},
        {'description': '弹出所有U盘', 'callback': action_eject_all_udisks},
        {'description': '显示当前配置', 'callback': action_show_config},
        {'description': '检测目标路径是否存在', 'callback': check_backup_dir}
    ]
    
    # 如果有未初始化的U盘，添加初始化所有U盘数据库选项
    has_uninitialized = any(not udisk['has_sqlite_flie'] for udisk in udisk_list)
    if has_uninitialized:
        next_menu_options.insert(1, {'description': '初始化所有U盘数据库', 'callback': action_init_all_udisks})
    
    # 将每个U盘信息都添加到菜单中
    for udisk in udisk_list:
        des = udisk['drive_path']
        if not udisk['has_sqlite_flie']:
            des = des+"(未初始化)"
        next_menu_options.append({'description': des, 'callback': action_into_udisk, 'args': [udisk]})

    # 生成主菜单标题（含程序名与版本号，便于用户确认当前版本）
    title = f"【U盘备份工具 v{__version__}】主菜单\n"
    if not SUFFIX_SETTING:
        title += f"\n【配置提示】未找到有效的 {CONFIG_FILE_NAME}，请复制 {EXAMPLE_CONFIG_FILE_NAME} 并重命名为 {CONFIG_FILE_NAME}，修改后重启程序\n"
    
    # U盘列表
    title += "\nU盘列表："
    for udisk in udisk_list:
        drive = udisk['drive_path']
        init_status = "已初始化" if udisk['has_sqlite_flie'] else "未初始化"
        scan_status = "已扫描" if udisk.get('has_scan', False) else "未扫描"
        title += f"\n- {drive} ({init_status}，{scan_status})"
    
    # 备份统计（所有U盘合计）
    if any(udisk.get('has_scan', False) for udisk in udisk_list):
        statistic_text = get_all_udisks_statistic()
        if statistic_text:
            title += "\n" + statistic_text
    
    return (title, next_menu_options)

def check_backup_dir():
    """检测目标路径是否存在"""
    missing_paths = []
    checked_paths = set()  # 避免重复检查同一个路径
    
    for suffix in SUFFIX_SETTING:
        if 'backup_path' in SUFFIX_SETTING[suffix]:
            dir_path = SUFFIX_SETTING[suffix]['backup_path']
            if dir_path not in checked_paths:
                checked_paths.add(dir_path)
                if not os.path.exists(dir_path):
                    missing_paths.append(dir_path)
    
    if not checked_paths:
        print("当前配置中没有备份路径，无需检查")
    elif missing_paths:
        print("以下备份路径不存在：")
        for path in missing_paths:
            print(f"  - {path}")
        
        user_input = input("是否创建这些目录？(y/n): ").strip().lower()
        if user_input == 'y':
            for path in missing_paths:
                try:
                    os.makedirs(path, exist_ok=True)
                    print(f"已创建目录: {path}")
                except Exception as e:
                    print(f"创建目录 {path} 失败: {e}")
        else:
            print("请手动创建缺失的目录后再继续")
            return False
    else:
        print("所有备份路径都已存在")
    
    return action_into_main_menu()

def get_base_dir():
    """获取程序基准目录：打包后为 exe 所在目录，源码运行时为项目根目录"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_config_path():
    """获取配置文件路径（与程序同目录）"""
    return os.path.join(get_base_dir(), CONFIG_FILE_NAME)


def ensure_example_config_file(base_dir):
    """确保程序目录下存在示例配置文件；打包环境下若缺失则从内置资源释放一份"""
    example_path = os.path.join(base_dir, EXAMPLE_CONFIG_FILE_NAME)
    if os.path.exists(example_path):
        return example_path
    if getattr(sys, 'frozen', False):
        bundled_path = os.path.join(getattr(sys, '_MEIPASS', ''), EXAMPLE_CONFIG_FILE_NAME)
        if os.path.exists(bundled_path):
            try:
                import shutil
                shutil.copyfile(bundled_path, example_path)
            except Exception:
                return bundled_path
    return example_path


def print_config_guide():
    """提示用户配置文件不存在或无效，并指导如何创建配置文件"""
    base_dir = get_base_dir()
    example_path = ensure_example_config_file(base_dir)
    print()
    print("=" * 64)
    print(f"如需使用本程序，请先创建配置文件 {CONFIG_FILE_NAME}：")
    print(f"  1. 找到程序目录下的示例配置：{example_path}")
    print(f"  2. 将示例配置复制或重命名为：{os.path.join(base_dir, CONFIG_FILE_NAME)}")
    print("  3. 按示例文件中的注释修改备份策略（后缀、操作类型、备份路径等）")
    print("  4. 修改完成后重新运行本程序生效")
    print("=" * 64)
    print()


def parse_suffix_list(suffix_text):
    """解析后缀配置字符串，支持英文/中文逗号或空格分隔，忽略大小写与 * . 前缀"""
    suffix_list = []
    for chunk in suffix_text.replace('，', ',').split(','):
        for item in chunk.split():
            suffix = item.strip().lower().lstrip('*.')
            if suffix and suffix not in suffix_list:
                suffix_list.append(suffix)
    return suffix_list


def load_config():
    """
    加载 config.ini 配置文件
    配置文件不存在或读取失败时不报错：以空策略运行，并提示用户如何创建配置文件
    """
    global SUFFIX_SETTING, SCAN_SUFFIX_LIST, SAME_PATH_WHIH_EVERY_TIME_SUFFIX, config_source
    config_path = get_config_path()
    new_suffix_setting = {}
    config_source = "未配置"
    
    if not os.path.exists(config_path):
        print(f"配置文件不存在：{config_path}")
        print_config_guide()
    else:
        try:
            parser = configparser.ConfigParser(
                inline_comment_prefixes=('#', ';'),  # 支持行内注释
                interpolation=None,                  # 关闭 % 插值，避免路径中的特殊字符触发异常
            )
            # utf-8-sig 兼容带/不带 BOM 的 UTF-8 文件（Windows 记事本另存为可能带 BOM）
            parser.read(config_path, encoding='utf-8-sig')
            
            for section in parser.sections():
                suffix_list = parse_suffix_list(parser.get(section, 'suffix', fallback=''))
                backup_type = parser.get(section, 'backup_type', fallback='').strip().lower()
                if not suffix_list or not backup_type:
                    print(f"配置段落 [{section}] 缺少 suffix 或 backup_type，已跳过")
                    continue
                if backup_type not in ('copy', 'move', 'delete'):
                    print(f"配置段落 [{section}] 的 backup_type 无效（{backup_type}），已跳过（可选值：copy / move / delete）")
                    continue
                
                backup_path = parser.get(section, 'backup_path', fallback='').strip()
                # 展开路径中的环境变量（如 %USERPROFILE%）与 ~ 前缀（当前用户目录），便于编写通用的示例配置
                backup_path = os.path.expandvars(os.path.expanduser(backup_path))
                rule = parser.get(section, 'target_sub_folder_name_rule', fallback='').strip().lower()
                if rule and rule not in ('every_day', 'every_time'):
                    print(f"配置段落 [{section}] 的 target_sub_folder_name_rule 无效（{rule}），将不生成子文件夹")
                    rule = ''
                
                for suffix in suffix_list:
                    suffix_config = {'backup_type': backup_type}
                    if backup_path:
                        suffix_config['backup_path'] = backup_path
                    if rule:
                        suffix_config['target_sub_folder_name_rule'] = rule
                    new_suffix_setting[suffix] = suffix_config
            
            config_source = "配置文件"
            if not new_suffix_setting:
                print(f"配置文件 {config_path} 中没有加载到任何有效策略")
                print_config_guide()
        except Exception as e:
            print(f"配置文件读取失败：{e}")
            print_config_guide()
            new_suffix_setting = {}
    
    SUFFIX_SETTING = new_suffix_setting
    SCAN_SUFFIX_LIST = list(SUFFIX_SETTING)
    
    # 重新构建SAME_PATH_WHIH_EVERY_TIME_SUFFIX
    SAME_PATH_WHIH_EVERY_TIME_SUFFIX.clear()
    for suffix in SCAN_SUFFIX_LIST:
        if 'target_sub_folder_name_rule' in SUFFIX_SETTING[suffix] and SUFFIX_SETTING[suffix]['target_sub_folder_name_rule'] == 'every_time':
            if SUFFIX_SETTING[suffix]['backup_path'] in SAME_PATH_WHIH_EVERY_TIME_SUFFIX:
                SAME_PATH_WHIH_EVERY_TIME_SUFFIX[SUFFIX_SETTING[suffix]['backup_path']].append(suffix)
            else:
                SAME_PATH_WHIH_EVERY_TIME_SUFFIX[SUFFIX_SETTING[suffix]['backup_path']] = [suffix]

def action_show_config():
    """显示当前配置"""
    global config_source
    print(f"当前生效配置（来源：{config_source}）")
    print()
    if not SUFFIX_SETTING:
        print("当前没有任何备份策略。")
        print_config_guide()
        return action_into_main_menu()
    print("备份策略：")
    
    # 按备份类型和路径分组
    strategies = {}
    for suffix, config in SUFFIX_SETTING.items():
        backup_type = config['backup_type']
        backup_path = config.get('backup_path', '')
        rule = config.get('target_sub_folder_name_rule', '')
        
        # 创建唯一键
        key = f"{backup_type}|{backup_path}|{rule}"
        if key not in strategies:
            strategies[key] = {
                'backup_type': backup_type,
                'backup_path': backup_path,
                'rule': rule,
                'suffixes': []
            }
        strategies[key]['suffixes'].append(suffix)
    
    # 显示配置
    for i, (key, strategy) in enumerate(strategies.items(), 1):
        suffix_str = "/".join(strategy['suffixes'])
        print(f"{i}. {suffix_str} 文件")
        
        # 备份类型
        type_map = {'copy': '复制', 'move': '移动', 'delete': '删除'}
        backup_type = type_map.get(strategy['backup_type'], strategy['backup_type'])
        print(f"   - 备份类型：{backup_type}")
        
        # 备份路径
        if strategy['backup_path']:
            print(f"   - 备份路径：{strategy['backup_path']}")
        
        # 子文件夹规则
        if strategy['rule']:
            if strategy['rule'] == 'every_day':
                print(f"   - 子文件夹规则：按文件修改日期（YYYY.MM.DD）")
            elif strategy['rule'] == 'every_time':
                print(f"   - 子文件夹规则：按时间范围生成（同路径文件共享子文件夹）")
        
        print()
    
    return action_into_main_menu()

def action_init_all_udisks():
    """初始化所有U盘数据库"""
    global udisk_list
    success_count = 0
    for udisk in udisk_list:
        if not udisk['has_sqlite_flie']:
            try:
                sql_path = os.path.join(udisk['drive_path'], '.auto_backup_data/sqlite.db')
                sql_dir = os.path.dirname(sql_path)
                if not os.path.exists(sql_dir):
                    os.mkdir(sql_dir)
                
                conn = sqlite3.connect(sql_path)
                cursor = conn.cursor()
                cursor.execute("""create table file_info(
                    id integer primary key autoincrement,
                    file_path varchar(255),
                    md5 varchar(255) default '',
                    has_copy integer default 0,
                    file_size integer default 0,
                    file_create_time integer default 0,
                    file_modify_time integer default 0,
                    suffix varchar(255))""")
                cursor.execute("""create table backup_log(
                    id integer primary key autoincrement, 
                    log_time integer default 0, 
                    action_detail varchar(255))""")
                conn.commit()
                cursor.close()
                conn.close()
                udisk['has_sqlite_flie'] = True
                success_count += 1
                print(f"U盘 {udisk['drive_path']} 数据库初始化成功")
            except Exception as e:
                print(f"U盘 {udisk['drive_path']} 数据库初始化失败: {e}")
    
    if success_count > 0:
        print(f"成功初始化 {success_count} 个U盘数据库")
    else:
        print("没有需要初始化的U盘")
    
    return action_into_main_menu()

def action_scan_all_udisks():
    """扫描所有U盘文件"""
    global udisk_list
    if not SCAN_SUFFIX_LIST:
        print(f"当前没有可用的备份策略，无法扫描文件（请先创建并配置 {CONFIG_FILE_NAME}）")
        print_config_guide()
        return action_into_main_menu()
    success_count = 0
    for udisk in udisk_list:
        if not udisk['has_sqlite_flie']:
            print(f"U盘 {udisk['drive_path']} 未初始化，跳过扫描")
            continue
        
        try:
            print(f"正在扫描U盘 {udisk['drive_path']}...")
            sql_path = os.path.join(udisk['drive_path'], '.auto_backup_data/sqlite.db')
            conn = sqlite3.connect(sql_path)
            cursor = conn.cursor()
            
            # 删除不存在的文件记录
            cursor.execute("SELECT id, file_path FROM file_info")
            rows = cursor.fetchall()
            drive_path = udisk['drive_path']
            for row in rows:
                file_id, file_path = row
                full_file_path = os.path.join(drive_path, file_path)
                if not os.path.exists(full_file_path):
                    cursor.execute("DELETE FROM file_info WHERE id = ?", (file_id,))
            
            # 扫描新文件
            for root, dirs, files in os.walk(drive_path):
                for file in files:
                    file_suffix = os.path.splitext(file)[1].lower().lstrip('.')
                    if file_suffix in SCAN_SUFFIX_LIST:
                        file_path = os.path.join(root, file)
                        file_path_without_drive = file_path.replace(drive_path, '').replace('\\', '/').lstrip('/')
                        full_file_path = os.path.join(drive_path, file_path_without_drive)
                        
                        file_size = os.path.getsize(full_file_path)
                        file_modify_time = os.path.getmtime(full_file_path)
                        file_create_time = os.path.getctime(full_file_path)
                        
                        cursor.execute("SELECT id, file_size, file_modify_time FROM file_info WHERE file_path = ?", 
                                      (file_path_without_drive,))
                        row = cursor.fetchone()
                        
                        if row is None:
                            cursor.execute("""INSERT INTO file_info 
                                (file_path, file_size, file_create_time, file_modify_time, suffix) 
                                VALUES (?, ?, ?, ?, ?)""", 
                                (file_path_without_drive, file_size, file_create_time, file_modify_time, file_suffix))
                        else:
                            file_id, db_file_size, db_file_modify_time = row
                            if db_file_size != file_size or db_file_modify_time != file_modify_time:
                                cursor.execute("""UPDATE file_info 
                                    SET file_size = ?, file_modify_time = ?, file_create_time = ?, has_copy = 0, suffix = ?
                                    WHERE id = ?""", 
                                    (file_size, file_modify_time, file_create_time, file_suffix, file_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            udisk['has_scan'] = True
            success_count += 1
            print(f"U盘 {udisk['drive_path']} 扫描完成")
        except Exception as e:
            print(f"U盘 {udisk['drive_path']} 扫描失败: {e}")
    
    if success_count > 0:
        print(f"成功扫描 {success_count} 个U盘")
    else:
        print("没有U盘被扫描")
    
    return action_into_main_menu()

def action_backup_all_udisks():
    """备份所有U盘文件"""
    global udisk_list
    import shutil
    
    if not SUFFIX_SETTING:
        print(f"当前没有可用的备份策略，无法备份文件（请先创建并配置 {CONFIG_FILE_NAME}）")
        print_config_guide()
        return action_into_main_menu()
    
    print("开始备份所有U盘文件...")
    
    # 检查所有U盘是否已初始化
    for udisk in udisk_list:
        if not udisk['has_sqlite_flie']:
            print(f"U盘 {udisk['drive_path']} 未初始化，请先初始化")
            return action_into_main_menu()
    
    # 自动扫描未扫描的U盘
    for udisk in udisk_list:
        if not udisk.get('has_scan', False):
            print(f"U盘 {udisk['drive_path']} 未扫描，正在自动扫描...")
            # 临时设置current_udisk进行扫描
            global current_udisk
            old_current = current_udisk
            current_udisk = udisk
            action_scan_file()
            current_udisk = old_current
    
    # 检查备份目录
    if not check_backup_dir():
        return action_into_main_menu()
    
    # 获取自定义名称
    custom_name = get_custom_name()
    
    # 获取备份统计
    backup_stats = {'copy': 0, 'move': 0, 'delete': 0, 'skip': 0, 'error': 0}
    
    # 按备份类型和路径分组处理
    for suffix, config in SUFFIX_SETTING.items():
        backup_type = config['backup_type']
        backup_path = config.get('backup_path', '')
        rule = config.get('target_sub_folder_name_rule', '')
        
        if not backup_path and backup_type != 'delete':
            continue
        
        # 对于every_time类型，先计算所有U盘的时间范围
        if rule == 'every_time':
            min_time_all = float('inf')
            max_time_all = 0
            has_files = False
            
            for udisk in udisk_list:
                sql_path = os.path.join(udisk['drive_path'], '.auto_backup_data/sqlite.db')
                if not os.path.exists(sql_path):
                    continue
                
                conn = sqlite3.connect(sql_path)
                cursor = conn.cursor()
                
                if backup_type == 'copy':
                    cursor.execute("SELECT MIN(file_modify_time), MAX(file_modify_time) FROM file_info WHERE suffix = ? AND has_copy = 0", (suffix,))
                else:
                    cursor.execute("SELECT MIN(file_modify_time), MAX(file_modify_time) FROM file_info WHERE suffix = ?", (suffix,))
                
                result = cursor.fetchone()
                if result and result[0] is not None:
                    min_time_all = min(min_time_all, result[0])
                    max_time_all = max(max_time_all, result[1])
                    has_files = True
                
                cursor.close()
                conn.close()
            
            if not has_files:
                continue
            
            # 生成统一的子文件夹名
            sub_folder_name = generate_sub_folder_name(min_time_all, max_time_all, custom_name)
            target_dir = os.path.join(backup_path, sub_folder_name)
            os.makedirs(target_dir, exist_ok=True)
            print(f"\n处理 {suffix} 文件，备份路径：{target_dir}")
        
        # 对每个U盘执行备份
        for udisk in udisk_list:
            sql_path = os.path.join(udisk['drive_path'], '.auto_backup_data/sqlite.db')
            if not os.path.exists(sql_path):
                continue
            
            conn = sqlite3.connect(sql_path)
            cursor = conn.cursor()
            
            # 获取文件列表
            if backup_type == 'copy':
                cursor.execute("SELECT id, file_path, file_size, file_modify_time FROM file_info WHERE suffix = ? AND has_copy = 0", (suffix,))
            else:
                cursor.execute("SELECT id, file_path, file_size, file_modify_time FROM file_info WHERE suffix = ?", (suffix,))
            
            files = cursor.fetchall()
            
            if not files:
                cursor.close()
                conn.close()
                continue
            
            print(f"  U盘 {udisk['drive_path']}：{len(files)} 个文件")
            
            for file_id, file_path, file_size, file_modify_time in files:
                file_name = os.path.basename(file_path)
                source_path = os.path.join(udisk['drive_path'], file_path)
                
                # 确定目标目录
                if rule == 'every_day':
                    date_str = time.strftime("%Y.%m.%d", time.localtime(file_modify_time))
                    file_target_dir = os.path.join(backup_path, date_str)
                    os.makedirs(file_target_dir, exist_ok=True)
                elif rule == 'every_time':
                    file_target_dir = target_dir
                else:
                    file_target_dir = backup_path
                    if file_target_dir:
                        os.makedirs(file_target_dir, exist_ok=True)
                
                # 处理文件
                if backup_type == 'delete':
                    try:
                        os.remove(source_path)
                        cursor.execute("DELETE FROM file_info WHERE id = ?", (file_id,))
                        backup_stats['delete'] += 1
                        print(f"    删除成功：{file_path}")
                    except Exception as e:
                        print(f"    删除失败：{file_path} - {e}")
                        backup_stats['error'] += 1
                else:
                    # 处理同名文件
                    target_file_path, action = get_unique_file_path(file_target_dir, file_name, file_size)
                    
                    if action == 'skip':
                        print(f"    跳过（已存在且相同）：{file_path}")
                        backup_stats['skip'] += 1
                        if backup_type == 'copy':
                            cursor.execute("UPDATE file_info SET has_copy = 1 WHERE id = ?", (file_id,))
                    elif action == 'error':
                        backup_stats['error'] += 1
                    else:
                        try:
                            if backup_type == 'copy':
                                shutil.copy2(source_path, target_file_path)
                                cursor.execute("UPDATE file_info SET has_copy = 1 WHERE id = ?", (file_id,))
                                backup_stats['copy'] += 1
                                if action == 'rename':
                                    print(f"    备份成功（重命名）：{file_path} -> {os.path.basename(target_file_path)}")
                                else:
                                    print(f"    备份成功：{file_path}")
                            elif backup_type == 'move':
                                shutil.move(source_path, target_file_path)
                                cursor.execute("DELETE FROM file_info WHERE id = ?", (file_id,))
                                backup_stats['move'] += 1
                                if action == 'rename':
                                    print(f"    移动成功（重命名）：{file_path} -> {os.path.basename(target_file_path)}")
                                else:
                                    print(f"    移动成功：{file_path}")
                        except Exception as e:
                            print(f"    操作失败：{file_path} - {e}")
                            backup_stats['error'] += 1
            
            conn.commit()
            cursor.close()
            conn.close()
            
            # 记录备份日志
            action_detail = f"复制:{backup_stats['copy']},移动:{backup_stats['move']},删除:{backup_stats['delete']},跳过:{backup_stats['skip']},失败:{backup_stats['error']}"
            log_backup_action(udisk, action_detail)
    
    print(f"\n所有U盘备份完成！")
    print(f"复制: {backup_stats['copy']} 个文件")
    print(f"移动: {backup_stats['move']} 个文件")
    print(f"删除: {backup_stats['delete']} 个文件")
    print(f"跳过: {backup_stats['skip']} 个文件")
    if backup_stats['error'] > 0:
        print(f"失败: {backup_stats['error']} 个文件")
    
    input("\n按回车键继续...")
    return action_into_main_menu()

def action_eject_all_udisks():
    """弹出所有U盘"""
    global udisk_list
    success_count = 0
    for udisk in udisk_list:
        try:
            drive_letter = udisk['drive_path'][0]
            
            # 使用DeviceIoControl方法弹出U盘
            from ctypes import wintypes
            
            # 定义常量
            IOCTL_STORAGE_EJECT_MEDIA = 0x2D4808
            GENERIC_READ_WRITE = 0x80000000 | 0x40000000
            OPEN_EXISTING = 3
            
            # 构造设备路径
            device_path = f"\\\\.\\{drive_letter}:"
            
            # 打开设备
            handle = ctypes.windll.kernel32.CreateFileW(
                device_path,
                GENERIC_READ_WRITE,
                0x1 | 0x2,  # FILE_SHARE_READ | FILE_SHARE_WRITE
                None,
                OPEN_EXISTING,
                0,
                None
            )
            
            if handle == -1:  # INVALID_HANDLE_VALUE
                print(f"无法打开U盘 {udisk['drive_path']} 的设备句柄")
                continue
                
            # 弹出设备
            bytes_returned = wintypes.DWORD()
            result = ctypes.windll.kernel32.DeviceIoControl(
                handle,
                IOCTL_STORAGE_EJECT_MEDIA,
                None,
                0,
                None,
                0,
                ctypes.byref(bytes_returned),
                None
            )
            
            # 关闭句柄
            ctypes.windll.kernel32.CloseHandle(handle)
            
            if result:
                print(f"已成功弹出U盘 {udisk['drive_path']}")
                success_count += 1
            else:
                print(f"弹出U盘 {udisk['drive_path']} 失败")
                
        except Exception as e:
            print(f"弹出U盘 {udisk['drive_path']} 时发生错误: {e}")
    
    if success_count > 0:
        print(f"成功弹出 {success_count} 个U盘")
    else:
        print("没有U盘被弹出")
    
    # 刷新U盘列表
    return action_refresh_udisk()

# 主程序入口
def main():
    menu_system = MenuSystem()

    global udisk_list
    # 加载配置（配置文件不存在时以空策略运行，并提示用户创建配置文件）
    load_config()
    print(f"配置来源: {config_source}")
    init_backup_paths_info()
    udisk_list = get_actual_usb_drives()

    # 定义主菜单
    main_menu_title, main_menu_options= action_into_main_menu()
    
    # 运行主菜单
    menu_system.run_menu(main_menu_title, main_menu_options)

if __name__ == "__main__":
    main()