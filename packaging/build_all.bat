@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0.."

echo ============================================
echo   维罗妮卡 X 助手 - 一键构建
echo ============================================
echo.

set "PY=python"
where py >nul 2>nul && set "PY=py -I"
if exist "..\RE-CodeVeronica-PC\assistant\venv\Scripts\python.exe" (
    set "PY=..\RE-CodeVeronica-PC\assistant\venv\Scripts\python.exe"
)

echo [1/4] 检查依赖...
%PY% -c "import PySide6, PIL, mss, win32gui, sounddevice, numpy" 2>nul
if errorlevel 1 (
    echo   安装依赖...
    %PY% -m pip install -q -r requirements.txt
)

echo [2/4] 打包 exe...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
%PY% -m PyInstaller app\build.spec --noconfirm --distpath dist --workpath build
if errorlevel 1 (
    echo   ! 打包失败
    pause
    exit /b 1
)

echo [3/4] 编译安装包...
set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo   ! 找不到 Inno Setup 的 ISCC.exe
    echo     装一个：winget install JRSoftware.InnoSetup
    pause
    exit /b 1
)
"%ISCC%" packaging\installer.iss
if errorlevel 1 (
    echo   ! 安装包编译失败
    pause
    exit /b 1
)

echo [4/4] 完成
echo.
echo   exe  : dist\VeraLauncher.exe
for %%f in (packaging\output\*.exe) do echo   安装包: %%f
echo.
pause
