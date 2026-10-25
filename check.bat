@echo off
rem Ren'Py branch checker
rem Drag a Ren'Py project folder onto this file, or run:
rem   check.bat "C:\path\to\your\renpy\project"

if "%~1"=="" (
    echo Usage:
    echo   Drag a Ren'Py project folder onto this file, or
    echo   check.bat "C:\path\to\your\renpy\project"
    echo.
    pause
    exit /b 2
)

python "%~dp0renpy_check.py" "%~1" --html "%~dp0report.html"
echo.
echo Exit code: %errorlevel%
echo Report: %~dp0report.html
echo.
pause
