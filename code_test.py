import win32api
import win32con
import win32file
import os

def get_actual_usb_drives():
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
    
    return actual_drives

usb_drives = get_actual_usb_drives()
print("实际插入的U盘:", usb_drives)