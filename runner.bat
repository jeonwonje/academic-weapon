@echo off
cd /d "%~dp0"

echo.
echo   ================================
echo     Canvas Academic Weapon
echo   ================================
echo.
echo   1. Sync courses
echo   2. View announcements
echo   3. View assignments
echo   4. Sync then view announcements
echo   5. Sync then view assignments
echo.
set /p choice="  Pick an option (1/2/3/4/5): "

if "%choice%"=="1" goto sync
if "%choice%"=="2" goto view_announcements
if "%choice%"=="3" goto view_assignments
if "%choice%"=="4" goto both_announcements
if "%choice%"=="5" goto both_assignments
echo Invalid choice.
goto end

:sync
python scripts\sync_canvas.py
if %errorlevel% neq 0 (
    echo.
    echo Sync finished with errors. Check logs\sync.log for details.
)
goto end

:view_announcements
python scripts\view_announcements.py
goto end

:view_assignments
python scripts\view_assignments.py
goto end

:both_announcements
python scripts\sync_canvas.py
if %errorlevel% neq 0 (
    echo.
    echo Sync finished with errors. Check logs\sync.log for details.
)
echo.
python scripts\view_announcements.py
goto end

:both_assignments
python scripts\sync_canvas.py
if %errorlevel% neq 0 (
    echo.
    echo Sync finished with errors. Check logs\sync.log for details.
)
echo.
python scripts\view_assignments.py
goto end

:end
pause