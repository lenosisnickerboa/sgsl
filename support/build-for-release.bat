cd ..
if exist "dist" (
    rmdir /s /q "dist"
)
py -m PyInstaller --onefile --noconsole src/sgsl.py
if exist "sgsl.exe" del /q "sgsl.exe"
copy .\dist\sgsl.exe .
echo Done
pause