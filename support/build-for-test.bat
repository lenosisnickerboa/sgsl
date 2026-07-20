@echo off
cd ..
if exist "dist" (
    rmdir /s /q "dist"
)
py -m PyInstaller --onefile --icon=src/app/assets/icon.ico --add-data "src/app/assets/icon.ico;app/assets" src/sgsl.py
if exist "sgsl-for-test.exe" del /q "sgsl-for-test.exe"
copy .\dist\sgsl.exe sgsl-for-test.exe
echo Done
pause