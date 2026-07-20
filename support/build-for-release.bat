@echo off
cd ..
if exist "dist" (
    rmdir /s /q "dist"
)
py -m PyInstaller --onefile --noconsole --icon=src/app/assets/icon.ico --add-data "src/app/assets/icon.ico;app/assets" src/sgsl.py
if exist "sgsl.exe" del /q "sgsl.exe"
copy .\dist\sgsl.exe .
echo Done
pause