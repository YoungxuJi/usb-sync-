"""PyInstaller 打包脚本：在项目根目录生成 dist/U盘备份工具/ 发布文件夹

用法：
    python scripts/build_exe.py

打包完成后：
    - 可执行文件位于 dist/U盘备份工具/U盘备份工具.exe
    - 示例配置 config.example.ini 会同时复制到该目录，便于用户直接编辑
    - 发布压缩包位于 dist/U盘备份工具.zip，可直接上传 GitHub Releases
"""
import os
import shutil
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_NAME = 'U盘备份工具'
ENTRY_SCRIPT = os.path.join('src', 'main.py')
EXAMPLE_CONFIG = 'config.example.ini'


def main():
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

    # 将示例配置复制到发布目录，用户首次运行前即可查看和编辑
    dist_dir = os.path.join(PROJECT_ROOT, 'dist', APP_NAME)
    shutil.copyfile(
        os.path.join(PROJECT_ROOT, EXAMPLE_CONFIG),
        os.path.join(dist_dir, EXAMPLE_CONFIG),
    )

    # 生成发布压缩包，便于上传 GitHub Releases
    zip_path = shutil.make_archive(
        os.path.join(PROJECT_ROOT, 'dist', APP_NAME), 'zip',
        root_dir=os.path.join(PROJECT_ROOT, 'dist'), base_dir=APP_NAME,
    )

    print()
    print('打包完成，发布目录：' + dist_dir)
    print('可执行文件：' + os.path.join(dist_dir, APP_NAME + '.exe'))
    print('发布压缩包：' + zip_path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
