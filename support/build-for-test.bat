@echo "### Building for test"
@echo off
rem Safety net: a previous build-for-release.bat run that got interrupted
rem before its own cleanup could otherwise leak this marker in here,
rem which would wrongly hide the Null Game from this build too -- testers
rem need it, to exercise the app without a real installed game.
if exist "src\app\assets\exclude_null_game.marker" del /q "src\app\assets\exclude_null_game.marker"
rem Marker bundled into this build only, so the main window title shows
rem "(Build for test <timestamp>)" -- see sgsl.py's _TestBuildMarker.
py -c "from datetime import datetime; open(r'src\app\assets\test_build.marker', 'w').write(datetime.now().strftime('%%Y-%%m-%%d %%H:%%M:%%S'))"
py -m PyInstaller --onefile --icon=src/app/assets/icon.ico --add-data "src/app/assets/icon.ico;app/assets" --add-data "src/app/assets/test_build.marker;app/assets" src/sgsl.py
del /q "src\app\assets\test_build.marker"
if exist "sgsl-for-test.exe" del /q "sgsl-for-test.exe"
copy .\dist\sgsl.exe sgsl-for-test.exe
