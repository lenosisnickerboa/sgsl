@echo "### Building for release"
@echo off
rem Safety net: a previous build-for-test.bat run that got interrupted
rem before its own cleanup could otherwise leak this marker in here,
rem which would wrongly tag this release build as a test build too.
if exist "src\app\assets\test_build.marker" del /q "src\app\assets\test_build.marker"
rem Marker bundled into this build only, so GameFactory hides the Null
rem Game from real users -- see game_factory.py's _ExcludeNullGameMarker.
type nul > "src\app\assets\exclude_null_game.marker"
py -m PyInstaller --onefile --noconsole --icon=src/app/assets/icon.ico --add-data "src/app/assets/icon.ico;app/assets" --add-data "src/app/assets/exclude_null_game.marker;app/assets" src/sgsl.py
del /q "src\app\assets\exclude_null_game.marker"
if exist "sgsl.exe" del /q "sgsl.exe"
copy .\dist\sgsl.exe .
