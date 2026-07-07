if exist "dist" (
    rmdir /s /q "dist"
)
py -m PyInstaller --onefile --noconsole src/cs2sl.py
if exist "cs2sl.exe" del /q "cs2sl.exe"
copy .\dist\cs2sl.exe .
echo Done
pause