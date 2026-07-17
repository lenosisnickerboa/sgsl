@echo off
cd ..
if exist "dist" (
    rmdir /s /q "dist"
)
py -m PyInstaller --onefile src/sgsl.py
if exist "sgsl-for-test.exe" del /q "sgsl-for-test.exe"
copy .\dist\sgsl.exe sgsl-for-test.exe
echo Done
pause