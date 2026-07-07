@echo off
setlocal enabledelayedexpansion

if "%1"=="" (
    echo "Usage: %0 <repeat_count> <exit_code>"
    exit /b 1
)

set "repeat_count=%1"
set "exit_code=%2"

set "counter=0"

:repeat
echo stdout: Some output %counter% ...
echo stderr: Some output %counter% ... 1>&2
set /a "counter+=1"

if !counter! lss %repeat_count% (
    timeout /t 1 >nul
    goto repeat
)

exit /b %exit_code%
