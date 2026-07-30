@echo off
cd ..
if exist "dist" (
    rmdir /s /q "dist"
)
rem Safety net: a previous build-for-test.bat run that got interrupted
rem before its own cleanup could otherwise leak this marker in here,
rem which would wrongly hide the Null Game from this build too.
if exist "src\app\assets\exclude_null_game.marker" del /q "src\app\assets\exclude_null_game.marker"
py -m PyInstaller --onefile --noconsole --icon=src/app/assets/icon.ico --add-data "src/app/assets/icon.ico;app/assets" src/sgsl.py
if exist "sgsl.exe" del /q "sgsl.exe"
copy .\dist\sgsl.exe .
echo Done
pause