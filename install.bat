@echo off
setlocal
chcp 65001 >nul

cd /d "%~dp0"

set "INSTALL_URL=https://zsj0000.github.io/install.py"
set "INSTALL_FILE=install"

if exist "%INSTALL_FILE%" del /f /q "%INSTALL_FILE%" >nul 2>&1

echo 正在创建 install 文件...
python -c "import urllib.request; open('install','wb').write(urllib.request.urlopen('%INSTALL_URL%', timeout=30).read())"

if errorlevel 1 (
    echo 创建 install 文件失败。
    if exist "%INSTALL_FILE%" del /f /q "%INSTALL_FILE%" >nul 2>&1
    pause
    exit /b 1
)

if not exist "%INSTALL_FILE%" (
    echo install 文件不存在。
    pause
    exit /b 1
)

echo 正在运行 install...
python "%INSTALL_FILE%"
set "INSTALL_RESULT=%errorlevel%"

echo 正在删除 install 文件...
if exist "%INSTALL_FILE%" del /f /q "%INSTALL_FILE%"

if exist "%INSTALL_FILE%" (
    echo 警告：install 文件删除失败，请手动删除。
) else (
    echo install 文件已删除。
)

if not "%INSTALL_RESULT%"=="0" (
    echo 安装程序执行失败，退出码：%INSTALL_RESULT%
    pause
    exit /b %INSTALL_RESULT%
)

echo 安装程序执行完成。
pause
exit /b 0
