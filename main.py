import os
import time
from MenuSystem import MenuSystem  # 从模块中导入类
import win32api
import win32con
import win32file
import ctypes
import sqlite3


udisk_list = []
current_udisk = None
current_suffix_sub_floder_name_map = {}
DEFAULT_RAW_PATH = 'D:\\35906\Pictures\相机'
DEFAULT_JPG_PATH = 'D:\\backup\jpg'
DEFAULT_VIDEO_PATH = 'D:\\35906\Videos\Captures'

#不同文件类型备份策略
SUFFIX_SETTING={
    'jpg':{
        'backup_type':'copy',
        'backup_path':DEFAULT_JPG_PATH,
        'target_sub_floder_name_rule':'every_day'

    },
    'jpeg':{
        'backup_type':'copy',
        'backup_path':DEFAULT_JPG_PATH,
        'target_sub_floder_name_rule':'every_day'

    },
    'mov':{
        'backup_type':'move',
        'backup_path':DEFAULT_VIDEO_PATH,
        'target_sub_floder_name_rule':'every_time'
    },
    'mp4':{
        'backup_type':'move',
        'backup_path':DEFAULT_VIDEO_PATH,
        'target_sub_floder_name_rule':'every_time'

    },
    'dng':{
        'backup_type':'move',
        'backup_path':DEFAULT_RAW_PATH,
        'target_sub_floder_name_rule':'every_time'
    },
    'orf':{
        'backup_type':'move',
        'backup_path':DEFAULT_RAW_PATH,
        'target_sub_floder_name_rule':'every_time'
    },
    'lrf':{
        'backup_type':'delete',
    },
}
# 需要扫描的文件后缀
SCAN_SUFFIX_LIST = list(SUFFIX_SETTING)

SAME_PATH_WHIH_EVERY_TIME_SUFFIX = {}
for suffix in SCAN_SUFFIX_LIST:
    if 'target_sub_floder_name_rule' in SUFFIX_SETTING[suffix] and SUFFIX_SETTING[suffix]['target_sub_floder_name_rule'] == 'every_time':
        if SUFFIX_SETTING[suffix]['backup_path'] in SAME_PATH_WHIH_EVERY_TIME_SUFFIX:
            SAME_PATH_WHIH_EVERY_TIME_SUFFIX[SUFFIX_SETTING[suffix]['backup_path']].append(suffix)
        else:
            SAME_PATH_WHIH_EVERY_TIME_SUFFIX[SUFFIX_SETTING[suffix]['backup_path']] = [suffix]
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
def update_backup_paths_info(rename_old_path = False):
    global backup_paths_info
    for backup_path in backup_paths_info:
        if backup_paths_info[backup_path]['oldest_file_time'] == 0 and backup_paths_info[backup_path]['last_file_time'] == 0 :
             backup_paths_info[backup_path]['old_path'] = ''
             backup_paths_info[backup_path]['real_path'] = ''
            #  写到这里了，下次从这开始写
            # else：

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

def action_auto():
    # todo 全自动
    print("功能还没实现呢，再等等。。。")
    pass

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
    
def refresh_udisk_statistic():
    """
    获取U盘统计信息
    """
    global current_suffix_sub_floder_name_map
    sql_path = os.path.join(current_udisk['drive_path'], '.auto_backup_data/sqlite.db')
    if not os.path.exists(sql_path):
        return ""
    suffix_sub_floder_name_map = {}
    conn = sqlite3.connect(sql_path)
    cursor = conn.cursor()
    for backup_path in SAME_PATH_WHIH_EVERY_TIME_SUFFIX:
        selected_suffix_list = SAME_PATH_WHIH_EVERY_TIME_SUFFIX[backup_path]
        selected_suffix_list_str = '","'.join(selected_suffix_list)
        selected_suffix_list_str = '"' + selected_suffix_list_str + '"'
        cursor.execute(f"SELECT MIN(file_modify_time), MAX(file_modify_time) FROM file_info WHERE suffix IN ({selected_suffix_list_str}) and has_copy=0 ")
        result = cursor.fetchall()
        min_time,max_time = result[0]
        min_time_year = time.strftime("%Y", time.localtime(min_time))
        min_time_month = time.strftime("%m", time.localtime(min_time))
        min_time_day = time.strftime("%d", time.localtime(min_time))
        max_time_year = time.strftime("%Y", time.localtime(max_time))
        max_time_month = time.strftime("%m", time.localtime(max_time))
        max_time_day = time.strftime("%d", time.localtime(max_time))
        sub_folder_name = f"{min_time_year}.{min_time_month}.{min_time_day}"
        sub_folder_name_ = ""
        if(min_time_year != max_time_year):
            sub_folder_name_ = f"{max_time_year}.{max_time_month}.{max_time_day}"
        elif(min_time_month != max_time_month):
            sub_folder_name_ = f"{max_time_month}.{max_time_day}"
        elif(min_time_day != max_time_day):
            sub_folder_name_ = f"{max_time_day}"
        if(sub_folder_name_ != ""):
            sub_folder_name = sub_folder_name+"-"+sub_folder_name_
        for suffix in selected_suffix_list:
            suffix_sub_floder_name_map[suffix] = sub_folder_name
    current_suffix_sub_floder_name_map = suffix_sub_floder_name_map
    #获取每种后缀的文件数量和文件总大小
    cursor.execute("SELECT suffix, COUNT(*),SUM(file_size) FROM file_info GROUP BY suffix")
    result = cursor.fetchall()
    return_text = ""
    for row in result:
        file_type, count ,sum = row
        sum = round(sum / 1024 / 1024/1024, 2)
        return_text += f"\n {file_type} 文件数量：{count}"
        return_text += f" 文件总大小：{sum} GB "
        if(file_type in SUFFIX_SETTING):
            return_text += f" 将要执行操作 {SUFFIX_SETTING[file_type]['backup_type']};"
            if('backup_path' in SUFFIX_SETTING[file_type]):
                if(file_type in suffix_sub_floder_name_map):
                    return_text += f" 备份路径：{SUFFIX_SETTING[file_type]['backup_path']}/{suffix_sub_floder_name_map[file_type]};"
                else:
                    return_text += f" 备份路径：{SUFFIX_SETTING[file_type]['backup_path']}/{{Y-m-d}};"
        
    return return_text

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
    
    remark = input("请输入此次备份标题(可为空),按回车键继续...")
    has_scan_file = current_udisk.get('has_scan',False)
    if(not has_scan_file):
        action_scan_file()
    # todo 开始备份文件
    # 1.检查目的地文件夹是否存在
    if not check_backup_dir():
        return action_into_udisk(current_udisk)
    

    

    input("请按回车键继续...")
    return action_into_udisk(current_udisk,"action_backup_file")

# 主菜单选项
def action_into_main_menu():
    global current_udisk
    current_udisk = None
    next_menu_options = [
        {'description': '全自动一条龙!', 'callback': action_auto},
        {'description': '重新检测U盘', 'callback': action_refresh_udisk},
        {'description': '检测目标路径是否存在', 'callback': check_backup_dir}
    ]
    # 将每个U盘信息都添加到菜单中
    for udisk in udisk_list:
        des = udisk['drive_path']
        if not udisk['has_sqlite_flie']:
            des = des+"(未初始化)"
        next_menu_options.append({'description': des, 'callback': action_into_udisk, 'args': [udisk]})

    return ('主菜单', next_menu_options)

def check_backup_dir():
    for suffix in SUFFIX_SETTING:
        if('backup_path' in SUFFIX_SETTING[suffix]):
            dir_path = SUFFIX_SETTING[suffix]['backup_path']
            if not os.path.exists(dir_path):
                print(f"备份路径 {dir_path} 不存在，请创建")
                return False
    return True
# 主程序入口
def main():
    menu_system = MenuSystem()

    global udisk_list
    init_backup_paths_info()
    udisk_list = get_actual_usb_drives()

    # 定义主菜单
    main_menu_title, main_menu_options= action_into_main_menu()
    
    # 运行主菜单
    menu_system.run_menu(main_menu_title, main_menu_options)

if __name__ == "__main__":
    main()