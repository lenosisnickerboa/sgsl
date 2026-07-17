@echo off
if exist "%~dp0sgsl-for-test.exe" (
    echo Found sglsl-for-test.exe, launching...
    "%~dp0sgsl-for-test.exe"
) else if exist "%~dp0sgsl.exe" (
    echo Found sgls.exe, launching...
    "%~dp0sgsl.exe"
) else (
    echo Neither sgsl-for-test.exe nor sgsl.exe was found in this folder.
)
pause