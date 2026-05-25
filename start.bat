@echo off
setlocal enabledelayedexpansion

title ComfyUI Server Startup
color 0A

REM 设置 UTF-8 编码，解决中文路径和文件编码问题
set PYTHONUTF8=1
chcp 65001 >nul 2>&1

REM 镜像源配置
REM   UV_MIRROR     - Python install mirror: auto/ghfast/ghproxy/direct
REM   UV_PIP_MIRROR - PyPI mirror: aliyun/tsinghua/tencent/official
if "%UV_MIRROR%"=="" set UV_MIRROR=auto
if "%UV_PIP_MIRROR%"=="" set UV_PIP_MIRROR=aliyun

REM PyPI 镜像
if "%UV_PIP_MIRROR%"=="aliyun" (
    set "UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/"
) else if "%UV_PIP_MIRROR%"=="tsinghua" (
    set "UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple/"
) else if "%UV_PIP_MIRROR%"=="tencent" (
    set "UV_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple/"
) else if "%UV_PIP_MIRROR%"=="official" (
    set "UV_INDEX_URL=https://pypi.org/simple/"
)

if "%comfyui_env%"=="" (
    set comfyui_env=prod
)

echo.
echo ========================================
echo   ComfyUI Server Startup
echo   Environment: %comfyui_env%
echo ========================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo [1/4] Checking uv package manager...
set "UV_CMD=%SCRIPT_DIR%bin\uv\uv.exe"
if not exist "!UV_CMD!" (
    echo [INFO] Downloading uv...
    if not exist "bin\uv" mkdir "bin\uv"
    powershell -ExecutionPolicy ByPass -c "Invoke-WebRequest -Uri 'https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip' -OutFile 'bin\uv\uv.zip'"

    if errorlevel 1 (
        echo [ERROR] Failed to download uv
        echo.
        pause
        exit /b 1
    )

    powershell -ExecutionPolicy ByPass -c "Expand-Archive -Path 'bin\uv\uv.zip' -DestinationPath 'bin\uv' -Force"
    del "bin\uv\uv.zip" >nul 2>&1
    echo [OK] uv downloaded
) else (
    echo [OK] uv found
)

REM === 预下载 Python，支持多镜像自动回退（每个镜像 180 秒超时） ===
echo [1.2/4] Ensuring Python 3.10 is available...
set "PYTHON_READY=0"
set "MIRROR_IDX=0"
set "AUTO_RETRY=1"
set "SUCCESS_FLAG=%TEMP%\comfyui_python_ok.flag"

if not "%UV_MIRROR%"=="auto" (
    if "%UV_MIRROR%"=="ghfast" set "MIRROR_IDX=0"
    if "%UV_MIRROR%"=="ghproxy" set "MIRROR_IDX=1"
    if "%UV_MIRROR%"=="direct" set "MIRROR_IDX=2"
    set "AUTO_RETRY=0"
)

:try_mirror
if "!MIRROR_IDX!"=="0" set "MIRROR_NAME=ghfast"
if "!MIRROR_IDX!"=="0" set "MIRROR_URL=https://ghfast.top/https://github.com/indygreg/python-build-standalone/releases/download"
if "!MIRROR_IDX!"=="1" set "MIRROR_NAME=ghproxy"
if "!MIRROR_IDX!"=="1" set "MIRROR_URL=https://ghproxy.cn/https://github.com/indygreg/python-build-standalone/releases/download"
if "!MIRROR_IDX!"=="2" set "MIRROR_NAME=direct"
if "!MIRROR_IDX!"=="2" set "MIRROR_URL="
if "!MIRROR_IDX!"=="3" goto :mirror_all_failed

del "!SUCCESS_FLAG!" 2>nul
echo   Trying !MIRROR_NAME! mirror (180s timeout)...

if not "!MIRROR_URL!"=="" goto :mirror_has_url
powershell -ExecutionPolicy ByPass -Command "$p = New-Object System.Diagnostics.Process; $p.StartInfo.FileName = '!UV_CMD!'; $p.StartInfo.Arguments = 'python install cpython-3.10-windows-x86_64-none'; $p.StartInfo.UseShellExecute = $false; $null = $p.Start(); if (-not $p.WaitForExit(180000)) { $p.Kill() } else { if ($p.ExitCode -eq 0) { '' | Set-Content -Path '!SUCCESS_FLAG!' } }"
goto :mirror_check

:mirror_has_url
powershell -ExecutionPolicy ByPass -Command "$p = New-Object System.Diagnostics.Process; $p.StartInfo.FileName = '!UV_CMD!'; $p.StartInfo.Arguments = 'python install cpython-3.10-windows-x86_64-none --mirror !MIRROR_URL!'; $p.StartInfo.UseShellExecute = $false; $null = $p.Start(); if (-not $p.WaitForExit(180000)) { $p.Kill() } else { if ($p.ExitCode -eq 0) { '' | Set-Content -Path '!SUCCESS_FLAG!' } }"

:mirror_check
if exist "!SUCCESS_FLAG!" (
    set "PYTHON_READY=1"
    del "!SUCCESS_FLAG!" 2>nul
    echo   [OK] Python ready via !MIRROR_NAME!
    goto :mirror_done
)

echo   [WARN] !MIRROR_NAME! failed, trying next...
if "!AUTO_RETRY!"=="0" goto :mirror_all_failed
set /a "MIRROR_IDX+=1"
goto :try_mirror

:mirror_all_failed
echo [ERROR] All mirrors failed to download Python 3.10
echo   You can set UV_MIRROR=direct and try again with a VPN
pause
exit /b 1

:mirror_done
echo.
REM ==========================================

REM === 启动前检查更新 ===
echo [1.5/4] Checking for updates...
"!UV_CMD!" run --python cpython-3.10-windows-x86_64-none --with-requirements requirements.txt scripts\upgrade_check.py
if errorlevel 2 (
    echo [ERROR] 更新检查遇到严重错误
    pause
    exit /b 1
)
if errorlevel 1 (
    echo [WARN] 更新检查失败，继续使用本地版本
)
echo.
REM =====================

echo [2/4] Checking config file...
if not exist "config_%comfyui_env%.yml" (
    echo [INFO] Config file not found, will be auto-created from config.example.yml
) else (
    echo [OK] config_%comfyui_env%.yml found
)
echo.

echo [3/4] Checking MySQL...
if not exist "bin\mysql" (
    echo [ERROR] MySQL directory not found: bin\mysql
    echo Please deploy MySQL to bin\mysql directory
    echo.
    pause
    exit /b 1
)
echo [OK] MySQL directory found
echo.

echo [4/4] Starting services...
echo ========================================
echo.


!UV_CMD! run --managed-python --python cpython-3.10-windows-x86_64-none --with-requirements requirements.txt scripts\launchers\start_windows.py

if errorlevel 1 (
    echo.
    echo ========================================
    echo [ERROR] Program exited with code: %errorlevel%
    echo ========================================
    echo.
    pause
)

endlocal
