@echo "### Building for test"
@echo off
rem Marker bundled into this build only, so GameFactory hides the Null
rem Game from testers -- see game_factory.py's _ExcludeNullGameMarker.
type nul > "src\app\assets\exclude_null_game.marker"
py -m PyInstaller --onefile --icon=src/app/assets/icon.ico --add-data "src/app/assets/icon.ico;app/assets" --add-data "src/app/assets/exclude_null_game.marker;app/assets" src/sgsl.py
del /q "src\app\assets\exclude_null_game.marker"
if exist "sgsl-for-test.exe" del /q "sgsl-for-test.exe"
copy .\dist\sgsl.exe sgsl-for-test.exe
