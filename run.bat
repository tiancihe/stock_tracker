@echo off
chcp 65001 >nul
set PYTHON=C:\Users\tianc\.lmstudio\extensions\backends\vendor\_amphibian\cpython3.11-win-x86@6\python.exe

echo ========================================
echo   股票追踪系统
echo ========================================
echo.
echo [1] 采集数据
echo [2] 启动看板
echo [3] 采集 + 启动看板
echo.

choice /c 123 /n /m "请选择操作: "
if errorlevel 3 goto both
if errorlevel 2 goto dashboard
if errorlevel 1 goto collect

:collect
echo.
"%PYTHON%" main.py collect
echo.
pause
exit /b

:dashboard
echo.
"%PYTHON%" main.py dashboard
exit /b

:both
echo.
"%PYTHON%" main.py both
exit /b
