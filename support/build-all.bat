@echo off
cd ..
if exist "dist" (
    rmdir /s /q "dist"
)
call "%~dp0build-for-test.bat"
call "%~dp0build-for-release.bat"
echo Done
pause