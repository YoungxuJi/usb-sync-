@echo off
REM One-click build script. Generates dist\U盘备份工具\ (see scripts/build_exe.py)
cd /d "%~dp0.."
where python3 >nul 2>nul
if %errorlevel%==0 (
    python3 "scripts\build_exe.py"
) else (
    python "scripts\build_exe.py"
)
pause
