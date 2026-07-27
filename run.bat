@echo off
chcp 65001 >nul
set PYTHON=C:\Users\tianc\.lmstudio\extensions\backends\vendor\_amphibian\cpython3.11-win-x86@6\python.exe
set SCRIPTS=C:\Users\tianc\.lmstudio\extensions\backends\vendor\_amphibian\cpython3.11-win-x86@6\Scripts

echo ========================================
echo   股票追踪系统 - 兆易创新 (603986)
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
echo 正在采集数据...
cd /d "%~dp0"
"%PYTHON%" collector.py
echo.
echo 采集完成!
pause
exit /b

:dashboard
echo.
echo 启动看板...
cd /d "%~dp0"
"%SCRIPTS%\streamlit.exe" run dashboard.py
exit /b

:both
echo.
echo 正在采集数据...
cd /d "%~dp0"
"%PYTHON%" collector.py
echo.
echo 采集完成，启动看板...
"%SCRIPTS%\streamlit.exe" run dashboard.py
exit /b
