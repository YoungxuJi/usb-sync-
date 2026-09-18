"""PyInstaller 打包脚本：在项目根目录生成 dist/U盘备份工具/ 发布文件夹

用法：
    python scripts/build_exe.py

打包完成后：
    - 可执行文件位于 dist/U盘备份工具/U盘备份工具.exe
    - 示例配置 config.example.ini 会同时复制到该目录，便于用户直接编辑
    - doc/ 目录下的说明文件（运行程序前请阅读我README.MD、使用说明书.MD）会复制到发布目录
    - 发布压缩包位于 dist/UdiskBackup_v<版本号>.zip（版本号解析自 src/main.py 的 __version__），可直接上传 GitHub Releases
"""
import os
import re
import shutil
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_NAME = 'U盘备份工具'
RELEASE_ZIP_NAME = 'UdiskBackup'  # 发布 zip 的英文名：GitHub Release 附件名会将中文等非 ASCII 字符清洗为 "."，zip 内部文件夹仍为中文 APP_NAME
ENTRY_SCRIPT = os.path.join('src', 'main.py')
EXAMPLE_CONFIG = 'config.example.ini'
DOC_DIR = 'doc'  # 随发布包分发的说明文件所在目录
USER_GUIDES = [
    '运行程序前请阅读我README.MD',
    '使用说明书.MD',
]


def get_app_version():
    """从 src/main.py 中解析 __version__ 常量，用于发布包命名（版本号只在代码中维护一处）"""
    main_py_path = os.path.join(PROJECT_ROOT, ENTRY_SCRIPT)
    try:
        with open(main_py_path, encoding='utf-8') as f:
            match = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", f.read())
    except OSError as e:
        print('警告：读取 ' + ENTRY_SCRIPT + ' 失败：' + str(e))
        return ''
    if not match:
        print('警告：未能从 ' + ENTRY_SCRIPT + ' 中解析到 __version__，发布包名将不含版本号')
        return ''
    return match.group(1)


def main():
    # 部分环境（如英文系统的 CI）输出编码无法表示中文（如 cp1252），打印中文时会抛
    # UnicodeEncodeError 导致打包中断；探测到无法编码中文时将输出流切换为 UTF-8
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, 'reconfigure'):
            try:
                '中文'.encode(stream.encoding or 'utf-8')
            except (UnicodeEncodeError, LookupError):
                try:
                    stream.reconfigure(encoding='utf-8', errors='replace')
                except Exception:
                    pass

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print('未检测到 PyInstaller，请先执行：pip install pyinstaller')
        return 1

    os.chdir(PROJECT_ROOT)

    # 构建前清理 dist 输出目录，避免旧版本或更名前的旧产物残留
    dist_root = os.path.join(PROJECT_ROOT, 'dist')
    if os.path.isdir(dist_root):
        try:
            shutil.rmtree(dist_root)
        except OSError as e:
            print('警告：清理 dist 目录失败：' + str(e))

    args = [
        sys.executable, '-m', 'PyInstaller',
        '--noconfirm',   # 覆盖上次打包产物
        '--clean',       # 清理 PyInstaller 缓存
        '--onedir',      # 文件夹模式：启动快，整体分发
        '--console',     # 保留命令行窗口（本程序为交互式命令行工具）
        '--name', APP_NAME,
        # 将示例配置打包进程序，程序发现缺少示例文件时可自动释放一份
        '--add-data', EXAMPLE_CONFIG + os.pathsep + '.',
        ENTRY_SCRIPT,
    ]
    print('执行打包命令：')
    print(' '.join(args))
    print()
    result = subprocess.run(args)
    if result.returncode != 0:
        print()
        print('打包失败，请检查上方 PyInstaller 输出')
        return result.returncode

    # 将示例配置与 doc/ 说明文件复制到发布目录，用户首次运行前即可查看和编辑
    dist_dir = os.path.join(PROJECT_ROOT, 'dist', APP_NAME)
    shutil.copyfile(
        os.path.join(PROJECT_ROOT, EXAMPLE_CONFIG),
        os.path.join(dist_dir, EXAMPLE_CONFIG),
    )
    doc_src = os.path.join(PROJECT_ROOT, DOC_DIR)
    for guide_name in USER_GUIDES:
        shutil.copyfile(
            os.path.join(doc_src, guide_name),
            os.path.join(dist_dir, guide_name),
        )

    # 生成发布压缩包（英文文件名含版本号：GitHub Release 附件名不支持中文，非 ASCII 字符会被清洗为 "."）
    version = get_app_version()
    zip_basename = RELEASE_ZIP_NAME + ('_v' + version if version else '')
    zip_path = shutil.make_archive(
        os.path.join(PROJECT_ROOT, 'dist', zip_basename), 'zip',
        root_dir=os.path.join(PROJECT_ROOT, 'dist'), base_dir=APP_NAME,
    )

    print()
    print('打包完成，程序版本：' + ('v' + version if version else '未知'))
    print('发布目录：' + dist_dir)
    print('可执行文件：' + os.path.join(dist_dir, APP_NAME + '.exe'))
    print('发布压缩包：' + zip_path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
